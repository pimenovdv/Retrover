import os
import re

files_to_fix = [
    "tests/test_text_align.py",
    "tests/test_sticky.py",
    "tests/test_responsive.py",
]

def get_free_port_code():
    return """
def get_free_port():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port
"""

for file_path in files_to_fix:
    full_path = os.path.join("miro-clone", file_path)
    with open(full_path, "r") as f:
        content = f.read()

    if "def get_free_port():" not in content:
        # Add get_free_port after imports
        import_match = re.search(r'(import .*?\n(?:from .*? import .*?\n)*)', content, re.MULTILINE)
        if import_match:
            end_of_imports = import_match.end()
            content = content[:end_of_imports] + "\n" + get_free_port_code() + "\n" + content[end_of_imports:]

    # Replace fixed port with dynamic port
    if 'port=8000' in content or 'port=8001' in content or 'port=8002' in content:
        content = re.sub(r'port=800\d', 'port=port', content)
        content = re.sub(r'config = uvicorn\.Config\(app', 'port = get_free_port()\n    config = uvicorn.Config(app', content)
        content = re.sub(r'http://127\.0\.0\.1:800\d/?', 'f"http://127.0.0.1:{port}"', content)

        # fix yield server url
        if 'yield server' in content:
            content = content.replace('yield server', 'port = server.config.port\n    yield f"http://127.0.0.1:{port}"')
            content = content.replace('await page.goto(f"http://127.0.0.1:{port}")', 'await page.goto(test_server)')

    with open(full_path, "w") as f:
        f.write(content)
