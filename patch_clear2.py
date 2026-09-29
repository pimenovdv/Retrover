with open("miro-clone/tests/test_clear_board.py", "r") as f:
    content = f.read()

content = content.replace("yield server", "yield f\"http://127.0.0.1:{port}\"")

with open("miro-clone/tests/test_clear_board.py", "w") as f:
    f.write(content)
