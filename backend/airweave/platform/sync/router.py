"""DAG router."""

import asyncio
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.entities._base import (
    BaseEntity,
    ChunkEntity,
    CodeFileEntity,
    FileEntity,
    PolymorphicEntity,
)
from airweave.platform.locator import resource_locator
from airweave.platform.transformers.code_file_chunker import code_file_chunker
from airweave.platform.transformers.code_file_summarizer import code_file_summarizer
from airweave.platform.transformers.default_file_chunker import file_chunker
from airweave.platform.transformers.entity_field_chunker import entity_chunker
from airweave.schemas.dag import DagNode, NodeType, SyncDag


class SyncDAGRouter:
    """Routes entities through the DAG based on producer and entity type."""

    def __init__(
        self,
        dag: SyncDag,
        entity_map: dict[type[BaseEntity], UUID],
    ):
        """Initialize the DAG router."""
        self.dag = dag
        self.entity_map = entity_map
        self.route = self._build_execution_route()
        # Add transformer cache to eliminate 1.5s database lookups
        self._transformer_cache = {}

    async def initialize_transformer_cache(self, db: AsyncSession) -> None:
        """Pre-load all transformers to eliminate database lookups during processing."""
        logger.info("🔧 ROUTER_CACHE_INIT Initializing transformer cache")
        cache_start = asyncio.get_event_loop().time()

        # Get all transformer IDs used in the DAG
        transformer_ids = set()
        for node in self.dag.nodes:
            if node.transformer_id:
                transformer_ids.add(node.transformer_id)

        # Batch load all transformers
        for transformer_id in transformer_ids:
            transformer = await crud.transformer.get(db, id=transformer_id)
            if transformer:
                self._transformer_cache[transformer_id] = transformer
                logger.info(f"🔧 ROUTER_CACHE_ADD Cached transformer: {transformer.method_name}")

        cache_elapsed = asyncio.get_event_loop().time() - cache_start
        logger.info(
            f"✅ ROUTER_CACHE_READY Transformer cache initialized in {cache_elapsed:.3f}s "
            f"({len(self._transformer_cache)} transformers cached)"
        )

    def _build_execution_route(self) -> dict[tuple[UUID, UUID], list[Optional[UUID]]]:
        """Construct an execution route for the DAG.

        Maps a tuple of a producer node id with a entity definition id to a consumer node id.

        If the entity is sent to a destination, the route is set to None, this stops the entity
        from being routed further.
        """
        route_map = {}
        for node in self.dag.nodes:
            if node.type == NodeType.entity:
                edge_inwards = self.dag.get_edges_to_node(node.id)

                # Get the producer node
                producer = edge_inwards[0].from_node_id

                edges_outwards = self.dag.get_edges_from_node(node.id)

                # Check if all outgoing edges go to destination nodes
                if edges_outwards:
                    all_destinations = True
                    for edge in edges_outwards:
                        consumer_node = self.dag.get_node(edge.to_node_id)
                        if consumer_node.type != NodeType.destination:
                            all_destinations = False
                            break

                    if all_destinations:
                        # If all outgoing edges go to destinations, stop routing
                        route_map[(producer, node.entity_definition_id)] = None
                    elif len(edges_outwards) == 1:
                        # If there's only one outgoing edge and it's not to a destination,
                        # route to that node
                        route_map[(producer, node.entity_definition_id)] = edges_outwards[
                            0
                        ].to_node_id
                    else:
                        # If there are multiple outgoing edges and not all go to destinations,
                        # this is an invalid configuration
                        raise ValueError(
                            f"Entity node {node.id} has multiple outbound edges "
                            "to non-destination nodes."
                        )
                else:
                    # No outgoing edges, this is a terminal node
                    route_map[(producer, node.entity_definition_id)] = None

        return route_map

    def _get_entity_definition_id(self, entity_type: type) -> UUID:
        """Get entity definition ID for a given entity type.

        This method first tries to find the exact type in the entity map.
        If not found, it tries to find a matching class by name and module.
        This handles dynamically created classes like Parent and Chunk models.

        Args:
            entity_type: The entity type to look up

        Returns:
            The entity definition ID

        Raises:
            ValueError: If no matching entity definition is found
        """
        logger.info(f"🔍 ROUTER_LOOKUP_DEF Looking up definition for {entity_type.__name__}")

        # First try direct lookup
        if entity_type in self.entity_map:
            logger.info(f"✅ ROUTER_DIRECT_MATCH Found direct match for {entity_type.__name__}")
            return self.entity_map[entity_type]

        # Handle PolymorphicEntity subclasses
        if hasattr(entity_type, "__mro__") and issubclass(entity_type, PolymorphicEntity):
            RESERVED_TABLE_ENTITY_ID = UUID("11111111-1111-1111-1111-111111111111")
            logger.info(
                f"🏷️  ROUTER_POLYMORPHIC Using reserved ID for "
                f"PolymorphicEntity {entity_type.__name__}"
            )
            return RESERVED_TABLE_ENTITY_ID

        # Handle dynamically created Parent/Chunk classes
        entity_name = entity_type.__name__
        entity_module = entity_type.__module__

        logger.info(f"🔍 ROUTER_DYNAMIC_LOOKUP Searching for dynamic class pattern: {entity_name}")

        base_name = None
        if entity_name.endswith("Parent"):
            base_name = entity_name.replace("Parent", "Entity")
            logger.info(
                f"🔍 ROUTER_PARENT_PATTERN Detected Parent class, looking for base: {base_name}"
            )
        elif entity_name.endswith("Chunk"):
            base_name = entity_name.replace("Chunk", "Entity")
            logger.info(
                f"🔍 ROUTER_CHUNK_PATTERN Detected Chunk class, looking for base: {base_name}"
            )

        if base_name:
            for cls, definition_id in self.entity_map.items():
                if cls.__name__ == base_name and cls.__module__ == entity_module:
                    logger.info(
                        f"✅ ROUTER_BASE_MATCH Found base class {base_name} for {entity_name}"
                    )
                    # Cache the result for future lookups
                    self.entity_map[entity_type] = definition_id
                    return definition_id

        logger.error(f"❌ ROUTER_NO_DEF_FOUND No entity definition found for {entity_type}")
        raise ValueError(f"No entity definition found for {entity_type}")

    async def process_entity(self, producer_id: UUID, entity: BaseEntity) -> list[BaseEntity]:
        """Route an entity to its next consumer based on DAG structure."""
        entity_context = f"Entity({entity.entity_id})"
        entity_type = type(entity)
        router_start = asyncio.get_event_loop().time()

        logger.info(
            f"🔀 ROUTER_START [{entity_context}] Routing entity of type {entity_type.__name__} "
            f"from producer {producer_id}"
        )

        # Handle special entity types with dedicated processing
        if self._is_code_file_entity(entity_type, entity):
            return await self._handle_code_file_entity(entity, entity_context, router_start)

        if self._is_regular_file_entity(entity_type, entity):
            return await self._handle_regular_file_entity(entity, entity_context, router_start)

        if self._is_chunk_entity_for_field_processing(entity_type, entity):
            return await self._handle_chunk_entity_processing(entity, entity_context, router_start)

        # Normal DAG routing for other entities
        return await self._handle_dag_routing(
            producer_id, entity, entity_context, entity_type, router_start
        )

    def _is_code_file_entity(self, entity_type: type, entity: BaseEntity) -> bool:
        """Check if entity is a CodeFileEntity."""
        return issubclass(entity_type, CodeFileEntity) or isinstance(entity, CodeFileEntity)

    def _is_regular_file_entity(self, entity_type: type, entity: BaseEntity) -> bool:
        """Check if entity is a regular FileEntity (not CodeFileEntity)."""
        return (
            issubclass(entity_type, FileEntity)
            and not issubclass(entity_type, CodeFileEntity)
            and not isinstance(entity, CodeFileEntity)
        )

    def _is_chunk_entity_for_field_processing(self, entity_type: type, entity: BaseEntity) -> bool:
        """Check if entity is a ChunkEntity that needs field processing."""
        return (
            issubclass(entity_type, ChunkEntity)
            and not issubclass(entity_type, FileEntity)
            and not isinstance(entity, FileEntity)
        )

    async def _handle_code_file_entity(
        self, entity: BaseEntity, entity_context: str, router_start: float
    ) -> list[BaseEntity]:
        """Handle CodeFileEntity processing with chunking and optional summarization."""
        logger.info(
            f"💻 ROUTER_CODE_FILE [{entity_context}] Detected CodeFileEntity, applying code chunker"
        )
        chunk_start = asyncio.get_event_loop().time()

        transformed_entities = await code_file_chunker(entity)

        chunk_elapsed = asyncio.get_event_loop().time() - chunk_start
        logger.info(
            f"💻 ROUTER_CODE_CHUNK_DONE [{entity_context}] "
            f"Code chunking complete in {chunk_elapsed:.3f}s "
            f"({len(transformed_entities)} chunks created)"
        )

        if settings.CODE_SUMMARIZER_ENABLED:
            transformed_entities = await self._apply_code_summarization(
                transformed_entities, entity_context
            )

        total_elapsed = asyncio.get_event_loop().time() - router_start
        logger.info(
            f"✅ ROUTER_CODE_COMPLETE [{entity_context}] "
            f"Code processing complete in {total_elapsed:.3f}s"
        )
        return transformed_entities

    async def _apply_code_summarization(
        self, transformed_entities: list[BaseEntity], entity_context: str
    ) -> list[BaseEntity]:
        """Apply code summarization to transformed entities."""
        logger.info(f"📝 ROUTER_CODE_SUMMARY_START [{entity_context}] Applying code summarizer")
        summary_start = asyncio.get_event_loop().time()

        for i, transformed_entity in enumerate(transformed_entities):
            logger.info(f"📝 ROUTER_CODE_SUMMARY_{i} [{entity_context}] Summarizing chunk {i + 1}")
            transformed_entity = await code_file_summarizer(transformed_entity)

        summary_elapsed = asyncio.get_event_loop().time() - summary_start
        logger.info(
            f"📝 ROUTER_CODE_SUMMARY_DONE [{entity_context}] Summarization complete "
            f"in {summary_elapsed:.3f}s"
        )
        return transformed_entities

    async def _handle_regular_file_entity(
        self, entity: BaseEntity, entity_context: str, router_start: float
    ) -> list[BaseEntity]:
        """Handle regular FileEntity processing."""
        entity_type = type(entity)
        logger.info(
            f"📄 ROUTER_FILE [{entity_context}] Detected FileEntity "
            f"(type: {entity_type.__name__}), applying file chunker"
        )
        chunk_start = asyncio.get_event_loop().time()

        # Try to use optimized chunker if available
        try:
            from airweave.platform.transformers.optimized_file_chunker import (
                optimized_file_chunker,
            )

            logger.info(f"🚀 ROUTER_FILE_OPTIMIZED [{entity_context}] Using optimized file chunker")
            transformed_entities = await optimized_file_chunker(entity)
        except ImportError:
            logger.info(f"📄 ROUTER_FILE_DEFAULT [{entity_context}] Using default file chunker")
            transformed_entities = await file_chunker(entity)

        chunk_elapsed = asyncio.get_event_loop().time() - chunk_start
        logger.info(
            f"📄 ROUTER_FILE_CHUNK_DONE [{entity_context}] "
            f"File chunking complete in {chunk_elapsed:.3f}s "
            f"({len(transformed_entities)} entities created)"
        )

        total_elapsed = asyncio.get_event_loop().time() - router_start
        logger.info(
            f"✅ ROUTER_FILE_COMPLETE [{entity_context}] "
            f"File processing complete in {total_elapsed:.3f}s"
        )
        return transformed_entities

    async def _handle_chunk_entity_processing(
        self, entity: BaseEntity, entity_context: str, router_start: float
    ) -> list[BaseEntity]:
        """Handle ChunkEntity field processing."""
        logger.info(
            f"🔧 ROUTER_CHUNK_FIELD [{entity_context}] Detected ChunkEntity, applying field chunker"
        )
        field_start = asyncio.get_event_loop().time()

        chunked_entities = await entity_chunker(entity)

        field_elapsed = asyncio.get_event_loop().time() - field_start

        if len(chunked_entities) > 1:
            logger.info(
                f"🔧 ROUTER_CHUNK_FIELD_SPLIT [{entity_context}] "
                f"Entity split into {len(chunked_entities)} parts in {field_elapsed:.3f}s"
            )
            total_elapsed = asyncio.get_event_loop().time() - router_start
            logger.info(
                f"✅ ROUTER_CHUNK_COMPLETE [{entity_context}] "
                f"Field chunking complete in {total_elapsed:.3f}s"
            )
            return chunked_entities
        else:
            logger.info(f"🔧 ROUTER_CHUNK_FIELD_KEEP [{entity_context}] No field chunking needed")
            # Continue with normal DAG routing since no chunking occurred
            return [entity]

    async def _handle_dag_routing(
        self,
        producer_id: UUID,
        entity: BaseEntity,
        entity_context: str,
        entity_type: type,
        router_start: float,
    ) -> list[BaseEntity]:
        """Handle normal DAG routing for entities."""
        logger.info(f"🗺️  ROUTER_DAG_START [{entity_context}] Starting normal DAG routing")

        try:
            entity_definition_id = self._get_entity_definition_id(entity_type)
            logger.info(
                f"🆔 ROUTER_ENTITY_DEF [{entity_context}] "
                f"Found entity definition ID: {entity_definition_id}"
            )
        except ValueError as e:
            logger.error(
                f"❌ ROUTER_NO_DEF [{entity_context}] No entity definition found: {str(e)}"
            )
            # Return entity as-is if no definition found
            return [entity]

        route_key = (producer_id, entity_definition_id)

        if route_key not in self.route:
            logger.info(
                f"🛑 ROUTER_NO_ROUTE [{entity_context}] No route found, treating as destination"
            )
            total_elapsed = asyncio.get_event_loop().time() - router_start
            logger.info(
                f"✅ ROUTER_DESTINATION [{entity_context}] "
                f"Routing to destination in {total_elapsed:.3f}s"
            )
            return [entity]

        consumer_id = self.route[route_key]

        if consumer_id is None:
            logger.info(
                f"🏁 ROUTER_TERMINAL [{entity_context}] Terminal route, sending to destination"
            )
            total_elapsed = asyncio.get_event_loop().time() - router_start
            logger.info(
                f"✅ ROUTER_TERMINAL_COMPLETE [{entity_context}] "
                f"Terminal routing complete in {total_elapsed:.3f}s"
            )
            return [entity]

        # Get the consumer node and apply transformer
        consumer = self.dag.get_node(consumer_id)
        logger.info(
            f"🔄 ROUTER_TRANSFORM [{entity_context}] Applying transformer from node {consumer_id} "
            f"(type: {consumer.type})"
        )

        transform_start = asyncio.get_event_loop().time()
        transformed_entities = await self._apply_transformer(consumer, entity)
        transform_elapsed = asyncio.get_event_loop().time() - transform_start

        logger.info(
            f"🔄 ROUTER_TRANSFORM_DONE [{entity_context}] "
            f"Transformation complete in {transform_elapsed:.3f}s "
            f"({len(transformed_entities)} entities produced)"
        )

        # Route the transformed entities recursively
        return await self._route_transformed_entities(
            consumer_id, transformed_entities, entity_context, router_start
        )

    async def _route_transformed_entities(
        self,
        consumer_id: UUID,
        transformed_entities: list[BaseEntity],
        entity_context: str,
        router_start: float,
    ) -> list[BaseEntity]:
        """Route transformed entities recursively."""
        logger.info(
            f"🔁 ROUTER_RECURSIVE [{entity_context}] "
            f"Routing {len(transformed_entities)} transformed entities"
        )
        recursive_start = asyncio.get_event_loop().time()

        result_entities = []
        for i, transformed_entity in enumerate(transformed_entities):
            logger.info(
                f"🔁 ROUTER_RECURSIVE_{i} [{entity_context}] Routing transformed entity {i + 1}"
            )
            sub_entities = await self.process_entity(consumer_id, transformed_entity)
            result_entities.extend(sub_entities)

        recursive_elapsed = asyncio.get_event_loop().time() - recursive_start
        total_elapsed = asyncio.get_event_loop().time() - router_start

        logger.info(
            f"🔁 ROUTER_RECURSIVE_DONE [{entity_context}] "
            f"Recursive routing complete in {recursive_elapsed:.3f}s "
            f"({len(result_entities)} final entities)"
        )
        logger.info(
            f"✅ ROUTER_COMPLETE [{entity_context}] All routing complete in {total_elapsed:.3f}s"
        )

        return result_entities

    def _get_if_node_is_destination(self, node: DagNode) -> bool:
        """Get if a node is a destination."""
        return node.type == NodeType.destination

    async def _apply_transformer(self, consumer: DagNode, entity: BaseEntity) -> list[BaseEntity]:
        """Apply the transformer to the entity."""
        entity_context = f"Entity({entity.entity_id})"

        if consumer.transformer_id:
            logger.info(
                f"🔧 ROUTER_TRANSFORMER_LOOKUP [{entity_context}] "
                f"Looking up transformer {consumer.transformer_id}"
            )
            lookup_start = asyncio.get_event_loop().time()

            # Use cached transformer instead of database lookup
            transformer = self._transformer_cache.get(consumer.transformer_id)
            if not transformer:
                logger.warning(
                    f"⚠️  ROUTER_CACHE_MISS [{entity_context}] Transformer not in cache, "
                    f"falling back to database lookup"
                )
                # Create a temporary database session just for this lookup
                from airweave.db.session import get_db_context

                async with get_db_context() as db:
                    transformer = await crud.transformer.get(db, id=consumer.transformer_id)
                    # Cache for future use
                    if transformer:
                        self._transformer_cache[consumer.transformer_id] = transformer

            lookup_elapsed = asyncio.get_event_loop().time() - lookup_start
            logger.info(
                f"🔧 ROUTER_TRANSFORMER_FOUND [{entity_context}] "
                f"Transformer found in {lookup_elapsed:.3f}s "
                f"(cached: {consumer.transformer_id in self._transformer_cache})"
            )

            logger.info(f"⚙️  ROUTER_TRANSFORMER_APPLY [{entity_context}] Applying transformer")
            apply_start = asyncio.get_event_loop().time()

            transformer_callable = resource_locator.get_transformer(transformer)
            result = await transformer_callable(entity)

            apply_elapsed = asyncio.get_event_loop().time() - apply_start
            logger.info(
                f"⚙️  ROUTER_TRANSFORMER_DONE [{entity_context}] "
                f"Transformer applied in {apply_elapsed:.3f}s "
                f"(produced {len(result)} entities)"
            )

            return result
        else:
            logger.error(
                f"❌ ROUTER_NO_TRANSFORMER [{entity_context}] "
                f"No transformer found for node {consumer.id}"
            )
            raise ValueError(f"No transformer found for node {consumer.id}")
