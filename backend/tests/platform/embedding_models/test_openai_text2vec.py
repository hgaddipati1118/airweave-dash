"""Tests for OpenAIText2Vec embedding model."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai.types import Embedding
from openai.types.create_embedding_response import CreateEmbeddingResponse

from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec


class TestOpenAIText2Vec:
    """Tests for the OpenAIText2Vec embedding model."""

    @pytest.fixture
    def model_class(self):
        """Return the OpenAIText2Vec class."""
        return OpenAIText2Vec

    @pytest.fixture
    def model_kwargs(self):
        """Return kwargs for model initialization."""
        return {"api_key": "test-api-key", "embedding_model": "text-embedding-3-small"}

    @pytest.fixture
    def model(self, model_class, model_kwargs):
        """Create and return a model instance."""
        return model_class(**model_kwargs)

    @pytest.mark.asyncio
    async def test_embed_empty_text(self, model):
        """Test embedding an empty string returns zero vector."""
        result = await model.embed("")
        assert isinstance(result, list)
        assert len(result) == model.vector_dimensions
        assert all(v == 0.0 for v in result)

    @pytest.mark.asyncio
    async def test_embed_many_empty_list(self, model):
        """Test embedding an empty list returns empty list."""
        result = await model.embed_many([])
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_embed_many_all_empty_strings(self, model):
        """Test embedding a list of empty strings returns zeros."""
        result = await model.embed_many(["", ""])
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(len(vec) == model.vector_dimensions for vec in result)
        assert all(all(v == 0.0 for v in vec) for vec in result)

    @pytest.mark.asyncio
    async def test_create_classmethod(self, model_class, model_kwargs):
        """Test the create class method works."""
        model = model_class.create(**model_kwargs)
        assert isinstance(model, model_class)
        for key, value in model_kwargs.items():
            assert getattr(model, key) == value

    @pytest.mark.asyncio
    async def test_embed_success(self, model):
        """Test successful embedding of a single text."""
        # Mock the client's embeddings.create method
        mock_embedding = [0.1, 0.2, 0.3] * 512  # 1536 dimensions
        mock_response = CreateEmbeddingResponse(
            object="list",
            data=[
                Embedding(
                    object="embedding",
                    embedding=mock_embedding,
                    index=0
                )
            ],
            model="text-embedding-3-small",
            usage={"prompt_tokens": 5, "total_tokens": 5}
        )

        with patch.object(model._client.embeddings, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response

            result = await model.embed("Test text")

            # Verify the result
            assert isinstance(result, list)
            assert len(result) == 1536  # Default dimensions for OpenAI
            assert result == mock_embedding

            # Verify the API call
            mock_create.assert_called_once_with(
                input="Test text",
                model="text-embedding-3-small",
                encoding_format="float",
            )

    @pytest.mark.asyncio
    async def test_embed_with_model_override(self, model):
        """Test embedding with model override."""
        mock_embedding = [0.1, 0.2, 0.3] * 512
        mock_response = CreateEmbeddingResponse(
            object="list",
            data=[
                Embedding(
                    object="embedding",
                    embedding=mock_embedding,
                    index=0
                )
            ],
            model="text-embedding-3-large",
            usage={"prompt_tokens": 5, "total_tokens": 5}
        )

        with patch.object(model._client.embeddings, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response

            await model.embed("Test text", model="text-embedding-3-large")

            # Verify the API call uses the overridden model
            mock_create.assert_called_once_with(
                input="Test text",
                model="text-embedding-3-large",
                encoding_format="float",
            )

    @pytest.mark.asyncio
    async def test_embed_with_dimensions_override(self, model):
        """Test that dimensions override raises an error."""
        with pytest.raises(ValueError, match="Dimensions override not supported"):
            await model.embed("Test text", dimensions=512)

    @pytest.mark.asyncio
    async def test_embed_many_success(self, model):
        """Test successful embedding of multiple texts."""
        mock_embeddings = [
            [0.1, 0.2, 0.3] * 512,
            [0.4, 0.5, 0.6] * 512
        ]
        mock_response = CreateEmbeddingResponse(
            object="list",
            data=[
                Embedding(
                    object="embedding",
                    embedding=mock_embeddings[0],
                    index=0
                ),
                Embedding(
                    object="embedding",
                    embedding=mock_embeddings[1],
                    index=1
                )
            ],
            model="text-embedding-3-small",
            usage={"prompt_tokens": 10, "total_tokens": 10}
        )

        with patch.object(model._client.embeddings, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response

            texts = ["Text 1", "Text 2"]
            result = await model.embed_many(texts)

            # Verify the result
            assert isinstance(result, list)
            assert len(result) == 2
            assert all(len(vec) == 1536 for vec in result)
            assert result == mock_embeddings

            # Verify the API call
            mock_create.assert_called_once_with(
                input=texts,
                model="text-embedding-3-small",
                encoding_format="float",
            )

    @pytest.mark.asyncio
    async def test_embed_many_with_some_empty(self, model):
        """Test embedding of a mix of empty and non-empty texts."""
        mock_embedding = [0.1, 0.2, 0.3] * 512
        mock_response = CreateEmbeddingResponse(
            object="list",
            data=[
                Embedding(
                    object="embedding",
                    embedding=mock_embedding,
                    index=0
                )
            ],
            model="text-embedding-3-small",
            usage={"prompt_tokens": 5, "total_tokens": 5}
        )

        with patch.object(model._client.embeddings, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response

            texts = ["", "Text 2"]
            result = await model.embed_many(texts)

            # Verify the result
            assert isinstance(result, list)
            assert len(result) == 2
            assert all(len(vec) == 1536 for vec in result)
            assert all(v == 0.0 for v in result[0])  # First vector should be all zeros
            assert result[1] == mock_embedding  # Second vector should be the real embedding

            # Verify the API call only sends the non-empty text
            mock_create.assert_called_once_with(
                input=["Text 2"],  # Only non-empty text
                model="text-embedding-3-small",
                encoding_format="float",
            )

    @pytest.mark.asyncio
    async def test_embed_many_with_model_override(self, model):
        """Test embedding with model override."""
        mock_embedding = [0.1, 0.2, 0.3] * 512
        mock_response = CreateEmbeddingResponse(
            object="list",
            data=[
                Embedding(
                    object="embedding",
                    embedding=mock_embedding,
                    index=0
                )
            ],
            model="text-embedding-3-large",
            usage={"prompt_tokens": 5, "total_tokens": 5}
        )

        with patch.object(model._client.embeddings, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response

            await model.embed_many(["Test text"], model="text-embedding-3-large")

            # Verify the API call uses the overridden model
            mock_create.assert_called_once_with(
                input=["Test text"],
                model="text-embedding-3-large",
                encoding_format="float",
            )

    @pytest.mark.asyncio
    async def test_embed_many_with_dimensions_override(self, model):
        """Test that dimensions override raises an error."""
        with pytest.raises(ValueError, match="Dimensions override not supported"):
            await model.embed_many(["Test text"], dimensions=512)

    @pytest.mark.asyncio
    async def test_embed_handles_exception(self, model):
        """Test that exceptions from the OpenAI client are propagated."""
        with patch.object(model._client.embeddings, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("OpenAI API error")

            with pytest.raises(Exception, match="OpenAI API error"):
                await model.embed("Test text")

    @pytest.mark.asyncio
    async def test_embed_many_handles_exception(self, model):
        """Test that exceptions from the OpenAI client are propagated."""
        with patch.object(model._client.embeddings, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("OpenAI API error")

            with pytest.raises(Exception, match="OpenAI API error"):
                await model.embed_many(["Test text"])

    @pytest.mark.asyncio
    async def test_close_client(self, model):
        """Test that close method properly closes the client."""
        # The client should exist initially
        assert model._client is not None

        # Mock the close method
        with patch.object(model._client, 'close', new_callable=AsyncMock) as mock_close:
            await model.close()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_with_entity_context(self, model):
        """Test embedding with entity context (should just be logged)."""
        mock_embedding = [0.1, 0.2, 0.3] * 512
        mock_response = CreateEmbeddingResponse(
            object="list",
            data=[
                Embedding(
                    object="embedding",
                    embedding=mock_embedding,
                    index=0
                )
            ],
            model="text-embedding-3-small",
            usage={"prompt_tokens": 5, "total_tokens": 5}
        )

        with patch.object(model._client.embeddings, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response

            result = await model.embed("Test text", entity_context="test_entity")

            # Verify the result is the same (entity_context only affects logging)
            assert result == mock_embedding

            # Verify the API call is the same
            mock_create.assert_called_once_with(
                input="Test text",
                model="text-embedding-3-small",
                encoding_format="float",
            )

    @pytest.mark.asyncio
    async def test_embed_many_with_entity_context(self, model):
        """Test batch embedding with entity context (should just be logged)."""
        mock_embedding = [0.1, 0.2, 0.3] * 512
        mock_response = CreateEmbeddingResponse(
            object="list",
            data=[
                Embedding(
                    object="embedding",
                    embedding=mock_embedding,
                    index=0
                )
            ],
            model="text-embedding-3-small",
            usage={"prompt_tokens": 5, "total_tokens": 5}
        )

        with patch.object(model._client.embeddings, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response

            result = await model.embed_many(["Test text"], entity_context="test_entity")

            # Verify the result is the same (entity_context only affects logging)
            assert result == [mock_embedding]

            # Verify the API call is the same
            mock_create.assert_called_once_with(
                input=["Test text"],
                model="text-embedding-3-small",
                encoding_format="float",
            )

    @pytest.mark.asyncio
    async def test_large_batch_splitting(self, model):
        """Test that large batches are split appropriately."""
        # Create a list of 150 texts (larger than MAX_BATCH_SIZE of 100)
        texts = [f"Text {i}" for i in range(150)]

        mock_embedding = [0.1, 0.2, 0.3] * 512

        # Create responses for each batch
        def create_mock_response(batch_size):
            return CreateEmbeddingResponse(
                object="list",
                data=[
                    Embedding(
                        object="embedding",
                        embedding=mock_embedding,
                        index=i
                    ) for i in range(batch_size)
                ],
                model="text-embedding-3-small",
                usage={"prompt_tokens": batch_size * 5, "total_tokens": batch_size * 5}
            )

        with patch.object(model._client.embeddings, 'create', new_callable=AsyncMock) as mock_create:
            # Setup side effects for multiple batches
            mock_create.side_effect = [
                create_mock_response(100),  # First batch: 100 texts
                create_mock_response(50),   # Second batch: 50 texts
            ]

            result = await model.embed_many(texts)

            # Verify the result
            assert isinstance(result, list)
            assert len(result) == 150
            assert all(len(vec) == 1536 for vec in result)

            # Verify two API calls were made
            assert mock_create.call_count == 2

            # Verify the first call had 100 texts and second had 50
            first_call_args = mock_create.call_args_list[0]
            second_call_args = mock_create.call_args_list[1]

            assert len(first_call_args.kwargs["input"]) == 100
            assert len(second_call_args.kwargs["input"]) == 50
