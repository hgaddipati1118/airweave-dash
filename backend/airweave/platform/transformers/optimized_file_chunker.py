"""Optimized file chunker with faster semantic chunking."""

import asyncio
import os
from typing import List

from chonkie import RecursiveChunker, TokenChunker

from airweave.core.logging import logger
from airweave.platform.decorators import transformer
from airweave.platform.entities._base import ChunkEntity, FileEntity, ParentEntity
from airweave.platform.file_handling.conversion.factory import document_converter
from airweave.platform.sync.async_helpers import run_in_thread_pool
from airweave.platform.transformers.utils import (
    MARGIN_OF_ERROR,
    MAX_CHUNK_SIZE,
    METADATA_SIZE,
    count_tokens,
)

# Create optimized chunkers at module level
_token_chunker = None
_recursive_chunker = None

# Calculate safe chunk size accounting for metadata overhead
SAFE_CHUNK_SIZE = MAX_CHUNK_SIZE - METADATA_SIZE - MARGIN_OF_ERROR  # 8191 - 1200 - 250 = 6741


def get_token_chunker(max_chunk_size: int = SAFE_CHUNK_SIZE):
    """Get or create a token chunker."""
    global _token_chunker
    if _token_chunker is None or _token_chunker.chunk_size != max_chunk_size:
        _token_chunker = TokenChunker(
            tokenizer_or_token_counter=count_tokens,
            chunk_size=max_chunk_size,
            chunk_overlap=100,  # Small overlap for context
        )
    return _token_chunker


def get_recursive_chunker():
    """Get or create a recursive chunker optimized for speed."""
    global _recursive_chunker
    if _recursive_chunker is None:
        from chonkie import RecursiveLevel, RecursiveRules

        # Simpler rules for faster processing
        rules = RecursiveRules(
            [
                RecursiveLevel(delimiters=["\n\n\n"], include_delim="next"),
                RecursiveLevel(delimiters=["\n\n"], include_delim="next"),
                RecursiveLevel(delimiters=["\n"], include_delim="next"),
                RecursiveLevel(delimiters=[". ", "! ", "? "], include_delim="prev"),
            ]
        )

        _recursive_chunker = RecursiveChunker(
            tokenizer_or_token_counter=count_tokens,
            chunk_size=SAFE_CHUNK_SIZE,
            rules=rules,
            min_characters_per_chunk=100,
        )
    return _recursive_chunker


async def _process_file_content(file: FileEntity, entity_context: str) -> str:
    """Process file content and convert to text if needed."""
    if not file.local_path:
        logger.error(f"📂 CHUNKER_NO_PATH [{entity_context}] File has no local path")
        return ""

    _, extension = os.path.splitext(file.local_path)
    extension = extension.lower()

    if extension == ".md":
        logger.info(f"📑 CHUNKER_READ_MD [{entity_context}] Reading markdown file directly")
        import aiofiles

        async with aiofiles.open(file.local_path, "r", encoding="utf-8") as f:
            content = await f.read()
        logger.info(f"📖 CHUNKER_READ_DONE [{entity_context}] Read {len(content)} characters")
        return content
    else:
        logger.info(f"🔄 CHUNKER_CONVERT [{entity_context}] Converting file to markdown")
        result = await document_converter.convert(file.local_path)
        if not result or not result.text_content:
            logger.warning(f"🚫 CHUNKER_CONVERT_EMPTY [{entity_context}] No content extracted")
            return ""
        logger.info(
            f"✅ CHUNKER_CONVERT_DONE [{entity_context}] "
            f"Converted to {len(result.text_content)} characters"
        )
        return result.text_content


async def _chunk_text_optimized(text_content: str, entity_context: str) -> List[str]:
    """Optimized chunking using token-based approach for speed."""
    logger.info(f"🔧 CHUNKER_OPTIMIZED_START [{entity_context}] Starting optimized chunking")

    # First try recursive chunking
    recursive_chunker = get_recursive_chunker()

    def _chunk_recursive(text: str):
        try:
            chunks = recursive_chunker.chunk(text)
            return [(chunk.text, chunk.token_count) for chunk in chunks]
        except Exception as e:
            logger.warning(
                f"⚠️  CHUNKER_RECURSIVE_FAIL [{entity_context}] Recursive chunking failed: {str(e)}"
            )
            return None

    chunk_result = await run_in_thread_pool(_chunk_recursive, text_content)

    if chunk_result is None:
        # Fallback to simple token chunking
        logger.info(f"🔄 CHUNKER_FALLBACK [{entity_context}] Using token chunker as fallback")
        token_chunker = get_token_chunker()

        def _chunk_tokens(text: str):
            chunks = token_chunker.chunk(text)
            return [(chunk.text, chunk.token_count) for chunk in chunks]

        chunk_result = await run_in_thread_pool(_chunk_tokens, text_content)

    # Extract just the text from results
    final_chunks = [text for text, _ in chunk_result]

    logger.info(f"📦 CHUNKER_OPTIMIZED_DONE [{entity_context}] Created {len(final_chunks)} chunks")
    return final_chunks


