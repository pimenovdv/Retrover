import re

with open("miro-clone/tests/test_coverage_main.py", "r") as f:
    content = f.read()

# Fix the test_db_batcher_add_add logic
new_content = re.sub(
    r'db_batcher\.queue\.clear\(\)\n\n    await db_batcher\.push\("add", {"id": "x3"}\)\n    await db_batcher\.push\("add", {"id": "x3", "val": 2}\)',
    r'import uuid\n    id_str = str(uuid.uuid4())\n    db_batcher.queue.clear()\n    await db_batcher.push("add", {"id": id_str})\n    await db_batcher.push("add", {"id": id_str, "val": 2})',
    content
)

new_content = re.sub(
    r'db_batcher\.queue\.clear\(\)\n    await db_batcher\.push\("modify", {"id": "x1", "val": 1}\)\n    await db_batcher\.push\("remove", {"id": "x1"}\)\n    await db_batcher\.push\("remove", {"id": "x2"}\)',
    r'import uuid\n    id1 = str(uuid.uuid4())\n    id2 = str(uuid.uuid4())\n    db_batcher.queue.clear()\n    await db_batcher.push("modify", {"id": id1, "val": 1})\n    await db_batcher.push("remove", {"id": id1})\n    await db_batcher.push("remove", {"id": id2})',
    new_content
)

with open("miro-clone/tests/test_coverage_main.py", "w") as f:
    f.write(new_content)
