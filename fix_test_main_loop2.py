import os
import re

full_path = os.path.join("miro-clone", "tests/test_main.py")
with open(full_path, "r") as f:
    content = f.read()

# Let's completely replace the setup_db_sync
def new_fixture():
    return """
@pytest.fixture(autouse=True, scope="function")
def setup_db_sync():
    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_setup())
    yield
    loop.run_until_complete(_teardown())
"""

# replace everything from @pytest.fixture(autouse=True, scope="function") to loop.run_until_complete(_teardown())
content = re.sub(
    r'@pytest\.fixture\(autouse=True, scope="function"\)\ndef setup_db_sync\(\):.*?loop\.run_until_complete\(_teardown\(\)\)',
    new_fixture().strip(),
    content,
    flags=re.DOTALL
)

with open(full_path, "w") as f:
    f.write(content)
