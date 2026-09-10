import re

with open('miro-clone/static/app.js', 'r') as f:
    content = f.read()

content = content.replace("window.updatePropertiesPanel = function updatePropertiesPanel() {", "function updatePropertiesPanel() {")

with open('miro-clone/static/app.js', 'w') as f:
    f.write(content)

print("Fixed updatePropertiesPanel hoisting!")
