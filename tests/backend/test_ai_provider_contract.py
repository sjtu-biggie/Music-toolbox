import pytest
from abc import ABC
from backend.providers.base import AIProvider


def test_aiprovider_is_abstract():
    assert issubclass(AIProvider, ABC)


def test_aiprovider_cannot_be_instantiated():
    with pytest.raises(TypeError):
        AIProvider()


def test_aiprovider_has_modify_method():
    assert hasattr(AIProvider, "modify")
