import os

full_path = os.path.join("miro-clone", "tests/test_lock.py")
with open(full_path, "r") as f:
    content = f.read()

content = content.replace("browser = p.chromium.launch()", "browser = p.chromium.launch(headless=True)")

with open(full_path, "w") as f:
    f.write(content)
