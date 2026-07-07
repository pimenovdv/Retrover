import pytest
import os
import asyncio
from fastapi.testclient import TestClient

def test_exception():
    from src.main import app
    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        test_file_path = "test_img.xyz"
        with open(test_file_path, "wb") as f:
            f.write(b"dummy image content")

        with open(test_file_path, "rb") as f:
            response = client.post("/upload", files={"file": ("test_img.xyz", f, "image/png")})
            assert response.status_code == 400

        os.remove(test_file_path)

test_exception()
