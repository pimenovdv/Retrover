import re

with open("miro-clone/tests/test_text_align.py", "r") as f:
    content = f.read()

# Add logic to actually trigger updatePropertiesPanel in page evaluate after setActiveObject
# Actually wait... the problem might be that the text object isn't actually selected properly by `await page.click("#btn-text")` because when you click a button it loses focus.
# `updatePropertiesPanel` hides the panel if there is NO active object.
# Look at the error: waiting for locator("#properties-panel") to be visible
# 21 × locator resolved to hidden <div id="properties-panel">…</div>
# Panel state before: `{'propTextAlignExists': True, 'propTextAlignDisplay': 'none', 'btnRightExists': True, 'btnRightDisplay': '', 'panelDisplay': 'none'}`
# Panel state after manual update: `{'propTextAlignDisplay': 'none', 'propertiesPanelClass': 'hidden'}` -> WAIT propertiesPanelClass is "hidden"?!
