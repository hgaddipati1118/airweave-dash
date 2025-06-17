"""Lazy entity pattern for deferring expensive operations to workers."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, TypeVar

from airweave.core.logging import logger
from airweave.platform.entities._base import BaseEntity

T = TypeVar("T", bound=BaseEntity)


@dataclass
class LazyOperation:
    """Represents a deferred operation to be executed later."""

    name: str
    func: Callable
    args: tuple = ()
    kwargs: dict = None

    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


class LazyEntity(BaseEntity, ABC):
    """Base class for entities that defer expensive operations.

    This pattern allows sources to yield entities quickly without blocking
    on API calls or other expensive operations. The operations are executed
    later by workers during the enrichment phase.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lazy_operations: Dict[str, LazyOperation] = {}
        self._lazy_results: Dict[str, Any] = {}
        self._is_materialized = False

    def add_lazy_operation(self, name: str, func: Callable, *args, **kwargs) -> None:
        """Add a deferred operation to be executed later.

        Args:
            name: Unique name for this operation
            func: Async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        """
        self._lazy_operations[name] = LazyOperation(name=name, func=func, args=args, kwargs=kwargs)

    async def materialize(self) -> None:
        """Execute all deferred operations and populate the entity.

        This method is called by workers during the enrichment phase.
        """
        if self._is_materialized:
            return

        logger.info(
            f"🔄 LAZY_MATERIALIZE Starting materialization for {self.__class__.__name__} "
            f"{self.entity_id} with {len(self._lazy_operations)} operations"
        )

        # Execute all operations concurrently
        tasks = []
        for op_name, operation in self._lazy_operations.items():
            task = self._execute_operation(op_name, operation)
            tasks.append(task)

        # Wait for all operations to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    op_name = list(self._lazy_operations.keys())[i]
                    logger.error(
                        f"❌ LAZY_ERROR Operation '{op_name}' failed for entity "
                        f"{self.entity_id}: {result}"
                    )
                    raise result

        # Apply results to entity
        await self._apply_results()
        self._is_materialized = True

        logger.info(
            f"✅ LAZY_COMPLETE Materialization complete for {self.__class__.__name__} "
            f"{self.entity_id}"
        )

    async def _execute_operation(self, name: str, operation: LazyOperation) -> Any:
        """Execute a single deferred operation."""
        logger.debug(f"🔧 LAZY_EXECUTE Executing operation '{name}' for entity {self.entity_id}")

        start_time = asyncio.get_event_loop().time()
        result = await operation.func(*operation.args, **operation.kwargs)
        elapsed = asyncio.get_event_loop().time() - start_time

        self._lazy_results[name] = result

        logger.debug(
            f"⏱️  LAZY_TIMING Operation '{name}' completed in {elapsed:.2f}s "
            f"for entity {self.entity_id}"
        )

        return result

    @abstractmethod
    async def _apply_results(self) -> None:
        """Apply the results of lazy operations to populate entity fields.

        This method should be implemented by subclasses to map operation
        results to entity attributes.
        """
        pass

    @property
    def is_lazy(self) -> bool:
        """Check if this entity has deferred operations."""
        return bool(self._lazy_operations) and not self._is_materialized

    @property
    def needs_materialization(self) -> bool:
        """Check if this entity needs to be materialized."""
        return self.is_lazy


class LazyLoadMixin:
    """Mixin for sources that want to use lazy loading pattern."""

    def create_lazy_entity(
        self,
        entity_class: type[T],
        immediate_data: Dict[str, Any],
        lazy_operations: Dict[str, tuple[Callable, tuple, dict]] = None,
    ) -> T:
        """Create a lazy entity with immediate data and deferred operations.

        Args:
            entity_class: The entity class to instantiate
            immediate_data: Data available immediately (no API calls)
            lazy_operations: Dict of operation_name -> (func, args, kwargs)

        Returns:
            Lazy entity instance
        """
        # Create entity with immediate data
        entity = entity_class(**immediate_data)

        # Add lazy operations if entity supports it
        if isinstance(entity, LazyEntity) and lazy_operations:
            for op_name, (func, args, kwargs) in lazy_operations.items():
                entity.add_lazy_operation(op_name, func, *args, **kwargs)

        return entity
