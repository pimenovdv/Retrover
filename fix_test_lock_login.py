import os
import re

full_path = os.path.join("miro-clone", "tests/test_lock.py")
with open(full_path, "r") as f:
    content = f.read()

# Fix wait_for_selector by generating a unique board id so it doesn't collide with existing data
content = content.replace(
    'page.goto(f"http://127.0.0.1:{test_server}/")',
    'page.goto(f"http://127.0.0.1:{test_server}/")\n        page.wait_for_selector("#login-modal", state="visible")'
)

with open(full_path, "w") as f:
    f.write(content)
