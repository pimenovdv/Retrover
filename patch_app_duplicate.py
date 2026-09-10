with open("miro-clone/static/app.js", "r") as f:
    content = f.read()

# Remove the trailing `window.updatePropertiesPanel = updatePropertiesPanel;` which causes the JS error
content = content.replace("window.updatePropertiesPanel = updatePropertiesPanel;\n", "")

with open("miro-clone/static/app.js", "w") as f:
    f.write(content)
