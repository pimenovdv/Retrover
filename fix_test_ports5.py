import os

files_to_fix = [
    "tests/test_text_align.py",
    "tests/test_sticky.py",
    "tests/test_responsive.py",
]

for file_path in files_to_fix:
    full_path = os.path.join("miro-clone", file_path)
    with open(full_path, "r") as f:
        content = f.read()

    # fix the bad replacement quotes
    content = content.replace('yield "f"http://127.0.0.1:{port}""', 'port = server.config.port\n    yield f"http://127.0.0.1:{port}"')
    content = content.replace('yield f"http://127.0.0.1:{port}"', 'port = server.config.port\n    yield f"http://127.0.0.1:{port}"') # in case
    content = content.replace('yield f"http://127.0.0.1:{port}"', 'yield f"http://127.0.0.1:{port}"')
    content = content.replace('await page.goto("f"http://127.0.0.1:{port}"")', 'await page.goto(test_server)')
    content = content.replace('await page.goto(f"http://127.0.0.1:{port}")', 'await page.goto(test_server)')
    content = content.replace('page.goto("f"http://127.0.0.1:{port}"")', 'page.goto(test_server)')

    with open(full_path, "w") as f:
        f.write(content)
