with open("miro-clone/static/index.html", "r") as f:
    code = f.read()

chat_html = """    <!-- Chat Panel -->
    <div id="chat-panel" style="display: none;">
        <div id="chat-messages"></div>
        <div id="chat-input-container">
            <input type="text" id="chat-input" placeholder="Type a message..." />
            <button id="chat-send">Send</button>
        </div>
    </div>

    <!-- Cursors Container -->
    <div id="cursors-container"></div>
"""

# Insert before <script src="/static/app.js"></script>
code = code.replace("    <script src=\"/static/app.js\"></script>", chat_html + "    <script src=\"/static/app.js\"></script>")

with open("miro-clone/static/index.html", "w") as f:
    f.write(code)
