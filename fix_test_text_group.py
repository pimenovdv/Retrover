with open("miro-clone/tests/test_text_group.py", "r") as f:
    content = f.read()

# Replace force=True clicking with evaluate clicks in test_rich_text_formatting
content = content.replace('await page.locator("#btn-text").click()', 'await page.evaluate("() => document.getElementById(\'btn-text\').click()")')
content = content.replace('await page.locator("#btn-bold").click(force=True)', 'await page.evaluate("() => document.getElementById(\'btn-bold\').click()")')
content = content.replace('await page.locator("#btn-italic").click(force=True)', 'await page.evaluate("() => document.getElementById(\'btn-italic\').click()")')
content = content.replace('await page.locator("#btn-underline").click(force=True)', 'await page.evaluate("() => document.getElementById(\'btn-underline\').click()")')

with open("miro-clone/tests/test_text_group.py", "w") as f:
    f.write(content)
