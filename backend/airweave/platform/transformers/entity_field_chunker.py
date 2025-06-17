"""Entity chunker for chunking large text fields in entities."""

import json
from typing import Any, Dict, List, Tuple

from chonkie import RecursiveChunker, RecursiveLevel, RecursiveRules, TokenChunker

from airweave.core.logging import logger
from airweave.platform.decorators import transformer
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sync.async_helpers import run_in_thread_pool
from airweave.platform.transformers.utils import (
    count_tokens,
)

# Fields that should never be chunked (system fields)
NON_CHUNKABLE_FIELDS = {
    "entity_id",
    "breadcrumbs",
    "db_entity_id",
    "source_name",
    "sync_id",
    "sync_job_id",
    "url",
    "sync_metadata",
    "parent_entity_id",
    "vector",
    "chunk_index",
}

# Cache for chunkers
_token_chunker_cache = {}
_recursive_chunker = None

# Safe chunk size for entities considering JSON overhead
# OpenAI's limit is 8191, but we need to account for:
# 1. JSON stringification overhead (~20-30%)
# 2. Other entity fields
# 3. Safety margin
SAFE_ENTITY_SIZE = 5000  # Conservative limit to ensure we stay under 8191


def get_token_chunker(chunk_size: int) -> TokenChunker:
    """Get or create a token chunker with the specified chunk size.

    Args:
        chunk_size: Target size for each chunk

    Returns:
        Configured TokenChunker
    """
    global _token_chunker_cache

    if chunk_size not in _token_chunker_cache:
        _token_chunker_cache[chunk_size] = TokenChunker(
            tokenizer=count_tokens,  # Fixed: API changed from tokenizer_or_token_counter
            chunk_size=chunk_size,
            chunk_overlap=100,  # Small overlap for context
        )

    return _token_chunker_cache[chunk_size]


def get_recursive_chunker(chunk_size: int) -> RecursiveChunker:
    """Get or create a recursive chunker optimized for text fields.

    Args:
        chunk_size: Target size for each chunk

    Returns:
        Configured RecursiveChunker
    """
    # Simpler rules optimized for general text content
    rules = RecursiveRules(
        [
            RecursiveLevel(delimiters=["\n\n\n"], include_delim="next"),
            RecursiveLevel(delimiters=["\n\n"], include_delim="next"),
            RecursiveLevel(delimiters=["\n"], include_delim="next"),
            RecursiveLevel(delimiters=[". ", "! ", "? "], include_delim="prev"),
            RecursiveLevel(delimiters=[", "], include_delim="prev"),
        ]
    )

    return RecursiveChunker(
        tokenizer_or_token_counter=count_tokens,
        chunk_size=chunk_size,
        rules=rules,
        min_characters_per_chunk=50,
    )


def calculate_entity_string_size(entity: BaseEntity) -> int:
    """Calculate the actual token size when entity is converted to string for embedding.

    This mimics what happens in entity_processor.py:
    str(entity.to_storage_dict())
    """
    # Get the storage dict and convert to string (same as in entity_processor)
    storage_dict = entity.to_storage_dict()
    entity_string = str(storage_dict)
    return count_tokens(entity_string)


def calculate_entity_size(entity_dict: Dict[str, Any]) -> Tuple[int, Dict[str, int]]:
    """Calculate the token size of entity and its fields."""
    total_size = 0
    field_sizes = {}

    for field_name, field_value in entity_dict.items():
        if isinstance(field_value, str):
            size = count_tokens(field_value)
        elif isinstance(field_value, (dict, list)):
            # For complex types, serialize to JSON to count tokens
            size = count_tokens(json.dumps(field_value))
        else:
            # For other types, convert to string
            size = count_tokens(str(field_value))

        field_sizes[field_name] = size
        total_size += size

    return total_size, field_sizes


def find_field_to_chunk(entity_dict: Dict, field_sizes: Dict[str, int]) -> Tuple[str, int]:
    """Find the largest chunkable field that contributes most to entity size.

    Args:
        entity_dict: Entity dictionary
        field_sizes: Dictionary of field sizes

    Returns:
        Tuple of (field_name, field_size)
    """
    largest_field = None
    largest_field_size = 0

    for field_name, field_size in field_sizes.items():
        if (
            field_name not in NON_CHUNKABLE_FIELDS
            and isinstance(entity_dict[field_name], str)
            and field_size > largest_field_size
        ):
            largest_field = field_name
            largest_field_size = field_size

    return largest_field, largest_field_size


