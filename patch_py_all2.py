import glob
import re

for file in ["miro-clone/tests/test_templates.py", "miro-clone/tests/test_duplicate.py", "miro-clone/tests/test_responsive.py", "miro-clone/tests/test_clear_board.py", "miro-clone/tests/test_history_panel.py", "miro-clone/tests/test_alignment.py", "miro-clone/tests/test_undo_redo.py"]:
    with open(file, "r") as f:
        content = f.read()

    # Change hardcoded http://127.0.0.1:800x/ to test_server
    content = content.replace('"http://127.0.0.1:8000/"', "test_server")
    content = content.replace('"http://127.0.0.1:8001/"', "test_server")
    content = content.replace('"http://127.0.0.1:8002/"', "test_server")

    with open(file, "w") as f:
        f.write(content)
