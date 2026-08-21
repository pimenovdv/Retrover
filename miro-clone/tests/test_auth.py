import os

import pytest
from fastapi.testclient import TestClient

os.environ["TESTING"] = "1"

import asyncio
import uuid

from src.auth import verify_password
from src.database import Base, engine
from src.main import app


@pytest.fixture(scope="module")
def client():
    # Setup test DB schema
    async def setup_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup_db())

    with TestClient(app) as c:
        yield c

    loop.close()


def test_register_login(client):
    username = f"testuser_{uuid.uuid4()}"
    password = "testpassword123"

    # Test Register
    response = client.post(
        "/register", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Test Register Duplicate
    response = client.post(
        "/register", json={"username": username, "password": password}
    )
    assert response.status_code == 400

    # Test Login
    response = client.post("/login", json={"username": username, "password": password})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Test Login Invalid
    response = client.post(
        "/login", json={"username": username, "password": "wrongpassword"}
    )
    assert response.status_code == 401


def test_unauthenticated_ws_rejected(client):
    # Unset TESTING to simulate production env for this specific block
    # Note: TestClient handles WebSockets locally
    os.environ["TESTING"] = "0"

    try:
        with pytest.raises(
            Exception
        ):  # WebSocketDisconnect or similar due to code=1008
            with client.websocket_connect("/ws/default/testuser"):
                pass
    finally:
        os.environ["TESTING"] = "1"  # Restoreimport pytest


def test_verify_password():
    assert not verify_password(
        "wrong", "$2b$12$KIXeW3n4Y1QhU0Yd1.1Q3.V/z9/k936.pT.H/uNf/J2qV7uV5aLp2"
    )
