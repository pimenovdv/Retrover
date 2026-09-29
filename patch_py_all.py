import os
import glob
import re

for file in glob.glob("miro-clone/tests/test_*.py"):
    with open(file, "r") as f:
        content = f.read()

    if "s.bind((\"\", 0))" not in content and "def test_server" in content:
        # Needs to be updated to the socket trick!
        print(f"Updating {file}")

        search = """    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run)
    thread.start()
    time.sleep(1)
    yield server"""

        replace = """    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1)
    yield f"http://127.0.0.1:{port}\""""

        content = content.replace(search, replace)

        search2 = """    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1)
    yield server"""
        content = content.replace(search2, replace)

        with open(file, "w") as f:
            f.write(content)
