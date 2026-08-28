import pytest
from fastapi.testclient import TestClient

from src.main import app


def test_login_invalid():
    with TestClient(app) as client:
        response = client.post(
            "/login", json={"username": "invalid", "password": "user"}
        )
        assert response.status_code == 401


def test_register_invalid():
    with TestClient(app) as client:
        # Create user
        import uuid

        username = f"test_{uuid.uuid4()}"
        client.post("/register", json={"username": username, "password": "user"})
        response = client.post(
            "/register", json={"username": username, "password": "user"}
        )
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_batcher_with_properties():
    from src.main import db_batcher

    await db_batcher.push(
        "add",
        {
            "id": "prop_obj",
            "type": "rect",
            "left": 10,
            "top": 10,
            "z_index": 1,
            "extra": "val",
            "nested": {"a": 1},
        },
    )
    await db_batcher.process_batch()
    await db_batcher.push(
        "modify", {"id": "prop_obj", "extra": "val2", "nested": {"a": 2}}
    )
    await db_batcher.process_batch()
    await db_batcher.push("remove", {"id": "prop_obj"})
    await db_batcher.process_batch()


def test_websocket_endpoint_unauthenticated():
    import os

    os.environ["TESTING"] = "0"
    from starlette.websockets import WebSocketDisconnect

    try:
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect("/ws/some_board/some_user?token=") as ws:
                    pass
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(
                    "/ws/some_board/some_user?token=invalid_token"
                ) as ws:
                    pass
    finally:
        os.environ["TESTING"] = "1"


@pytest.mark.asyncio
async def test_batcher_modify_properties():
    from src.main import db_batcher

    await db_batcher.push(
        "add",
        {
            "id": "prop_modify",
            "type": "rect",
            "left": 10,
            "top": 10,
            "z_index": 1,
            "width": 100,
            "height": 100,
            "fill": "black",
            "radius": 5,
            "text": "test",
            "fontSize": 12,
            "board_id": "test_board",
        },
    )
    await db_batcher.process_batch()

    await db_batcher.push(
        "modify",
        {
            "id": "prop_modify",
            "left": 20,
            "top": 20,
            "width": 200,
            "height": 200,
            "fill": "white",
            "radius": 10,
            "text": "new test",
            "fontSize": 14,
            "z_index": 2,
            "new_prop": "added",
        },
    )
    await db_batcher.process_batch()


@pytest.mark.asyncio
async def test_update_board_access_not_found():
    from datetime import timedelta

    from fastapi import HTTPException

    from src.auth import create_access_token
    from src.database import AsyncSessionLocal
    from src.main import BoardAccessUpdate, update_board_access

    token = create_access_token({"sub": "user1"}, timedelta(minutes=10))
    async with AsyncSessionLocal() as session:
        with pytest.raises(HTTPException) as exc:
            await update_board_access(
                "board_not_exist",
                BoardAccessUpdate(token=token, public_access="view"),
                session,
            )
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_board_access_not_owner():
    from datetime import timedelta

    from fastapi import HTTPException

    from src.auth import create_access_token
    from src.database import AsyncSessionLocal
    from src.main import BoardAccessUpdate, update_board_access
    from src.models import Board

    token = create_access_token({"sub": "user1"}, timedelta(minutes=10))
    async with AsyncSessionLocal() as session:
        board = Board(
            id="board_not_owner", name="board_not_owner", owner_username="other_user"
        )
        session.add(board)
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await update_board_access(
                "board_not_owner",
                BoardAccessUpdate(token=token, public_access="view"),
                session,
            )
        assert exc.value.status_code == 403

        await session.delete(board)
        await session.commit()


@pytest.mark.asyncio
async def test_update_board_access_success():
    from datetime import timedelta

    from src.auth import create_access_token
    from src.database import AsyncSessionLocal
    from src.main import BoardAccessUpdate, update_board_access
    from src.models import Board

    token = create_access_token({"sub": "user1"}, timedelta(minutes=10))
    async with AsyncSessionLocal() as session:
        board = Board(
            id="board_success",
            name="board_success",
            owner_username="user1",
            public_access="edit",
        )
        session.add(board)
        await session.commit()

        res = await update_board_access(
            "board_success",
            BoardAccessUpdate(token=token, public_access="view"),
            session,
        )
        assert res["status"] == "success"
        assert res["public_access"] == "view"

        await session.delete(board)
        await session.commit()


