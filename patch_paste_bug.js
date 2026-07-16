const fs = require('fs');
let code = fs.readFileSync('miro-clone/static/app.js', 'utf8');

const targetStr = `
                if (clonedObj.type === 'activeSelection') {
                    clonedObj.canvas = canvas;
                    clonedObj.forEachObject((obj) => {
                        const matrix = obj.calcTransformMatrix();
                        const point = fabric.util.qrDecompose(matrix);

                        obj.set({
                            left: point.translateX,
                            top: point.translateY,
                            scaleX: point.scaleX,
                            scaleY: point.scaleY,
                            angle: point.angle,
                            id: uuidv4(),
                            z_index: getMaxZIndex() + 1
                        });

                        canvas.add(obj);
                        const objData = obj.toObject(['id', 'z_index']);
                        pushHistory('add', null, objData);
                        ws.send(JSON.stringify({
                            action: 'add',
                            object: objData
                        }));
                    });
                    clonedObj.setCoords();
                    canvas.setActiveObject(clonedObj);
                } else {
`;

const replaceStr = `
                if (clonedObj.type === 'activeSelection') {
                    clonedObj.canvas = canvas;
                    clonedObj.forEachObject((obj) => {
                        obj.set({
                            id: uuidv4(),
                            z_index: getMaxZIndex() + 1
                        });
                        canvas.add(obj);

                        const matrix = obj.calcTransformMatrix();
                        const point = fabric.util.qrDecompose(matrix);

                        const objData = obj.toObject(['id', 'z_index']);
                        // Overwrite with absolute coordinates for websocket
                        objData.left = point.translateX;
                        objData.top = point.translateY;
                        objData.scaleX = point.scaleX;
                        objData.scaleY = point.scaleY;
                        objData.angle = point.angle;

                        pushHistory('add', null, objData);
                        ws.send(JSON.stringify({
                            action: 'add',
                            object: objData
                        }));
                    });
                    clonedObj.setCoords();
                    canvas.setActiveObject(clonedObj);
                } else {
`;

code = code.replace(targetStr, replaceStr);


// Fix dangling else
code = code.replace(`
             } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v') {
                 if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;
                 paste();
                 e.preventDefault();
             } else

             if (e.key === 'Delete' || e.key === 'Backspace') {
`, `
             } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v') {
                 if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;
                 paste();
                 e.preventDefault();
             } else if (e.key === 'Delete' || e.key === 'Backspace') {
`);

fs.writeFileSync('miro-clone/static/app.js', code);
