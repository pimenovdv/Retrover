import re

with open("miro-clone/tests/test_flip.py", "r") as f:
    content = f.read()

content = content.replace(
    "browser = await p.chromium.launch(headless=True, args=['--enable-logging', '--v=1'])",
    "browser = await p.chromium.launch(headless=False, slow_mo=500)"
)
with open("miro-clone/tests/test_flip.py", "w") as f:
    f.write(content)