@transformer(name="Optimized File Chunker")
async def optimized_file_chunker(file: FileEntity) -> list[ParentEntity | ChunkEntity]:
    """Optimized file chunker that uses faster chunking strategies.

    This transformer:
    1. Takes a FileEntity as input
    2. Converts the file to text content
    3. Uses token-based chunking for speed (no embeddings)
    4. Falls back to simple chunking if needed
    5. Returns parent and chunk entities
    6. Cleans up temporary files after processing

    Args:
        file: The FileEntity to process

    Returns:
        list[ParentEntity | ChunkEntity]: The processed chunks
    """
    entity_context = f"Entity({file.entity_id})"

    logger.info(
        f"📄 CHUNKER_START [{entity_context}] Starting optimized file chunking for: {file.name} "
        f"(type: {type(file).__name__})"
    )

    file_class = type(file)
    produced_entities = []

    FileParentClass, FileChunkClass = file_class.create_parent_chunk_models()

    try:
        # Process file content
        logger.info(f"🔍 CHUNKER_PROCESS [{entity_context}] Processing file content")
        start_time = asyncio.get_event_loop().time()

        text_content = await _process_file_content(file, entity_context)

        process_elapsed = asyncio.get_event_loop().time() - start_time

        if not text_content or not text_content.strip():
            logger.warning(f"📭 CHUNKER_EMPTY [{entity_context}] No text content found")
            return []

        content_length = len(text_content)
        logger.info(
            f"📊 CHUNKER_CONTENT [{entity_context}] Processed {content_length} characters "
            f"in {process_elapsed:.2f}s"
        )

        # Chunk the content
        logger.info(f"✂️  CHUNKER_SPLIT_START [{entity_context}] Starting text chunking")
        chunk_start = asyncio.get_event_loop().time()

        final_chunk_texts = await _chunk_text_optimized(text_content, entity_context)

        chunk_elapsed = asyncio.get_event_loop().time() - chunk_start
        logger.info(
            f"📦 CHUNKER_SPLIT_DONE [{entity_context}] Created {len(final_chunk_texts)} chunks "
            f"in {chunk_elapsed:.2f}s"
        )

        # Create entities
        logger.info(
            f"🏗️  CHUNKER_ENTITIES_START [{entity_context}] Creating parent and chunk entities"
        )

        # Create parent entity for the file using all fields from original entity
        file_data = file.model_dump()
        file_data.update(
            {
                "number_of_chunks": len(final_chunk_texts),
            }
        )
        parent = FileParentClass(**file_data)
        produced_entities.append(parent)

        for i, chunk_text in enumerate(final_chunk_texts):
            if not chunk_text.strip():
                continue

            chunk = FileChunkClass(
                name=f"{file.name} - Chunk {i + 1}",
                entity_id=file.entity_id,
                sync_id=file.sync_id,
                parent_entity_id=parent.entity_id,
                parent_db_entity_id=parent.db_entity_id,
                md_content=chunk_text,
                md_type="text",
                md_position=i,
                md_parent_title=file.name,
                metadata={
                    "chunk_index": i,
                    "total_chunks": len(final_chunk_texts),
                },
            )
            produced_entities.append(chunk)

        total_elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(
            f"✅ CHUNKER_COMPLETE [{entity_context}] Chunking completed in {total_elapsed:.2f}s "
            f"(1 parent + {len(final_chunk_texts)} chunks)"
        )

        # Mark entity as fully processed in storage
        if file.sync_id:
            from airweave.platform.storage import storage_manager

            # Check if this is a CTTI entity - they don't need marking as processed
            # since they use global deduplication in the aactmarkdowns container
            if not storage_manager._is_ctti_entity(file):
                await storage_manager.mark_entity_processed(
                    file.sync_id, file.entity_id, len(final_chunk_texts)
                )
                logger.info(
                    f"📝 CHUNKER_MARKED_PROCESSED [{entity_context}] "
                    f"Marked entity as fully processed with {len(final_chunk_texts)} chunks"
                )
            else:
                logger.info(
                    f"🏥 CHUNKER_CTTI_SKIP_MARK [{entity_context}] "
                    f"Skipping mark_processed for CTTI entity (uses global deduplication)"
                )

    except Exception as e:
        logger.error(
            f"💥 CHUNKER_ERROR [{entity_context}] Chunking failed: {type(e).__name__}: {str(e)}"
        )
        raise e
    finally:
        # Clean up temporary file if it exists
        if hasattr(file, "local_path") and file.local_path:
            from airweave.platform.storage import storage_manager

            await storage_manager.cleanup_temp_file(file.local_path)
            logger.info(
                f"🧹 CHUNKER_CLEANUP [{entity_context}] Cleaned up temp file: {file.local_path}"
            )

    return produced_entities
