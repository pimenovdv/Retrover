import os

full_path = os.path.join("miro-clone", "tests/test_main.py")
with open(full_path, "r") as f:
    content = f.read()

# Replace the run_until_complete which fails on closed loop
import re
content = re.sub(
    r'try:\n\s*loop = asyncio\.get_event_loop\(\)\n\s*except RuntimeError:\n\s*loop = asyncio\.new_event_loop\(\)\n\s*asyncio\.set_event_loop\(loop\)\n\n\s*loop\.run_until_complete\(_setup\(\)\)',
    'try:\n            loop = asyncio.get_event_loop()\n            if loop.is_closed():\n                loop = asyncio.new_event_loop()\n                asyncio.set_event_loop(loop)\n        except RuntimeError:\n            loop = asyncio.new_event_loop()\n            asyncio.set_event_loop(loop)\n\n        loop.run_until_complete(_setup())',
    content
)

with open(full_path, "w") as f:
    f.write(content)
