with open("miro-clone/static/app.js", "r") as f:
    code = f.read()

# Make chat panel visible on join
code = code.replace(
    'canvasContainer.style.display = "block";',
    'canvasContainer.style.display = "block";\n            document.getElementById("chat-panel").style.display = "flex";'
)

# Insert new global variables for cursors and chat
js_vars = """    const chatPanel = document.getElementById("chat-panel");
    const chatInput = document.getElementById("chat-input");
    const chatSend = document.getElementById("chat-send");
    const chatMessages = document.getElementById("chat-messages");
    const cursorsContainer = document.getElementById("cursors-container");

    let activeUsers = {};
    let lastCursorSend = 0;
"""

code = code.replace(
    'const canvasContainer = document.getElementById("canvas-container");',
    'const canvasContainer = document.getElementById("canvas-container");\n' + js_vars
)

with open("miro-clone/static/app.js", "w") as f:
    f.write(code)
