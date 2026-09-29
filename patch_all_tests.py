import os
import glob

# Ensure all fixtures use daemon=True for uvicorn thread to prevent pytest hanging
for file in glob.glob("miro-clone/tests/test_*.py"):
    with open(file, "r") as f:
        content = f.read()

    # Let's completely rewrite the test_server fixtures to use the proper port trick and yield the right URL.
    # We will look for anything that yields something regarding the server.

    search = """def test_server():
    import socket
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

    if "def test_server():" in content:
        # Revert the fixture to return port, and manually fix the usages
        print("FIXING", file)
