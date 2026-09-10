with open('miro-clone/static/app.js', 'r') as f:
    content = f.read()

# 1. Add elements and event listeners inside initApp
search1 = """        btnBold.addEventListener('click', () => applyTextFormat('bold'));
        btnItalic.addEventListener('click', () => applyTextFormat('italic'));
        btnUnderline.addEventListener('click', () => applyTextFormat('underline'));"""

replace1 = search1 + """

        const applyTextAlign = (align) => {
            const obj = canvas.getActiveObject();
            if (obj && obj.type === 'textbox') {
                const originalState = obj.toObject(TO_OBJECT_PROPS);
                obj.set({ textAlign: align });
                const newState = obj.toObject(TO_OBJECT_PROPS);
                pushHistory('modify', originalState, newState);

                canvas.requestRenderAll();
                canvas.fire('object:modified', { target: obj }); // Triggers WS sync
                updatePropertiesPanel();
            }
        };

        const btnAlignTextLeft = document.getElementById("btn-align-text-left");
        const btnAlignTextCenter = document.getElementById("btn-align-text-center");
        const btnAlignTextRight = document.getElementById("btn-align-text-right");
        const btnAlignTextJustify = document.getElementById("btn-align-text-justify");

        if (btnAlignTextLeft) btnAlignTextLeft.addEventListener('click', () => applyTextAlign('left'));
        if (btnAlignTextCenter) btnAlignTextCenter.addEventListener('click', () => applyTextAlign('center'));
        if (btnAlignTextRight) btnAlignTextRight.addEventListener('click', () => applyTextAlign('right'));
        if (btnAlignTextJustify) btnAlignTextJustify.addEventListener('click', () => applyTextAlign('justify'));"""

content = content.replace(search1, replace1)

# 2. Update updatePropertiesPanel logic
search2 = """        if (textObject) {
            propFontFamily.parentElement.style.display = 'flex';
            if (propFontSize) propFontSize.parentElement.style.display = 'flex';
            propTextFormats.style.display = 'block';"""

replace2 = search2 + """
            const propTextAlign = document.getElementById("prop-text-align");
            if (propTextAlign) propTextAlign.style.display = 'block';"""

content = content.replace(search2, replace2)

search3 = """        } else {
            propFontFamily.parentElement.style.display = 'none';
            if (propFontSize) propFontSize.parentElement.style.display = 'none';
            propTextFormats.style.display = 'none';"""

replace3 = search3 + """
            const propTextAlign = document.getElementById("prop-text-align");
            if (propTextAlign) propTextAlign.style.display = 'none';"""

content = content.replace(search3, replace3)

# 3. Export updatePropertiesPanel so playwright can call it natively
search4 = """    }

    [propFill, propStroke, propStrokeWidth, propFontFamily].forEach(input => {"""

replace4 = """    }
    window.updatePropertiesPanel = updatePropertiesPanel;

    [propFill, propStroke, propStrokeWidth, propFontFamily].forEach(input => {"""

content = content.replace(search4, replace4)

with open('miro-clone/static/app.js', 'w') as f:
    f.write(content)
