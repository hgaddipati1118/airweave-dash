"""Search service for vector database integrations."""

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.platform.embedding_models.local_text2vec import LocalText2Vec
from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec
from airweave.platform.locator import resource_locator
from airweave.schemas.search import ResponseType, SearchStatus

logger = logging.getLogger(__name__)


class SearchService:
    """Service for handling vector database searches."""

    def _clean_search_results(self, results: list[dict], for_display: bool = True) -> list[dict]:
        """Clean search results by removing large fields and optionally truncating content.

        Args:
            results: Raw search results from vector database
            for_display: If True, truncate large text fields for frontend display.
                        If False, only remove truly unnecessary fields (vectors, download_urls)

        Returns:
            Cleaned search results
        """
        cleaned_results = []

        for result in results:
            if not isinstance(result, dict):
                cleaned_results.append(result)
                continue

            cleaned_result = result.copy()

            if "payload" in cleaned_result and isinstance(cleaned_result["payload"], dict):
                payload = cleaned_result["payload"].copy()

                # Always remove these fields - they're too large or unnecessary
                fields_to_always_remove = [
                    "vector",
                    "download_url",
                    "local_path",
                    "file_uuid",
                    "checksum",
                ]
                for field in fields_to_always_remove:
                    payload.pop(field, None)

                if for_display:
                    # Handle nested JSON strings - parse them for better display
                    json_fields = ["metadata", "sync_metadata", "auth_fields", "config_fields"]
                    for field in json_fields:
                        if field in payload and isinstance(payload[field], str):
                            try:
                                # Try to parse JSON string to object for better display
                                payload[field] = json.loads(payload[field])
                            except json.JSONDecodeError:
                                # If it's not valid JSON, keep as is (no truncation)
                                pass

                cleaned_result["payload"] = payload

            cleaned_results.append(cleaned_result)

        return cleaned_results

    async def search(
        self,
        db: AsyncSession,
        query: str,
        readable_id: str,
        current_user: schemas.User,
    ) -> list[dict]:
        """Search across vector database using existing connections.

        Args:
            db (AsyncSession): Database session
            query (str): Search query text
            readable_id (str): Readable ID of the collection to search within
            current_user (schemas.User): Current user performing the search

        Returns:
            list[dict]: List of cleaned search results

        Raises:
            NotFoundException: If sync or connections not found
        """
        try:
            collection = await crud.collection.get_by_readable_id(db, readable_id, current_user)
            if not collection:
                raise NotFoundException("Collection not found")

            # Get the destination model
            destination_model = await crud.destination.get_by_short_name(db, "qdrant_native")
            if not destination_model:
                raise NotFoundException("Destination not found")

            # Initialize destination class
            destination_class = resource_locator.get_destination(destination_model)

            # Use OpenAI embeddings if API key is available
            if settings.OPENAI_API_KEY:
                logger.info(
                    "Using OpenAI embedding model for search in "
                    f"collection {readable_id} {collection.id}"
                )
                embedding_model = OpenAIText2Vec(api_key=settings.OPENAI_API_KEY)
            else:
                logger.info(
                    "Using local embedding model for search in "
                    f"collection {readable_id} {collection.id}"
                )
                embedding_model = LocalText2Vec()

            vector = await embedding_model.embed(query)
            destination = await destination_class.create(collection_id=collection.id)

            # Perform search
            results = await destination.search(vector)

            # Clean results before returning
            cleaned_results = self._clean_search_results(results, for_display=True)

            return cleaned_results

        except NotFoundException:
            # Re-raise NotFoundExceptions as-is
            raise
        except ConnectionError as e:
            logger.error(f"Vector database connection error: {str(e)}")
            raise ConnectionError(f"Unable to connect to vector database: {str(e)}") from e
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            # Add more context to the error
            if "connection" in str(e).lower():
                raise ConnectionError(f"Vector database connection failed: {str(e)}") from e
            raise

    async def search_with_completion(
        self,
        db: AsyncSession,
        query: str,
        readable_id: str,
        current_user: schemas.User,
        response_type: ResponseType = ResponseType.RAW,
    ) -> schemas.SearchResponse:
        """Search and optionally generate AI completion for results.

        Args:
            db: The database session
            query: The search query text
            readable_id: Readable ID of the collection to search in
            current_user: The current user
            response_type: Type of response (raw results or AI completion)

        Returns:
            dict: A dictionary containing search results or AI completion
        """
        # Lazy import to avoid circular dependency
        from airweave.core.chat_service import chat_service

        # Note: search() now returns cleaned results
        results = await self.search(
            db=db,
            query=query,
            readable_id=readable_id,
            current_user=current_user,
        )

        if response_type == ResponseType.RAW:
            return schemas.SearchResponse(
                results=results, response_type=response_type, status=SearchStatus.SUCCESS
            )

        # If no results found, return a more specific message
        if not results:
            return schemas.SearchResponse(
                results=[],
                completion=(
                    "I couldn't find any relevant information for that query. "
                    "Try asking about something in your data collection."
                ),
                response_type=ResponseType.COMPLETION,
                status=SearchStatus.NO_RESULTS,
            )

        # For low-quality results (where scores are low), add this check:
        has_relevant_results = any(result.get("score", 0) > 0.25 for result in results)
        if not has_relevant_results:
            return schemas.SearchResponse(
                results=results,
                completion=(
                    "Your query didn't match anything meaningful in the database. "
                    "Please try a different question related to your data."
                ),
                response_type=ResponseType.COMPLETION,
                status=SearchStatus.NO_RELEVANT_RESULTS,
            )

        # For completion generation, we need full content (not truncated)
        # So fetch results again but with less aggressive cleaning
        raw_results = await self._get_raw_search_results(
            db=db,
            query=query,
            readable_id=readable_id,
            current_user=current_user,
        )

        # Clean raw results but don't truncate content
        context_results = self._clean_search_results(raw_results, for_display=False)

        # Modify the context prompt to be more specific about only answering based on context
        messages = [
            {
                "role": "system",
                "content": chat_service.CONTEXT_PROMPT.format(
                    context=str(context_results),
                    additional_instruction=(
                        "If the provided context doesn't contain information to answer "
                        "the query directly, respond with 'I don't have enough information to "
                        "answer that question based on the available data.'"
                    ),
                ),
            },
            {"role": "user", "content": query},
        ]

        # Generate completion
        model = chat_service.DEFAULT_MODEL
        model_settings = chat_service.DEFAULT_MODEL_SETTINGS.copy()

        # Remove streaming setting if present
        if "stream" in model_settings:
            model_settings.pop("stream")

        try:
            response = await chat_service.client.chat.completions.create(
                model=model, messages=messages, **model_settings
            )

            completion = (
                response.choices[0].message.content
                if response.choices
                else "Unable to generate completion."
            )
        except Exception as e:
            completion = f"Error generating completion: {str(e)}"

        # Return the display-friendly cleaned results along with completion
        return schemas.SearchResponse(
            results=results,
            completion=completion,
            response_type=response_type,
            status=SearchStatus.SUCCESS,
        )

    async def _get_raw_search_results(
        self,
        db: AsyncSession,
        query: str,
        readable_id: str,
        current_user: schemas.User,
    ) -> list[dict]:
        """Get raw search results without cleaning (internal use only).

        This is used when we need the full content for AI completion generation.
        """
        collection = await crud.collection.get_by_readable_id(db, readable_id, current_user)
        if not collection:
            raise NotFoundException("Collection not found")

        destination_model = await crud.destination.get_by_short_name(db, "qdrant_native")
        if not destination_model:
            raise NotFoundException("Destination not found")

        destination_class = resource_locator.get_destination(destination_model)

        if settings.OPENAI_API_KEY:
            embedding_model = OpenAIText2Vec(api_key=settings.OPENAI_API_KEY)
        else:
            embedding_model = LocalText2Vec()

        vector = await embedding_model.embed(query)
        destination = await destination_class.create(collection_id=collection.id)

        return await destination.search(vector)


# Create singleton instance
search_service = SearchService()
