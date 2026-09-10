import re

with open("miro-clone/static/app.js", "r") as f:
    content = f.read()

# Make window.updatePropertiesPanel accessible globally by assigning it on window object INSIDE the function itself is fine,
# BUT if it's evaluated inside DOMContentLoaded and DOMContentLoaded hasn't finished, it won't exist globally until DOMContentLoaded finishes.
# But Playwright waits for `canvas !== undefined`, which happens during `initApp`. `window.updatePropertiesPanel = updatePropertiesPanel;` is inside `initApp`.
# Wait, why is it throwing `updatePropertiesPanel is not a function` in the browser context?
# Because `window.updatePropertiesPanel = updatePropertiesPanel` assigns it globally, but IF there is a Javascript runtime error during DOMContentLoaded BEFORE line 2055, `updatePropertiesPanel` is NEVER assigned to `window`!
