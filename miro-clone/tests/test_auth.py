import pytest
import os
os.environ["TESTING"] = "1"
import asyncio
from fastapi.testclient import TestClient

from src.main import app
from src.database import Base, engine

@pytest.fixture(autouse=True, scope="module")
def setup_db_sync():
    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_setup())
    yield
    loop.run_until_complete(_teardown())


def test_register_and_login():
    with TestClient(app) as client:
        # 1. Register a new user
        response = client.post("/register", json={"username": "testuser_auth", "password": "password123"})
        assert response.status_code == 200
        assert response.json() == {"message": "User registered successfully"}

        # 2. Try to register the same user again
        response = client.post("/register", json={"username": "testuser_auth", "password": "password123"})
        assert response.status_code == 400
        assert response.json() == {"detail": "Username already registered"}

        # 3. Login with correct credentials
        response = client.post("/login", json={"username": "testuser_auth", "password": "password123"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "testuser_auth"

        # 4. Login with incorrect password
        response = client.post("/login", json={"username": "testuser_auth", "password": "wrongpassword"})
        assert response.status_code == 401
        assert response.json() == {"detail": "Incorrect username or password"}

        # 5. Login with non-existent user
        response = client.post("/login", json={"username": "nonexistent_user", "password": "password123"})
        assert response.status_code == 401

def test_websocket_auth():
    # Remove TESTING flag to test auth requirement
    os.environ.pop("TESTING", None)
    try:
        with TestClient(app) as client:
            client.post("/register", json={"username": "ws_auth_user", "password": "password123"})
            response = client.post("/login", json={"username": "ws_auth_user", "password": "password123"})
            token = response.json()["access_token"]

            # Should connect with correct token
            with client.websocket_connect(f"/ws/auth_board/ws_auth_user?token={token}") as ws:
                data = ws.receive_json()
                assert data["type"] == "init"

            # Should fail without token
            from fastapi.websockets import WebSocketDisconnect
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(f"/ws/auth_board/ws_auth_user") as ws:
                    pass

            # Should fail with token for different user
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(f"/ws/auth_board/other_user?token={token}") as ws:
                    pass

            # Should fail with invalid token
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(f"/ws/auth_board/ws_auth_user?token=invalid_token") as ws:
                    pass
    finally:
        os.environ["TESTING"] = "1"
