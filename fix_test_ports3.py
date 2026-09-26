import os

files_to_fix = [
    "tests/test_text_group.py",
    "tests/test_zoom.py",
]

for file_path in files_to_fix:
    full_path = os.path.join("miro-clone", file_path)
    with open(full_path, "r") as f:
        content = f.read()

    # fix the name error
    content = content.replace('await page.goto(f"http://127.0.0.1:{port}")', 'await page.goto(test_server)')
    # Fix the missing yielding format in test_server
    content = content.replace('yield server', 'port = server.config.port\n    yield f"http://127.0.0.1:{port}"')

    with open(full_path, "w") as f:
        f.write(content)
