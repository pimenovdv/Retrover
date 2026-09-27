import os
import re

full_path = os.path.join("miro-clone", "tests/test_minimap.py")
with open(full_path, "r") as f:
    content = f.read()

import uuid
content = content.replace('"test_board"', f'"test_board_{uuid.uuid4().hex[:8]}"')

with open(full_path, "w") as f:
    f.write(content)
