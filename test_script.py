import re

with open('miro-clone/static/app.js', 'r') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'canvas.freeDrawingBrush.color = propStroke ? propStroke.value : \'' in line:
        print(f"Line {i+1}: {line.strip()}")
