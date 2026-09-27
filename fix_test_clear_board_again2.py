import os
import re

full_path = os.path.join("miro-clone", "tests/test_clear_board.py")
with open(full_path, "r") as f:
    content = f.read()

# Ah it says "server" instead of "server.should_exit = True \n thread.join()"
content = content.replace("yield f\"http://127.0.0.1:{port}\"\n    \n    server\n\n\n@pytest.mark.asyncio", "yield f\"http://127.0.0.1:{port}\"\n    server.should_exit = True\n    thread.join()\n\n\n@pytest.mark.asyncio")

with open(full_path, "w") as f:
    f.write(content)