def _clean_text_for_chunking(text: str) -> str:
    """Clean text by removing problematic Unicode characters."""
    zero_width_chars = [
        "\u200b",  # Zero-width space
        "\u200c",  # Zero-width non-joiner
        "\u200d",  # Zero-width joiner
        "\u200e",  # Left-to-right mark
        "\u200f",  # Right-to-left mark
        "\ufeff",  # Zero-width no-break space
        "\u00a0",  # Non-breaking space (replace with regular space)
    ]

    cleaned_text = text
    for char in zero_width_chars:
        if char in cleaned_text:
            count = cleaned_text.count(char)
            if count > 10:  # Only log if significant
                logger.debug(f"Removing {count} instances of Unicode {ord(char):04X} from text")
            # Replace non-breaking space with regular space instead of removing
            if char == "\u00a0":
                cleaned_text = cleaned_text.replace(char, " ")
            else:
                cleaned_text = cleaned_text.replace(char, "")

    # Also collapse multiple spaces into single space
    import re

    cleaned_text = re.sub(r"\s+", " ", cleaned_text)
    return cleaned_text


def _create_truncated_chunk(chunk, target_chunk_size: int):
    """Create a truncated chunk when original is too large."""
    max_chars = int(len(chunk.text) * target_chunk_size / count_tokens(chunk.text))
    truncated_text = chunk.text[:max_chars]

    # Create a simple chunk-like object with truncated text
    class SimpleChunk:
        def __init__(self, text):
            self.text = text
            self.start_index = 0
            self.end_index = len(text)

    return SimpleChunk(truncated_text)


def _validate_chunks(chunk_result, target_chunk_size: int) -> List[Any]:
    """Post-process chunks to ensure none are too large."""
    validated_chunks = []
    for chunk in chunk_result:
        chunk_size = count_tokens(chunk.text)
        if chunk_size > target_chunk_size * 1.2:  # Allow 20% margin
            logger.warning(
                f"Chunk exceeded target size ({chunk_size} > {target_chunk_size * 1.2}). "
                f"Will truncate to fit."
            )
            truncated_chunk = _create_truncated_chunk(chunk, target_chunk_size)
            validated_chunks.append(truncated_chunk)
        else:
            validated_chunks.append(chunk)
    return validated_chunks


async def chunk_text_optimized(
    text: str, target_chunk_size: int, field_name: str, entity_id: str
) -> List[Any]:
    """Chunk text using optimized token-based approach without embeddings.

    Args:
        text: Text to chunk
        target_chunk_size: Target size for each chunk
        field_name: Name of the field being chunked
        entity_id: Entity ID for logging

    Returns:
        List of chunks
    """
    # Clean text
    cleaned_text = _clean_text_for_chunking(text)
    text_size = count_tokens(cleaned_text)

    logger.info(
        f"Starting optimized chunking for field '{field_name}' in entity {entity_id} "
        f"(size: {text_size} tokens after cleaning, target chunk size: {target_chunk_size})"
    )

    # First try recursive chunking which respects text structure
    recursive_chunker = get_recursive_chunker(target_chunk_size)

    def _chunk_recursive(text: str):
        try:
            chunks = recursive_chunker.chunk(text)
            return chunks
        except Exception as e:
            logger.warning(
                f"Recursive chunking failed for field '{field_name}' in entity {entity_id}: "
                f"{str(e)}. Falling back to token chunking."
            )
            return None

    chunk_result = await run_in_thread_pool(_chunk_recursive, cleaned_text)

    if chunk_result is None:
        # Fallback to simple token chunking
        logger.info(
            f"Using token chunker as fallback for field '{field_name}' in entity {entity_id}"
        )
        token_chunker = get_token_chunker(target_chunk_size)

        def _chunk_tokens(text: str):
            return token_chunker.chunk(text)

        chunk_result = await run_in_thread_pool(_chunk_tokens, cleaned_text)

    # Post-process chunks to ensure none are too large
    validated_chunks = _validate_chunks(chunk_result, target_chunk_size)

    logger.info(
        f"Chunking complete: {len(chunk_result)} original chunks → "
        f"{len(validated_chunks)} validated chunks"
    )

    return validated_chunks


