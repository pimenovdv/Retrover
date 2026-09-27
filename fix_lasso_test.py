import os

full_path = os.path.join("miro-clone", "tests/test_lasso.py")
with open(full_path, "r") as f:
    content = f.read()

# Add a unique board id so previous runs don't interfere and give us 2 objects selected
import uuid
content = content.replace('"test_board_lasso"', f'"test_board_lasso_{uuid.uuid4().hex[:8]}"')

with open(full_path, "w") as f:
    f.write(content)
