import os
import re

full_path = os.path.join("miro-clone", "tests/test_minimap.py")
with open(full_path, "r") as f:
    content = f.read()

# I apparently restored tests/ in git midway and forgot to fix minimap again.
def new_server_fixture():
    return """
@pytest.fixture(scope="module")
def server():
    import threading
    import time
    import uvicorn
    import socket
    from src.main import app

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run)
    thread.start()
    time.sleep(1)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join()
"""

content = re.sub(
    r'@pytest\.fixture\(scope="module"\)\ndef server\(\):.*?yield.*?\n.*?thread\.join\(\)',
    new_server_fixture().strip(),
    content,
    flags=re.DOTALL
)

content = content.replace('page.goto("http://127.0.0.1:8001")', 'page.goto(server)')
content = content.replace('page.fill("#board-id-input", "test_board")', 'page.wait_for_selector("#login-modal", state="visible")\n        page.fill("#board-id-input", "test_board")')

with open(full_path, "w") as f:
    f.write(content)
