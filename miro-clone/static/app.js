document.addEventListener("DOMContentLoaded", () => {
    const loginModal = document.getElementById("login-modal");
    const joinBtn = document.getElementById("join-btn");
    const nicknameInput = document.getElementById("nickname-input");
    const toolbar = document.getElementById("toolbar");
    const canvasContainer = document.getElementById("canvas-container");

    let canvas;
    let ws;
    let nickname;
    let isProcessingSync = false;

    joinBtn.addEventListener("click", () => {
        nickname = nicknameInput.value.trim();
        if (nickname) {
            loginModal.style.display = "none";
            toolbar.style.display = "flex";
            canvasContainer.style.display = "block";
            initApp();
        }
    });

    function initApp() {
        // Init Fabric Canvas
        canvas = new fabric.Canvas('canvas', {
            width: window.innerWidth,
            height: window.innerHeight,
            backgroundColor: '#f5f5f5'
        });

        // Resize handling
        window.addEventListener('resize', () => {
            canvas.setWidth(window.innerWidth);
            canvas.setHeight(window.innerHeight);
            canvas.renderAll();
        });

        // Connect WebSocket
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(`${protocol}//${window.location.host}/ws/${nickname}`);

        ws.onopen = () => {
            console.log("Connected to WS");
        };

        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);

            if (message.type === "init") {
                // Load existing shapes
                isProcessingSync = true;
                message.data.forEach(shapeData => {
                    addShapeToCanvas(shapeData);
                });
                isProcessingSync = false;
            } else if (message.type === "update") {
                handleRemoteUpdate(message.action, message.object);
            }
        };

        // Toolbar actions
        document.getElementById("btn-rect").addEventListener("click", () => {
            const id = uuidv4();
            const rect = new fabric.Rect({
                left: 100,
                top: 100,
                fill: 'red',
                width: 100,
                height: 100,
                id: id
            });
            canvas.add(rect);
            canvas.setActiveObject(rect);
        });

        document.getElementById("btn-circle").addEventListener("click", () => {
            const id = uuidv4();
            const circle = new fabric.Circle({
                radius: 50,
                fill: 'green',
                left: 200,
                top: 200,
                id: id
            });
            canvas.add(circle);
            canvas.setActiveObject(circle);
        });

        document.getElementById("btn-text").addEventListener("click", () => {
            const id = uuidv4();
            const text = new fabric.IText('Hello World', {
                left: 300,
                top: 300,
                fontSize: 40,
                fill: 'blue',
                id: id
            });
            canvas.add(text);
            canvas.setActiveObject(text);
        });

        document.getElementById("btn-clear").addEventListener("click", () => {
            canvas.discardActiveObject();
            canvas.requestRenderAll();
        });

        // Canvas events -> WebSocket
        canvas.on('object:added', (e) => {
            if (isProcessingSync) return;
            const obj = e.target;
            if (!obj.id) obj.id = uuidv4(); // fallback

            ws.send(JSON.stringify({
                action: 'add',
                object: obj.toObject(['id'])
            }));
        });

        canvas.on('object:modified', (e) => {
            if (isProcessingSync) return;
            const obj = e.target;
            ws.send(JSON.stringify({
                action: 'modify',
                object: obj.toObject(['id'])
            }));
        });

        // Handle deletion via keyboard
        window.addEventListener('keydown', (e) => {
             if (e.key === 'Delete' || e.key === 'Backspace') {
                 // Check if we are editing text, if so don't delete the whole object
                 if (canvas.getActiveObject() && canvas.getActiveObject().isEditing) {
                     return;
                 }

                 const activeObjects = canvas.getActiveObjects();
                 if (activeObjects.length) {
                     activeObjects.forEach(obj => {
                         if (isProcessingSync) return;
                         ws.send(JSON.stringify({
                             action: 'remove',
                             object: { id: obj.id }
                         }));
                         canvas.remove(obj);
                     });
                     canvas.discardActiveObject();
                 }
             }
        });
    }

    function addShapeToCanvas(shapeData) {
        fabric.util.enlivensObjects([shapeData], (objects) => {
            const origRenderOnAddRemove = canvas.renderOnAddRemove;
            canvas.renderOnAddRemove = false;

            objects.forEach((obj) => {
                canvas.add(obj);
            });

            canvas.renderOnAddRemove = origRenderOnAddRemove;
            canvas.renderAll();
        });
    }

    function handleRemoteUpdate(action, objData) {
        isProcessingSync = true;

        if (action === 'add') {
             addShapeToCanvas(objData);
        } else if (action === 'modify') {
            const obj = getObjectById(objData.id);
            if (obj) {
                obj.set(objData);
                obj.setCoords();
                canvas.renderAll();
            } else {
                // Object not found, add it
                addShapeToCanvas(objData);
            }
        } else if (action === 'remove') {
            const obj = getObjectById(objData.id);
            if (obj) {
                canvas.remove(obj);
            }
        }

        isProcessingSync = false;
    }

    function getObjectById(id) {
        return canvas.getObjects().find(obj => obj.id === id);
    }
});
