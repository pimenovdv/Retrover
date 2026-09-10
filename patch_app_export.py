with open("miro-clone/static/app.js", "r") as f:
    content = f.read()

# I removed the ONLY export of updatePropertiesPanel globally (`window.updatePropertiesPanel = updatePropertiesPanel;`)
# Now the test throws TypeError: window.updatePropertiesPanel is not a function.
# I need to re-add it, but INSIDE initApp() or right AFTER function updatePropertiesPanel() { ... }

search = """        } else {
            propFontFamily.parentElement.style.display = 'none';
            if (propFontSize) propFontSize.parentElement.style.display = 'none';
            propTextFormats.style.display = 'none';
            const propTextAlign = document.getElementById("prop-text-align");
            if (propTextAlign) propTextAlign.style.display = 'none';
        }
    }"""

replace = search + """
    window.updatePropertiesPanel = updatePropertiesPanel;"""

if search in content:
    content = content.replace(search, replace, 1)
    with open("miro-clone/static/app.js", "w") as f:
        f.write(content)
    print("Patched!")
else:
    print("Search string not found!")