@transformer(name="Entity Chunker")
async def entity_chunker(entity: BaseEntity) -> List[BaseEntity]:
    """Chunk large text fields in an entity using optimized token-based chunking.

    This transformer ensures the stringified entity stays under the embedding model's
    token limit by:
    1. Calculating the actual stringified entity size (not just field sizes)
    2. Finding the largest field to chunk if needed
    3. Using token-based chunking (no embeddings) to avoid API limits
    4. Creating chunks small enough that the full stringified entity stays under limits

    Args:
        entity: The BaseEntity to process

    Returns:
        List[BaseEntity]: Multiple copies of the entity with chunks of the large field
    """
    # Skip if already chunked
    if getattr(entity, "chunk_index", None) is not None:
        return [entity]

    # Calculate the actual stringified size
    stringified_size = calculate_entity_string_size(entity)

    logger.info(
        f"Entity {entity.entity_id} stringified size: {stringified_size} tokens "
        f"(limit: {SAFE_ENTITY_SIZE})"
    )

    # If entity is small enough, return as is
    if stringified_size <= SAFE_ENTITY_SIZE:
        return [entity]

    # Get entity data and calculate field sizes
    entity_dict = entity.model_dump()
    total_size, field_sizes = calculate_entity_size(entity_dict)

    # Find the largest field to chunk
    largest_field, largest_field_size = find_field_to_chunk(entity_dict, field_sizes)

    # If no suitable field found, log warning and return original
    if not largest_field:
        logger.warning(
            f"Entity {entity.entity_id} exceeds safe size "
            f"({stringified_size} > {SAFE_ENTITY_SIZE}), but no suitable field found for chunking. "
            f"Returning as-is, may cause embedding errors."
        )
        return [entity]

    logger.info(
        f"Chunking entity {entity.entity_id} (stringified size: {stringified_size}) "
        f"using field '{largest_field}' (size: {largest_field_size})"
    )

    # Calculate a very conservative target chunk size
    # We need to account for:
    # 1. JSON overhead (can be 30-50% more)
    # 2. All other fields in the entity
    # 3. Safety margin

    # Estimate the overhead from other fields and JSON formatting
    base_overhead = stringified_size - largest_field_size

    # For Gmail entities with lots of fields, be extra conservative
    entity_type = type(entity).__name__
    if "Gmail" in entity_type:
        json_overhead_factor = 2.5  # Gmail entities have MASSIVE overhead due to many fields
        safety_limit = 3500  # Even more conservative for Gmail
        # For very large Gmail entities, be even more aggressive
        if stringified_size > 15000:
            json_overhead_factor = 3.0
            safety_limit = 3000
    else:
        json_overhead_factor = 1.5  # Assume 50% overhead for JSON formatting
        safety_limit = SAFE_ENTITY_SIZE

    # Calculate target chunk size to ensure final stringified entity < safety_limit
    target_chunk_size = int((safety_limit - base_overhead) / json_overhead_factor)

    # Ensure we have a reasonable minimum chunk size but cap maximum
    target_chunk_size = max(300, min(target_chunk_size, 2000))  # Cap at 2000 tokens

    logger.info(
        f"Calculated target chunk size: {target_chunk_size} "
        f"(base overhead: {base_overhead}, with JSON factor: {json_overhead_factor})"
    )

    # Chunk the text using optimized approach (no embeddings)
    chunks = await chunk_text_optimized(
        entity_dict[largest_field], target_chunk_size, largest_field, entity.entity_id
    )

    # Create a copy of the entity for each chunk
    chunked_entities = []
    entity_class = type(entity)
    oversized_chunks = []

    for i, chunk in enumerate(chunks):
        # Create a new entity with the chunked field
        # IMPORTANT: Create a unique entity_id for each chunk to avoid database conflicts
        chunked_entity_data = {
            **entity_dict,
            largest_field: chunk.text,
            "chunk_index": i,
            # Append chunk index to create unique entity_id
            "entity_id": f"{entity.entity_id}_chunk_{i}",
        }
        chunked_entity = entity_class(**chunked_entity_data)

        # Verify the chunk size
        chunk_stringified_size = calculate_entity_string_size(chunked_entity)

        if chunk_stringified_size > 7500:  # More conservative limit
            logger.error(
                f"🚨 OVERSIZED CHUNK: Chunk {i} of entity {entity.entity_id} is "
                f"{chunk_stringified_size} tokens! (limit: 8191). Chunk text length: "
                f"{len(chunk.text)} chars"
            )
            oversized_chunks.append((i, chunk.text, chunk_stringified_size))

            # Force a smaller chunk by truncating
            max_chars = int(
                len(chunk.text) * 7000 / chunk_stringified_size
            )  # Scale down proportionally
            truncated_text = chunk.text[:max_chars]
            logger.warning(f"Truncating chunk {i} from {len(chunk.text)} to {max_chars} chars")

            # Re-create with truncated text
            chunked_entity_data = {**entity_dict, largest_field: truncated_text, "chunk_index": i}
            chunked_entity = entity_class(**chunked_entity_data)

            # Verify again
            new_size = calculate_entity_string_size(chunked_entity)
            logger.info(f"After truncation, chunk {i} is now {new_size} tokens")

        chunked_entities.append(chunked_entity)

    # Log final chunk information
    chunk_sizes = [calculate_entity_string_size(e) for e in chunked_entities]
    logger.info(
        f"Created {len(chunks)} chunks for entity {entity.entity_id} with stringified sizes: "
        f"{', '.join(str(size) for size in chunk_sizes)}"
    )

    if oversized_chunks:
        logger.error(
            f"⚠️ Entity {entity.entity_id} had {len(oversized_chunks)} oversized chunks "
            f"that required truncation. This suggests the chunker is not handling "
            f"the content properly."
        )

    return chunked_entities
