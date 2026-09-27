import os
import re

full_path = os.path.join("miro-clone", "tests/test_line_thickness.py")
with open(full_path, "r") as f:
    content = f.read()

# Fix timeout error where it tries to fill register before logging in / waiting for modal
content = content.replace('await page.goto(test_server)', 'await page.goto(test_server)\n        await page.wait_for_selector("#login-modal", state="visible")')
content = content.replace('await page.fill("#board-id-input", "test-board")', 'await page.fill("#board-id-input", f"test-board-{uuid.uuid4().hex[:8]}")')

with open(full_path, "w") as f:
    f.write(content)
