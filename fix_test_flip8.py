import re

with open("miro-clone/tests/test_flip.py", "r") as f:
    content = f.read()

content = content.replace(
    "page.on(\"console\", lambda msg: print(f\"Browser console: {msg.text}\"))",
    ""
)

with open("miro-clone/tests/test_flip.py", "w") as f:
    f.write(content)
