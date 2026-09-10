with open('miro-clone/static/app.js', 'r') as f:
    content = f.read()

# 1. Add elements and event listeners inside initApp
search1 = """        btnBold.addEventListener('click', () => applyTextFormat('bold'));
        btnItalic.addEventListener('click', () => applyTextFormat('italic'));
        btnUnderline.addEventListener('click', () => applyTextFormat('underline'));"""

replace1 = search1 + """

        const propTextAlign = document.getElementById("prop-text-align");
        const btnAlignTextLeft = document.getElementById("btn-align-text-left");
        const btnAlignTextCenter = document.getElementById("btn-align-text-center");
        const btnAlignTextRight = document.getElementById("btn-align-text-right");
        const btnAlignTextJustify = document.getElementById("btn-align-text-justify");

        const applyTextAlign = (align) => {
            const obj = canvas.getActiveObject();
            if (obj && obj.type === 'textbox') {
                const originalState = obj.toObject(TO_OBJECT_PROPS);
                obj.set({ textAlign: align });
                const newState = obj.toObject(TO_OBJECT_PROPS);
                pushHistory('modify', originalState, newState);

                canvas.requestRenderAll();
                canvas.fire('object:modified', { target: obj }); // Triggers WS sync

                // Keep the property panel visible since original function hides it
                if (propTextAlign) propTextAlign.style.display = 'block';
            }
        };

        if (btnAlignTextLeft) btnAlignTextLeft.addEventListener('click', () => applyTextAlign('left'));
        if (btnAlignTextCenter) btnAlignTextCenter.addEventListener('click', () => applyTextAlign('center'));
        if (btnAlignTextRight) btnAlignTextRight.addEventListener('click', () => applyTextAlign('right'));
        if (btnAlignTextJustify) btnAlignTextJustify.addEventListener('click', () => applyTextAlign('justify'));"""

content = content.replace(search1, replace1)

with open('miro-clone/static/app.js', 'w') as f:
    f.write(content)

print("APP PATCHED!")
