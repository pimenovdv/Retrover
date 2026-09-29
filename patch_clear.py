with open("miro-clone/tests/test_clear_board.py", "r") as f:
    content = f.read()

search = """@pytest.fixture
def test_server():
    import threading
    import time

    import uvicorn

    from src.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run)
    thread.start()
    time.sleep(1)
    yield server
    server.should_exit = True
    thread.join(timeout=5)"""

replace = """@pytest.fixture
def test_server():
    import socket
    import threading
    import time
    import uvicorn
    from src.main import app

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)"""

content = content.replace(search, replace)
content = content.replace('await page.goto("http://127.0.0.1:8000/")', 'await page.goto(f"{test_server}/")')

with open("miro-clone/tests/test_clear_board.py", "w") as f:
    f.write(content)
