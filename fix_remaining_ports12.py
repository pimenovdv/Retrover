import os
import re

files_to_fix = [
    "tests/test_grid_snap.py",
    "tests/test_clear_board.py",
]

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

for file_path in files_to_fix:
    full_path = os.path.join("miro-clone", file_path)
    if not os.path.exists(full_path):
        continue

    with open(full_path, "r") as f:
        content = f.read()

    # The previous fix failed to catch test_grid_snap because it has app_server fixture name
    if 'def app_server():' in content:
        content = re.sub(
            r'@pytest\.fixture\(scope="module"\)\ndef app_server\(\):.*?yield.*?\n.*?thread\.join\(\)',
            new_server_fixture().replace('def server():', 'def app_server():').strip(),
            content,
            flags=re.DOTALL
        )
        content = content.replace('page.goto("http://127.0.0.1:8002/")', 'page.goto(app_server)')

    if 'def test_clear_board' in content:
        content = re.sub(
            r'def run_server\(\):.*?@pytest\.fixture\(scope="module"\)\ndef test_server\(\):.*?yield',
            new_server_fixture().replace('def server():', 'def test_server():')[:-38].strip(),
            content,
            flags=re.DOTALL
        )
        content = content.replace('await page.goto("http://127.0.0.1:8002/")', 'await page.goto(test_server)')

    with open(full_path, "w") as f:
        f.write(content)
