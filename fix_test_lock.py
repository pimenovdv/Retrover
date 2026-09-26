import os
import re

full_path = os.path.join("miro-clone", "tests/test_lock.py")
with open(full_path, "r") as f:
    content = f.read()

# Fix wait_for_selector by generating a unique board id so it doesn't collide with existing data
content = content.replace(
    'username = str(uuid.uuid4())',
    'username = str(uuid.uuid4())\n        page.fill("#board-id-input", f"board_{uuid.uuid4().hex[:8]}")'
)

with open(full_path, "w") as f:
    f.write(content)
