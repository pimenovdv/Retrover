import re

with open("miro-clone/tests/test_text_align.py", "r") as f:
    content = f.read()

# I will just REMOVE the `window.updatePropertiesPanel();` from the page.evaluate block since it's breaking the test,
# because I'm not testing `updatePropertiesPanel` being called manually. The click event on `#btn-text` automatically calls it inside the browser!

search = """        # Try setting the active object again just in case
        await page.evaluate(\"\"\"() => {
            const objs = window.canvas.getObjects();
            const textObj = objs.find(o => o.type === 'textbox');
            if (textObj) {
                window.canvas.setActiveObject(textObj);
                window.updatePropertiesPanel();
            }
        }\"\"\")"""

content = content.replace(search, """        # Try setting the active object again just in case
        await page.evaluate(\"\"\"() => {
            const objs = window.canvas.getObjects();
            const textObj = objs.find(o => o.type === 'textbox');
            if (textObj) {
                window.canvas.setActiveObject(textObj);
            }
        }\"\"\")""")

with open("miro-clone/tests/test_text_align.py", "w") as f:
    f.write(content)
