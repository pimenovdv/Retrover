with open("miro-clone/static/app.js", "r") as f:
    content = f.read()

# Wait... in my previous `git checkout HEAD static/app.js` I LOST all the `initApp` logic!
# Including `window.updatePropertiesPanel = updatePropertiesPanel;` if it wasn't there initially.
# But wait, looking at `app.js` line 2055, `window.updatePropertiesPanel = updatePropertiesPanel;` is right there inside `initApp()`!
# Why does `window.updatePropertiesPanel is not a function`?
# Is it because `initApp()` is never finishing because of a crash?