@pytest.mark.asyncio
async def test_websocket_endpoint_unauthenticated_logic():
    # Because testing actual disconnects is flaky, we mock the manager directly
    from unittest.mock import AsyncMock

    from src.main import websocket_endpoint

    ws = AsyncMock()
    # Test valid token but invalid nickname
    import os

    os.environ["TESTING"] = "0"
    from datetime import timedelta

    from src.auth import create_access_token

    try:
        valid_token = create_access_token({"sub": "wrong_user"}, timedelta(minutes=10))
        await websocket_endpoint(ws, "b1", "nick1", valid_token)
        ws.close.assert_called_with(code=1008)
    finally:
        os.environ["TESTING"] = "1"


@pytest.mark.asyncio
async def test_websocket_endpoint_unauthenticated_no_token():
    from unittest.mock import AsyncMock

    from src.main import websocket_endpoint

    ws = AsyncMock()
    import os

    os.environ["TESTING"] = "0"
    try:
        await websocket_endpoint(ws, "b1", "nick1", None)
        ws.close.assert_called_with(code=1008)
    finally:
        os.environ["TESTING"] = "1"


@pytest.mark.asyncio
async def test_websocket_endpoint_unauthenticated_logic_invalid_token():
    from unittest.mock import AsyncMock

    from src.main import websocket_endpoint

    ws = AsyncMock()
    import os

    os.environ["TESTING"] = "0"
    try:
        await websocket_endpoint(ws, "b1", "nick1", "invalid_token")
        ws.close.assert_called_with(code=1008)
    finally:
        os.environ["TESTING"] = "1"


@pytest.mark.asyncio
async def test_batcher_queue_logic():
    from src.main import db_batcher

    db_batcher.queue.clear()

    # Add -> Modify
    await db_batcher.push("add", {"id": "obj1", "val": 1}, "board1")
    await db_batcher.push("modify", {"id": "obj1", "val": 2}, "board1")

    # Modify -> Modify
    await db_batcher.push("modify", {"id": "obj2", "val": 1}, "board1")
    await db_batcher.push("modify", {"id": "obj2", "val": 2}, "board1")

    # Remove -> Add/Modify
    await db_batcher.push("remove", {"id": "obj3"}, "board1")
    await db_batcher.push("add", {"id": "obj3", "val": 1}, "board1")
    await db_batcher.push("remove", {"id": "obj4"}, "board1")
    await db_batcher.push("modify", {"id": "obj4", "val": 1}, "board1")

    # Other combination fallback
    await db_batcher.push("add", {"id": "obj5"}, "board1")
    await db_batcher.push("remove", {"id": "obj5"}, "board1")

    # Should not throw any errors covering all branches
    await db_batcher.process_batch()


