with open('miro-clone/static/index.html', 'r') as f:
    content = f.read()

search = """        <div class="prop-group" id="prop-text-formats" style="display: none;">
            <label>Format</label>
            <div style="display: flex; gap: 5px;">
                <button id="btn-bold" style="font-weight: bold;">B</button>
                <button id="btn-italic" style="font-style: italic;">I</button>
                <button id="btn-underline" style="text-decoration: underline;">U</button>
            </div>
        </div>
        <div class="prop-group">
            <label for="prop-angle">Rotation</label>"""

replace = """        <div class="prop-group" id="prop-text-formats" style="display: none;">
            <label>Format</label>
            <div style="display: flex; gap: 5px;">
                <button id="btn-bold" style="font-weight: bold;">B</button>
                <button id="btn-italic" style="font-style: italic;">I</button>
                <button id="btn-underline" style="text-decoration: underline;">U</button>
            </div>
        </div>
        <div class="prop-group" id="prop-text-align" style="display: none;">
            <label>Align</label>
            <div style="display: flex; gap: 5px;">
                <button id="btn-align-text-left" style="font-weight: bold;">L</button>
                <button id="btn-align-text-center" style="font-weight: bold;">C</button>
                <button id="btn-align-text-right" style="font-weight: bold;">R</button>
                <button id="btn-align-text-justify" style="font-weight: bold;">J</button>
            </div>
        </div>
        <div class="prop-group">
            <label for="prop-angle">Rotation</label>"""

if search in content:
    content = content.replace(search, replace)
    with open('miro-clone/static/index.html', 'w') as f:
        f.write(content)
    print("HTML PATCHED!")
else:
    print("HTML SEARCH NOT FOUND!")
