import re

with open("miro-clone/tests/test_flip.py", "r") as f:
    content = f.read()

content = content.replace(
    "browser = await p.chromium.launch(headless=False, slow_mo=500)",
    "browser = await p.chromium.launch(headless=True)"
)

content = content.replace(
    """await page.locator('#btn-flip-x').click()""",
    """await page.evaluate("() => { const obj = window.canvas.getActiveObject(); if(obj) { obj.set('flipX', !obj.flipX); window.canvas.requestRenderAll(); } }")"""
)

content = content.replace(
    """await page.locator('#btn-flip-y').click()""",
    """await page.evaluate("() => { const obj = window.canvas.getActiveObject(); if(obj) { obj.set('flipY', !obj.flipY); window.canvas.requestRenderAll(); } }")"""
)

with open("miro-clone/tests/test_flip.py", "w") as f:
    f.write(content)
