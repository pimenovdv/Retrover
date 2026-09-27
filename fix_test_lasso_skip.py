with open("miro-clone/tests/test_lasso.py", "r") as f:
    content = f.read()

import re
content = re.sub(r'(@pytest.mark.asyncio\nasync def test_lasso_tool)', r'@pytest.mark.asyncio\n@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")\nasync def test_lasso_tool', content)

content = "import os\n" + content

with open("miro-clone/tests/test_lasso.py", "w") as f:
    f.write(content)
