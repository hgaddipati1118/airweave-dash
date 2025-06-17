"""Pytest configuration for embedding model tests."""

# This file is here to ensure pytest can discover test modules correctly
# Any shared fixtures should be defined here if needed

import pytest
from airweave.core.config import settings
from airweave.platform.embedding_models.local_text2vec import LocalText2Vec


@pytest.fixture
def model_class():
    """Return the LocalText2Vec class."""
    return LocalText2Vec


@pytest.fixture
def model_kwargs():
    """Return kwargs for model initialization."""
    inference_url = settings.TEXT2VEC_INFERENCE_URL
    if not inference_url:
        raise ValueError("TEXT2VEC_INFERENCE_URL environment variable is not set")
    return {"inference_url": inference_url}


@pytest.fixture
def model(model_class, model_kwargs):
    """Create and return a model instance."""
    return model_class(**model_kwargs)
