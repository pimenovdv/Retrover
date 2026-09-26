import os
import glob
import re

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

files_to_fix = [
    "tests/test_text_group.py",
    "tests/test_undo_redo.py",
    "tests/test_zoom.py",
]

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
            content = content.replace('yield server', 'yield f"http://127.0.0.1:{port}"')
            content = content.replace('page.goto(test_server)', 'page.goto(test_server)')
            content = content.replace('page.goto("http://127.0.0.1:{port}")', 'page.goto(test_server)')
            content = content.replace('await page.goto(f"http://127.0.0.1:{port}")', 'await page.goto(test_server)')

            # for test_undo_redo
            content = content.replace('yield "http://127.0.0.1:8001"', 'yield f"http://127.0.0.1:{port}"')

    with open(full_path, "w") as f:
        f.write(content)
