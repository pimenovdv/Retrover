import os

full_path = os.path.join("miro-clone", "tests/test_sticky.py")
with open(full_path, "r") as f:
    content = f.read()

content = content.replace('page.goto(test_server)', 'page.goto(app_server)')

with open(full_path, "w") as f:
    f.write(content)
