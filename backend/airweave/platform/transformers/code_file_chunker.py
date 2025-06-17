"""Code file chunker."""

import os
from copy import deepcopy
from typing import List

from chonkie import CodeChunker, SemanticChunker

from airweave.core.logging import logger
from airweave.platform.decorators import transformer
from airweave.platform.entities._base import CodeFileEntity
from airweave.platform.transformers.utils import (
    MAX_CHUNK_SIZE,
    METADATA_SIZE,
    count_tokens,
)

# Module-level shared chunkers
_shared_semantic_chunker = None
_shared_code_chunker = None


def get_shared_semantic_chunker(chunk_size_limit: int):
    """Get or create a shared semantic chunker for text files."""
    global _shared_semantic_chunker
    if _shared_semantic_chunker is None or _shared_semantic_chunker.chunk_size != chunk_size_limit:
        _shared_semantic_chunker = SemanticChunker(
            tokenizer_or_token_counter=count_tokens,
            chunk_size=chunk_size_limit,
            min_sentences=1,
            threshold=0.5,
            mode="window",
            similarity_window=2,
        )
    return _shared_semantic_chunker


def get_shared_code_chunker(chunk_size_limit: int):
    """Get or create a shared code chunker."""
    global _shared_code_chunker
    if _shared_code_chunker is None or _shared_code_chunker.chunk_size != chunk_size_limit:
        _shared_code_chunker = CodeChunker(
            tokenizer_or_token_counter=count_tokens,
            chunk_size=chunk_size_limit,
        )
    return _shared_code_chunker


@transformer(name="Code File Chunker")
async def code_file_chunker(file: CodeFileEntity) -> List[CodeFileEntity]:
    """Chunk a code file.

    This transformer:
    1. Takes a CodeFileEntity as input
    2. Uses Chonkie to chunk the code file if content size is greater than chunk limit
    3. Yields each chunk as a CodeFileEntity

    Args:
        file: The CodeFileEntity to process

    Returns:
        List[CodeFileEntity]: The processed chunks
    """
    logger.info(f"Starting code file chunker for file: {file.name} (file_id: {file.file_id})")

    # If file.content is None, return empty list
    if file.content is None:
        logger.warning(f"File content is None for {file.name}, returning empty list")
        return []

    # Count tokens in just the content (not the entire entity)
    content_token_count = count_tokens(file.content)
    chunk_size_limit = MAX_CHUNK_SIZE - METADATA_SIZE  # Leave room for metadata
    logger.info(
        f"File {file.name} content has {content_token_count} tokens, "
        f"chunk limit is {chunk_size_limit}"
    )

    # If the content is small enough to fit in one chunk, return it as is
    if content_token_count <= chunk_size_limit:
        logger.info(
            f"File {file.name} content is small enough ({content_token_count} tokens), "
            f"no chunking needed"
        )
        return [file]

    # Check if this is a text file by extension
    file_extension = os.path.splitext(file.name)[1].lower().lstrip(".")
    is_text_file = file_extension in ["txt", "text", "csv"]
    logger.info(f"File {file.name} has extension {file_extension}, is_text_file={is_text_file}")

    if is_text_file:
        logger.info(f"Using semantic chunker for text file {file.name}")
        semantic_chunker = get_shared_semantic_chunker(chunk_size_limit)  # Use shared
        chunks = semantic_chunker.chunk(file.content)
        logger.debug(f"Semantic chunker produced {len(chunks)} chunks")
    else:
        logger.info(f"Using code chunker for code file {file.name}")
        code_chunker = get_shared_code_chunker(chunk_size_limit)  # Use shared
        chunks = code_chunker.chunk(file.content)
        logger.debug(f"Code chunker produced {len(chunks)} chunks")

    if not chunks:  # If chunking failed or returned empty, return original
        logger.warning(
            f"Chunking failed or returned empty for {file.name}, returning original file"
        )
        return [file]

    # Create a new CodeFileEntity for each chunk
    chunked_files = []
    total_chunks = len(chunks)
    logger.info(f"Creating {total_chunks} chunked entities for {file.name}")

    for idx, chunk in enumerate(chunks):
        # Create a deep copy of the original file
        chunked_file = deepcopy(file)

        # Update the content with just this chunk
        chunked_file.content = chunk.text
        chunk_token_count = count_tokens(chunked_file.content)

        logger.debug(
            f"Chunk {idx + 1}/{total_chunks} for {file.name}: {chunk_token_count} tokens, "
            f"span: {chunk.start_index}-{chunk.end_index}"
        )

        # Add chunk metadata to entity metadata
        if chunked_file.metadata is None:
            chunked_file.metadata = {}

        chunked_file.metadata.update(
            {
                "chunk_index": idx + 1,
                "total_chunks": total_chunks,
                "original_file_id": file.file_id,
                "chunk_start_index": chunk.start_index,
                "chunk_end_index": chunk.end_index,
            }
        )

        # Update name to indicate it's a chunk
        chunked_file.name = f"{file.name} (Chunk {idx + 1}/{total_chunks})"

        chunked_files.append(chunked_file)

    logger.info(f"Completed chunking {file.name} into {len(chunked_files)} chunks")
    return chunked_files
