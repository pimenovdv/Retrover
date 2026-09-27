import os
import re

full_path = os.path.join("miro-clone", "tests/test_clear_board.py")
with open(full_path, "r") as f:
    content = f.read()

# Let's inspect test_clear_board.py to see why it hangs.
print(content)
