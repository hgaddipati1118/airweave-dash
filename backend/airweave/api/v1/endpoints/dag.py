"""API endpoints for the DAG system."""

from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.dag_service import dag_service
from airweave.crud.crud_dag import (
    sync_dag,
)
from airweave.models.user import User
from airweave.schemas.dag import NodeType

router = TrailingSlashRouter()


@router.get("/sync/{sync_id}/dag/", response_model=schemas.SyncDag)
async def get_sync_dag(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
):
    """Get the DAG definition for a sync."""
    dag = await sync_dag.get_by_sync_id(db, sync_id=sync_id, current_user=current_user)
    if not dag:
        raise HTTPException(status_code=404, detail="DAG not found")
    return dag


def _validate_entity_node_edges(dag: schemas.SyncDag, entity_node: schemas.DagNode) -> None:
    """Validate that entity node has exactly one outgoing edge."""
    edges_from_entity_node = dag.get_edges_from_node(entity_node.id)
    if not edges_from_entity_node:
        raise HTTPException(
            status_code=400, detail=f"Entity node '{entity_node.name}' has no outgoing edges"
        )
    if len(edges_from_entity_node) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Entity node '{entity_node.name}' has more than one outgoing edge. "
                f"Only one destination is allowed."
            ),
        )


def _process_transformer_chain(
    dag: schemas.SyncDag,
    entity_dag: schemas.SyncDagCreate,
    current_node: schemas.DagNode,
    destination_node_create: schemas.DagNodeCreate,
) -> None:
    """Process the chain of transformers until reaching a destination."""
    while True:
        edges_from_current = dag.get_edges_from_node(current_node.id)
        if not edges_from_current:
            raise HTTPException(
                status_code=400, detail=f"Node '{current_node.name}' has no outgoing edges"
            )

        if len(edges_from_current) > 1:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Node '{current_node.name}' has more than one outgoing edge. "
                    f"Only one path is allowed."
                ),
            )

        edge_from_current = edges_from_current[0]
        edge_from_current_create = convert_to_edge_create(edge_from_current)
        entity_dag.edges.append(edge_from_current_create)

        next_node = dag.get_node(edge_from_current.to_node_id)

        if next_node.type == NodeType.destination:
            # Reached destination, we're done
            break
        elif next_node.type == NodeType.transformer:
            # Add transformer node
            next_node_create = convert_to_node_create(next_node)
            entity_dag.nodes.append(next_node_create)

            # Check if this is a web fetcher (which should continue the chain)
            # or a regular chunker (which should end the chain)
            if "web_fetcher" in next_node.name.lower() or "web fetcher" in next_node.name.lower():
                # Web fetcher continues the chain (outputs FileEntity)
                current_node = next_node
            else:
                # Regular transformers (like file_chunker) end the chain
                # After a transformer, connect directly to destination
                # (skip parent/chunk entities for UI simplification)
                transformer_to_dest_edge = schemas.DagEdgeCreate(
                    from_node_id=next_node.id, to_node_id=destination_node_create.id
                )
                entity_dag.edges.append(transformer_to_dest_edge)
                break
        elif next_node.type == NodeType.entity:
            # Add entity node and continue following the chain
            next_node_create = convert_to_node_create(next_node)
            entity_dag.nodes.append(next_node_create)
            current_node = next_node
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Node ({next_node.name}) after '{current_node.name}' "
                    f"has unsupported type ({next_node.type})."
                ),
            )


@router.get("/sync/{sync_id}/entity_dags/", response_model=list[schemas.SyncDagCreate])
async def get_sync_entity_dags(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
):
    """Get list of DAGs, one for each entity."""
    dag_model = await sync_dag.get_by_sync_id(db, sync_id=sync_id, current_user=current_user)
    dag = schemas.SyncDag.from_orm(dag_model)

    source_node = dag.get_source_node()
    source_node_create = convert_to_node_create(source_node)

    destination_nodes = dag.get_destination_nodes()
    if not destination_nodes:
        raise HTTPException(status_code=400, detail="No destination nodes found in the DAG")
    else:
        destination_node = destination_nodes[0]
        destination_node_create = convert_to_node_create(destination_node)

    entity_dags = []
    edges_from_source = dag.get_edges_from_node(source_node.id)
    for edge_from_source in edges_from_source:
        edge_from_source_create = convert_to_edge_create(edge_from_source)

        entity_node = dag.get_node(edge_from_source.to_node_id)
        entity_node_create = convert_to_node_create(entity_node)

        entity_dag = schemas.SyncDagCreate(
            name=f"{entity_node.name} DAG",
            description=f"Disparate DAG for the entity {entity_node.name}.",
            sync_id=dag.sync_id,
            nodes=[source_node_create, entity_node_create, destination_node_create],
            edges=[edge_from_source_create],
        )

        _validate_entity_node_edges(dag, entity_node)
        _process_transformer_chain(dag, entity_dag, entity_node, destination_node_create)

        entity_dags.append(entity_dag)

    return entity_dags


@router.post("/sync/{sync_id}/dag/", response_model=schemas.SyncDag)
async def create_sync_dag(
    sync_id: UUID,
    dag: schemas.SyncDagCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
):
    """Create a new DAG definition for a sync."""
    return await sync_dag.create_with_nodes_and_edges(db, obj_in=dag, current_user=current_user)


@router.put("/sync/{sync_id}/dag/", response_model=schemas.SyncDag)
async def update_sync_dag(
    sync_id: UUID,
    dag: schemas.SyncDagUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
):
    """Update a DAG definition for a sync."""
    db_dag = await sync_dag.get_by_sync_id(db, sync_id=sync_id, current_user=current_user)
    if not db_dag:
        raise HTTPException(status_code=404, detail="DAG not found")

    return await sync_dag.update_with_nodes_and_edges(
        db, db_obj=db_dag, obj_in=dag, current_user=current_user
    )


@router.get("/init", response_model=schemas.SyncDag)
async def initialize_dag(
    sync_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_user),
) -> schemas.SyncDag:
    """Initialize a new DAG with source, entities, and destination."""
    dag = await dag_service.create_initial_dag(db, sync_id=sync_id, current_user=current_user)
    return dag


def convert_to_node_create(node: schemas.DagNode) -> schemas.DagNodeCreate:
    """Convert a DagNode to DagNodeCreate."""
    return schemas.DagNodeCreate(
        id=node.id,
        type=node.type,
        name=node.name,
        config=node.config,
        connection_id=node.connection_id,
        entity_definition_id=node.entity_definition_id,
        transformer_id=node.transformer_id,
    )


def convert_to_edge_create(edge: schemas.DagEdge) -> schemas.DagEdgeCreate:
    """Convert a DagEdge to DagEdgeCreate."""
    return schemas.DagEdgeCreate(from_node_id=edge.from_node_id, to_node_id=edge.to_node_id)
