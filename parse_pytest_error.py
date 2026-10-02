import re

with open('pytest_output.txt', 'w') as f:
    f.write("""AssertionError: Expected #ff0000 or rgb(255,0,0), got #000000
assert '#000000' in ['#ff0000', 'rgb(255,0,0)']""")
