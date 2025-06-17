"""Simplified OpenAI text2vec model for embedding using official OpenAI client."""

import asyncio
from typing import List, Optional

from openai import AsyncOpenAI
from pydantic import Field

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import embedding_model

from ._base import BaseEmbeddingModel

# Global semaphore for OpenAI API rate limiting
_openai_semaphore: Optional[asyncio.Semaphore] = None


@embedding_model(
    "OpenAI Text2Vec Simple",
    "openai_text2vec_simple",
    "openai",
    AuthType.config_class,
    "OpenAIAuthConfig",
)
class OpenAIText2Vec(BaseEmbeddingModel):
    """Simplified OpenAI text2vec model configuration for embedding using official OpenAI client."""

    model_name: str = "openai-text2vec-simple"
    api_key: str = Field(..., description="OpenAI API key")
    vector_dimensions: int = 1536
    enabled: bool = True
    embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model name"
    )

    def __init__(self, **kwargs):
        """Initialize the OpenAI Text2Vec model with a shared client."""
        super().__init__(**kwargs)

        # Create a single shared client with extended timeout for high concurrency
        # Default is 10 minutes, but we extend it for reliability with 100 concurrent workers
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            timeout=1200.0,  # 20 minutes total timeout (was 10 minutes default)
            max_retries=2,  # Retry on transient errors
        )
        logger.info("Created shared OpenAI client with 20 minute timeout")

        # Initialize rate limiting semaphore (limit concurrent OpenAI requests)
        global _openai_semaphore
        if _openai_semaphore is None:
            # Limit concurrent OpenAI requests to prevent API overload
            max_concurrent = getattr(settings, "OPENAI_MAX_CONCURRENT", 20)
            _openai_semaphore = asyncio.Semaphore(max_concurrent)
            logger.info(f"Initialized OpenAI rate limiting to {max_concurrent} concurrent requests")

    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
        entity_context: Optional[str] = None,
    ) -> List[float]:
        """Embed a single text string using OpenAI official client.

        Args:
            text: The text to embed
            model: The OpenAI model to use (defaults to self.embedding_model)
            encoding_format: Format of the embedding (default: float)
            dimensions: Vector dimensions (defaults to self.vector_dimensions)
            entity_context: Optional context string for entity identification in logs

        Returns:
            List of embedding values
        """
        if dimensions:
            raise ValueError("Dimensions override not supported for OpenAI embedding")

        context_prefix = f"{entity_context} " if entity_context else ""

        if not text.strip():
            logger.info(f"{context_prefix}Empty text provided for embedding, returning zero vector")
            return [0.0] * self.vector_dimensions

        used_model = model or self.embedding_model
        logger.info(
            f"{context_prefix}Embedding single text with model {used_model} "
            f"(text length: {len(text)})"
        )

        loop = asyncio.get_event_loop()
        cpu_start = loop.time()
        try:
            # Wait for the API call to complete with await
            response = await self._client.embeddings.create(
                input=text,
                model=used_model,
                encoding_format=encoding_format,
            )

            embedding = response.data[0].embedding
            cpu_elapsed = loop.time() - cpu_start
            logger.info(
                f"{context_prefix}Embedding completed in {cpu_elapsed:.2f}s, "
                f"vector size: {len(embedding)}"
            )
            return embedding

        except Exception as e:
            cpu_elapsed = loop.time() - cpu_start
            error_type = type(e).__name__
            logger.error(
                f"{context_prefix}Embedding failed after {cpu_elapsed:.2f}s "
                f"with {error_type}: {str(e)}"
            )
            raise

    async def embed_many(
        self,
        texts: List[str],
        model: Optional[str] = None,
        encoding_format: str = "float",
        dimensions: Optional[int] = None,
        entity_context: Optional[str] = None,
    ) -> List[List[float]]:
        """Embed multiple text strings using OpenAI official client."""
        if dimensions:
            raise ValueError("Dimensions override not supported for OpenAI embedding")

        context_prefix = f"{entity_context} " if entity_context else ""

        if not texts:
            logger.info(f"📭 OPENAI_EMPTY [{context_prefix}] Empty texts list provided")
            return []

        logger.info(
            f"🤖 OPENAI_START [{context_prefix}] Starting batch embedding for {len(texts)} texts"
        )

        # Filter empty texts and track indices
        filtered_result = self._filter_empty_texts(texts, context_prefix)
        filtered_texts, empty_indices = filtered_result

        if not filtered_texts:
            logger.info(f"📭 OPENAI_ALL_EMPTY [{context_prefix}] All texts were empty")
            return [[0.0] * self.vector_dimensions] * len(texts)

        self._log_processing_stats(filtered_texts, empty_indices, context_prefix)

        used_model = model or self.embedding_model
        embeddings = await self._process_embeddings_in_batches(
            filtered_texts, used_model, encoding_format, context_prefix
        )

        # Reinsert empty vectors at the correct positions
        return self._reinsert_empty_vectors(embeddings, empty_indices, len(texts))

    def _filter_empty_texts(self, texts: List[str], context_prefix: str) -> tuple[List[str], set]:
        """Filter out empty texts and return filtered list and empty indices."""
        filtered_texts = []
        empty_indices = set()
        total_chars = 0

        for i, text in enumerate(texts):
            if text.strip():
                filtered_texts.append(text)
                total_chars += len(text)
            else:
                empty_indices.add(i)

        return filtered_texts, empty_indices

    def _log_processing_stats(
        self, filtered_texts: List[str], empty_indices: set, context_prefix: str
    ):
        """Log statistics about texts being processed."""
        total_chars = sum(len(text) for text in filtered_texts)
        avg_chars = total_chars / len(filtered_texts) if filtered_texts else 0

        logger.info(
            f"📊 OPENAI_STATS [{context_prefix}] Processing {len(filtered_texts)} non-empty texts "
            f"(skipped {len(empty_indices)} empty, avg chars: {avg_chars:.0f})"
        )

    async def _process_embeddings_in_batches(
        self, texts: List[str], model: str, encoding_format: str, context_prefix: str
    ) -> List[List[float]]:
        """Process embeddings in optimized batches."""
        loop = asyncio.get_event_loop()
        cpu_start = loop.time()

        # Process in batches to avoid API limits
        # OpenAI limits: 8191 tokens per text, 2048 texts per batch, 300k total tokens per request
        MAX_BATCH_SIZE = 100  # Well under the 2048 limit, allows good parallelism
        MAX_TOKENS_PER_BATCH = 280000  # ~93% of 300k limit for safety margin
        MAX_CONCURRENT_BATCHES = 5  # Limit concurrent API calls

        # Prepare batches first
        batches = []
        current_batch = []
        current_batch_tokens = 0

        for text in texts:
            # Estimate tokens (rough: 1 token ≈ 4 chars for English text)
            estimated_tokens = len(text) // 4

            # Check if adding this text would exceed limits
            should_create_new_batch = current_batch and (
                len(current_batch) >= MAX_BATCH_SIZE
                or current_batch_tokens + estimated_tokens > MAX_TOKENS_PER_BATCH
            )

            if should_create_new_batch:
                # Save current batch
                batches.append(current_batch)
                # Start new batch
                current_batch = [text]
                current_batch_tokens = estimated_tokens
            else:
                # Add to current batch
                current_batch.append(text)
                current_batch_tokens += estimated_tokens

        # Don't forget the last batch
        if current_batch:
            batches.append(current_batch)

        logger.info(
            f"📦 OPENAI_BATCHES [{context_prefix}] Created {len(batches)} batches "
            f"from {len(texts)} texts"
        )

        # Process batches in parallel with concurrency limit
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_BATCHES)

        async def process_batch_with_limit(batch, batch_idx):
            async with semaphore:
                logger.info(
                    f"🔄 OPENAI_BATCH_START [{context_prefix}] Processing batch "
                    f"{batch_idx + 1}/{len(batches)} ({len(batch)} texts)"
                )
                return await self._process_single_batch(
                    batch, model, encoding_format, context_prefix
                )

        # Create tasks for all batches
        tasks = [process_batch_with_limit(batch, idx) for idx, batch in enumerate(batches)]

        # Process all batches in parallel
        batch_results = await asyncio.gather(*tasks)

        # Flatten results
        embeddings = []
        for batch_embeddings in batch_results:
            embeddings.extend(batch_embeddings)

        cpu_elapsed = loop.time() - cpu_start
        logger.info(
            f"✅ OPENAI_COMPLETE [{context_prefix}] All {len(batches)} batches completed "
            f"in {cpu_elapsed:.2f}s ({len(embeddings)} vectors returned)"
        )

        return embeddings

    async def _process_single_batch(
        self, batch: List[str], model: str, encoding_format: str, context_prefix: str
    ) -> List[List[float]]:
        """Process a single batch of texts."""
        global _openai_semaphore

        loop = asyncio.get_event_loop()
        batch_start = loop.time()

        try:
            # Use global rate limiter
            async with _openai_semaphore:
                max_concurrent = getattr(settings, "OPENAI_MAX_CONCURRENT", 20)
                logger.info(
                    f"🔗 OPENAI_BATCH_API_CALL [{context_prefix}] "
                    f"Processing batch of {len(batch)} texts "
                    f"(active: {max_concurrent - _openai_semaphore._value}/{max_concurrent})"
                )

                response = await self._client.embeddings.create(
                    input=batch,
                    model=model,
                    encoding_format=encoding_format,
                )

            batch_embeddings = [embedding_data.embedding for embedding_data in response.data]
            batch_elapsed = loop.time() - batch_start

            logger.info(
                f"✅ OPENAI_BATCH_SUCCESS [{context_prefix}] "
                f"Batch completed in {batch_elapsed:.2f}s"
            )

            return batch_embeddings

        except Exception as e:
            # Check if it's a token limit error
            if "maximum context length" in str(e) or "max_tokens_per_request" in str(e):
                logger.warning(
                    f"🚦 OPENAI_TOKEN_LIMIT [{context_prefix}] Hit token limit with batch of "
                    f"{len(batch)} texts, splitting batch"
                )
                return await self._handle_token_limit_error(
                    batch, model, encoding_format, context_prefix
                )
            else:
                raise e

    async def _handle_token_limit_error(
        self, batch: List[str], model: str, encoding_format: str, context_prefix: str
    ) -> List[List[float]]:
        """Handle token limit errors by splitting batches."""
        # Split batch in half and retry
        if len(batch) > 1:
            mid = len(batch) // 2
            first_half = await self._process_single_batch(
                batch[:mid], model, encoding_format, context_prefix
            )
            second_half = await self._process_single_batch(
                batch[mid:], model, encoding_format, context_prefix
            )
            return first_half + second_half
        else:
            # Single text is too long - this shouldn't happen if chunkers work correctly
            logger.error(
                f"❌ OPENAI_CHUNK_TOO_LARGE [{context_prefix}] "
                f"Single chunk exceeds token limit! This indicates a chunker failure."
            )

            # Log the actual content to debug
            text = batch[0]
            text_length = len(text)
            token_count = len(text) // 4  # Rough estimate

            logger.error(
                f"🔍 OPENAI_DEBUG [{context_prefix}] Text details: "
                f"length={text_length} chars, ~{token_count} tokens"
            )

            # Log first 1000 chars to see what type of content it is
            logger.error(
                f"📄 OPENAI_CONTENT_PREVIEW [{context_prefix}] First 1000 chars:\n{text[:1000]}..."
            )

            # Log last 500 chars to see if there's a pattern
            if text_length > 1500:
                logger.error(
                    f"📄 OPENAI_CONTENT_END [{context_prefix}] Last 500 chars:\n...{text[-500:]}"
                )

            # As a last resort, truncate
            truncated_text = batch[0][:30000]  # ~7500 tokens as emergency fallback
            return await self._process_single_batch(
                [truncated_text], model, encoding_format, context_prefix
            )

    def _reinsert_empty_vectors(
        self, embeddings: List[List[float]], empty_indices: set, total_length: int
    ) -> List[List[float]]:
        """Reinsert empty vectors at their original positions."""
        result = []
        embedding_idx = 0

        for i in range(total_length):
            if i in empty_indices:
                result.append([0.0] * self.vector_dimensions)
            else:
                result.append(embeddings[embedding_idx])
                embedding_idx += 1

        logger.info(f"📦 OPENAI_FINAL Final result: {len(result)} vectors")
        return result

    async def close(self):
        """Clean up the shared client when done."""
        if self._client:
            await self._client.close()
            logger.info("OpenAI client closed successfully")