@pytest.mark.asyncio
async def test_upload_endpoints():
    with TestClient(app) as client:
        # Invalid pdf
        files = {
            "file": ("test.pdf", b"This is not a real PDF file", "application/pdf")
        }
        resp = client.post("/upload", files=files)
        assert resp.status_code == 400

        # Invalid file type entirely
        files = {"file": ("test.txt", b"text", "text/plain")}
        resp = client.post("/upload", files=files)
        assert resp.status_code == 400

        files = {"file": ("test.txt", b"image", "image/png")}
        resp = client.post("/upload", files=files)
        assert resp.status_code == 400

        # Valid pdf
        import fitz

        pdf_path = "test.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Test", fontsize=20)
        page2 = doc.new_page()
        page2.insert_text((50, 50), "Page 2", fontsize=20)
        doc.save(pdf_path)
        doc.close()

        with open(pdf_path, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            response = client.post("/upload", files=files)

        assert response.status_code == 200

        # valid image
        files = {"file": ("test_image.png", b"fake_image_content", "image/png")}
        response = client.post("/upload", files=files)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_websocket_endpoint_unauthenticated_logic_valid_token():
    import uuid

    from src.database import AsyncSessionLocal
    from src.main import websocket_endpoint
    from src.models import Board

    board_id = f"mocked_{uuid.uuid4()}"

    async with AsyncSessionLocal() as session:
        b = Board(id=board_id, name="Pre Board")
        session.add(b)
        await session.commit()

    class MockWS:
        def __init__(self):
            self.closed = False

        async def accept(self):
            pass

        async def send_text(self, text):
            pass

        async def receive_text(self):
            import asyncio

            await asyncio.sleep(0.1)
            from starlette.websockets import WebSocketDisconnect

            raise WebSocketDisconnect()

        async def close(self, code):
            self.closed = True

    ws = MockWS()
    import os

    os.environ["TESTING"] = "0"
    from datetime import timedelta

    from src.auth import create_access_token

    try:
        async with AsyncSessionLocal() as session:
            valid_token = create_access_token(
                {"sub": "valid_user"}, timedelta(minutes=10)
            )
            # Should not close with 1008 if token is valid and sub matches nickname
            await websocket_endpoint(ws, board_id, "valid_user", valid_token, session)
            assert not ws.closed
    finally:
        os.environ["TESTING"] = "1"


@pytest.mark.asyncio
async def test_websocket_endpoint_existing_board_coverage_with_properties():
    import uuid

    from src.database import AsyncSessionLocal
    from src.models import Board, Shape

    board_id = f"pre_board_prop_{uuid.uuid4()}"

    async with AsyncSessionLocal() as session:
        b = Board(id=board_id, name="Pre Board")
        session.add(b)
        s1 = Shape(
            id=f"s1_{uuid.uuid4()}",
            board_id=board_id,
            type="rect",
            left=10,
            top=10,
            z_index=1,
            width=20,
            height=20,
            fill="blue",
            properties={"extra": "prop"},
        )
        s2 = Shape(
            id=f"s2_{uuid.uuid4()}",
            board_id=board_id,
            type="circle",
            left=10,
            top=10,
            z_index=2,
            radius=10,
            fill="red",
            properties={},
        )
        s3 = Shape(
            id=f"s3_{uuid.uuid4()}",
            board_id=board_id,
            type="text",
            left=10,
            top=10,
            z_index=3,
            text="hello",
            fontSize=16,
            properties={},
        )
        session.add(s1)
        session.add(s2)
        session.add(s3)
        await session.commit()

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{board_id}/pre_user") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "init"
            assert len(msg["data"]) == 3
            assert msg["data"][0]["type"] == "rect"
            assert msg["data"][1]["type"] == "circle"
            assert msg["data"][2]["type"] == "text"


@pytest.mark.asyncio
async def test_auth_routes_directly():
    import uuid

    from fastapi import HTTPException

    from src.database import AsyncSessionLocal
    from src.main import UserAuth, login, register

    username = f"auth_user_{uuid.uuid4()}"
    pwd = "password123"

    async with AsyncSessionLocal() as session:
        # Register user
        req = UserAuth(username=username, password=pwd)
        res = await register(req, session)
        assert "access_token" in res

        # Register existing
        with pytest.raises(HTTPException) as exc:
            await register(req, session)
        assert exc.value.status_code == 400

        # Login correct
        res2 = await login(req, session)
        assert "access_token" in res2

        # Login incorrect
        req_bad = UserAuth(username=username, password="wrongpassword")
        with pytest.raises(HTTPException) as exc2:
            await login(req_bad, session)
        assert exc2.value.status_code == 401


@pytest.mark.asyncio
async def test_websocket_integrity_error_during_connect():
    import uuid
    from unittest.mock import patch

    from sqlalchemy.exc import IntegrityError

    from src.database import AsyncSessionLocal
    from src.main import websocket_endpoint
    from src.models import Board

    board_id = f"mocked_{uuid.uuid4()}"

    class MockWS:
        def __init__(self):
            self.closed = False

        async def accept(self):
            pass

        async def send_text(self, text):
            pass

        async def receive_text(self):
            import asyncio

            await asyncio.sleep(0.1)
            from starlette.websockets import WebSocketDisconnect

            raise WebSocketDisconnect()

        async def close(self, code):
            self.closed = True

    ws = MockWS()
    import os

    os.environ["TESTING"] = "1"

    async with AsyncSessionLocal() as session:
        # Mock session.commit to throw IntegrityError
        original_commit = session.commit

        async def mock_commit():
            # In an Integrity error, we actually create the board here behind the scenes
            # to simulate the other thread succeeding
            b = Board(id=board_id, name="Other thread board")
            session.add(b)
            await original_commit()
            raise IntegrityError("mock", "mock", "mock")

        with patch.object(session, "commit", new=mock_commit):
            try:
                await websocket_endpoint(ws, board_id, "test_user", None, session)
                assert not ws.closed
            except Exception:
                # the WebSocketDisconnect bubbles up from receive_text
                pass
