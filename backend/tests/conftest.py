import pytest
from fastapi import FastAPI


@pytest.fixture
def app() -> FastAPI:
    from main import create_app

    return create_app()
