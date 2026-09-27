import os

full_path = os.path.join("miro-clone", "tests/test_lock.py")
with open(full_path, "r") as f:
    content = f.read()

content = content.replace(
'''        page.goto(f"http://127.0.0.1:{test_server}/")
        page.fill("#board-id-input", f"board_{uuid.uuid4().hex[:8]}")
        page.wait_for_selector("#login-modal", state="visible")''',
'''        page.goto(f"http://127.0.0.1:{test_server}/")
        page.wait_for_selector("#login-modal", state="visible")
        page.fill("#board-id-input", f"board_{uuid.uuid4().hex[:8]}")'''
)

with open(full_path, "w") as f:
    f.write(content)
