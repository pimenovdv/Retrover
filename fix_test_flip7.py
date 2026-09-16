import re

with open("miro-clone/tests/test_flip.py", "r") as f:
    content = f.read()

content = content.replace(
    """await page.evaluate("() => { const obj = window.canvas.getActiveObject(); if(obj) { obj.set('flipX', !obj.flipX); window.canvas.requestRenderAll(); } }")""",
    """await page.locator('#btn-flip-x').click()"""
)

content = content.replace(
    """await page.evaluate("() => { const obj = window.canvas.getActiveObject(); if(obj) { obj.set('flipY', !obj.flipY); window.canvas.requestRenderAll(); } }")""",
    """await page.locator('#btn-flip-y').click()"""
)

with open("miro-clone/tests/test_flip.py", "w") as f:
    f.write(content)
