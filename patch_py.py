import re

with open("miro-clone/tests/test_coverage_main.py", "r") as f:
    code = f.read()

code = code.replace(") as ws:\n                    pass", "):\n                    pass")

with open("miro-clone/tests/test_coverage_main.py", "w") as f:
    f.write(code)
