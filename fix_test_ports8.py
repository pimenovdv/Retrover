import os

full_path = os.path.join("miro-clone", "tests/test_sticky.py")
with open(full_path, "r") as f:
    content = f.read()

content = content.replace('yield\n', 'yield f"http://127.0.0.1:{port}"\n')

with open(full_path, "w") as f:
    f.write(content)
