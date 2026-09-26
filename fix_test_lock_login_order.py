import os
import re

full_path = os.path.join("miro-clone", "tests/test_lock.py")
with open(full_path, "r") as f:
    content = f.read()

# page.fill is happening before page.goto()
content = content.replace(
    'page.fill("#board-id-input", f"board_{uuid.uuid4().hex[:8]}")\n        page.goto(f"http://127.0.0.1:{test_server}/")',
    'page.goto(f"http://127.0.0.1:{test_server}/")\n        page.fill("#board-id-input", f"board_{uuid.uuid4().hex[:8]}")'
)

with open(full_path, "w") as f:
    f.write(content)
