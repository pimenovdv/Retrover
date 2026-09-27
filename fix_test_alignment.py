import os
import re

full_path = os.path.join("miro-clone", "tests/test_alignment.py")
with open(full_path, "r") as f:
    content = f.read()

# Replace test_alignment server with one that works like minimap
content = re.sub(r'def run_server\(\):.*?\n\n\nasync def init_db\(\).*?async def drop_db\(\).*?\n\n\n@pytest\.fixture\(scope="module"\)\ndef test_server\(\):.*?asyncio\.run\(drop_db\(\)\)', '''
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

    thread = threading.Thread(target=server.run)
    thread.start()
    time.sleep(1)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join()
'''.strip(), content, flags=re.DOTALL)

content = content.replace('page.goto("http://127.0.0.1:8002/?board=alignment_board")', 'page.goto(f"{test_server}/?board=alignment_board_{uuid.uuid4().hex[:8]}")')

with open(full_path, "w") as f:
    f.write(content)
