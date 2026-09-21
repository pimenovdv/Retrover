import re
with open("miro-clone/tests/test_copy_paste.py", "r") as f:
    content = f.read()

# Generate a new unique board id for the test to avoid collisions
content = content.replace(
    'page.fill("#board-id-input", "copy_paste_board")',
    'page.fill("#board-id-input", f"copy_paste_board_{uuid.uuid4()}")'
)

# And clear the board first to be safe
content = content.replace(
    'page.wait_for_selector("#canvas-container", state="visible")',
    'page.wait_for_selector("#canvas-container", state="visible")\n        page.evaluate("""() => {\n            window.canvas.clear();\n        }""")\n'
)

with open("miro-clone/tests/test_copy_paste.py", "w") as f:
    f.write(content)
