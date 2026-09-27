import os
import re

full_path = os.path.join("tests", "test_clear_board.py")
with open(full_path, "r") as f:
    content = f.read()

def new_server_fixture():
    return """
@pytest.fixture(scope="module")
def test_server():
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

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join()
"""

# Replace test_export server with one that works like minimap
content = re.sub(r'def run_server\(\):.*?\n\n\n@pytest\.fixture\(scope="module"\)\ndef test_server\(\):.*?yield', new_server_fixture().strip(), content, flags=re.DOTALL)
content = content.replace('await page.goto("http://127.0.0.1:8002/")', 'await page.goto(test_server)')

with open(full_path, "w") as f:
    f.write(content)
