document.addEventListener("DOMContentLoaded", () => {
    const loginModal = document.getElementById("login-modal");
    const joinBtn = document.getElementById("join-btn");
    const boardIdInput = document.getElementById("board-id-input");
    const nicknameInput = document.getElementById("nickname-input");
    const toolbar = document.getElementById("toolbar");
    const canvasContainer = document.getElementById("canvas-container");
    const chatPanel = document.getElementById("chat-panel");
    const chatInput = document.getElementById("chat-input");
    const chatSend = document.getElementById("chat-send");
    const chatMessages = document.getElementById("chat-messages");
    const cursorsContainer = document.getElementById("cursors-container");

    let activeUsers = {};
    let lastCursorSend = 0;


    let canvas;
    window.canvas = canvas;
    let ws;
    let nickname;
    let boardId = "default";
    let isProcessingSync = false;
    let isUndoRedo = false;
    let undoStack = [];
    let redoStack = [];

    window.undoStack = undoStack;
    window.redoStack = redoStack;

    function pushHistory(actionType, prevData, newData) {
        if (isProcessingSync || isUndoRedo) return;
        undoStack.push({ type: actionType, prev: prevData, next: newData });
        redoStack.length = 0; // Clear redo stack on new action
    }

    function performUndo() {
        if (undoStack.length === 0) return;
        const action = undoStack.pop();
        redoStack.push(action);
        applyAction(action, true);
    }

    function performRedo() {
        if (redoStack.length === 0) return;
        const action = redoStack.pop();
        undoStack.push(action);
        applyAction(action, false);
    }

    window.performUndo = performUndo;
    window.performRedo = performRedo;

    function applyAction(action, isUndo) {
        isUndoRedo = true;

        const state = isUndo ? action.prev : action.next;
        const actionType = action.type;

        if (actionType === 'add') {
            if (isUndo) {
                // Undo an add -> remove
                const obj = getObjectById(action.next.id);
                if (obj) {
                    canvas.remove(obj);
                    ws.send(JSON.stringify({ action: 'remove', object: { id: obj.id } }));
                }
            } else {
                // Redo an add -> add back
                addShapeToCanvas(action.next);
                ws.send(JSON.stringify({ action: 'add', object: action.next }));
            }
        } else if (actionType === 'remove') {
            if (isUndo) {
                // Undo a remove -> add back
                action.prev.forEach(objData => {
                    addShapeToCanvas(objData);
                    ws.send(JSON.stringify({ action: 'add', object: objData }));
                });
            } else {
                // Redo a remove -> remove
                action.prev.forEach(objData => {
                    const obj = getObjectById(objData.id);
                    if (obj) {
                        canvas.remove(obj);
                        ws.send(JSON.stringify({ action: 'remove', object: { id: obj.id } }));
                    }
                });
                canvas.discardActiveObject();
            }
        } else if (actionType === 'modify') {
            // Both undo and redo of modify is just applying the respective state
            const obj = getObjectById(state.id);
            if (obj) {
                obj.set(state);
                obj.setCoords();
                canvas.renderAll();

                // For activeSelection elements we might need matrix transform,
                // but since we save exact state properties, we can just send modify.
                ws.send(JSON.stringify({ action: 'modify', object: state }));
            }
        }

        canvas.renderAll();
        isUndoRedo = false;
    }

    joinBtn.addEventListener("click", () => {
        nickname = nicknameInput.value.trim();
        boardId = boardIdInput.value.trim() || "default";
        if (nickname) {
            loginModal.style.display = "none";
            toolbar.style.display = "flex";
            canvasContainer.style.display = "block";
        document.getElementById("minimap-container").style.display = "block";

            document.getElementById("chat-panel").style.display = "flex";
            initApp();
        }
    });

    function initApp() {

    function getMaxZIndex() {
        const objects = window.canvas ? window.canvas.getObjects() : [];
        if (objects.length === 0) return 0;
        return Math.max(...objects.map(o => o.z_index || 0));
    }

        // Init Fabric Canvas
        canvas = new fabric.Canvas('canvas', {
            width: window.innerWidth,
            height: window.innerHeight,
            backgroundColor: '#f5f5f5'
        });
        window.canvas = canvas;

        // Resize handling

    // --- Minimap Logic ---
    const minimapCanvas = document.getElementById('minimap');
    const minimapViewport = document.getElementById('minimap-viewport');
    const minimapContainer = document.getElementById('minimap-container');
    let minimapCtx = minimapCanvas.getContext('2d');

    function getCanvasBounds() {
        let minX = 0, minY = 0, maxX = canvas.getWidth(), maxY = canvas.getHeight();
        const objects = canvas.getObjects();
        if (objects.length > 0) {
            let first = true;
            objects.forEach(obj => {
                // Ignore cursor objects and similar non-drawing stuff if needed
                const br = obj.getBoundingRect();
                if (first) {
                    minX = br.left;
                    minY = br.top;
                    maxX = br.left + br.width;
                    maxY = br.top + br.height;
                    first = false;
                } else {
                    minX = Math.min(minX, br.left);
                    minY = Math.min(minY, br.top);
                    maxX = Math.max(maxX, br.left + br.width);
                    maxY = Math.max(maxY, br.top + br.height);
                }
            });
            // Add padding
            minX -= 100; minY -= 100; maxX += 100; maxY += 100;
        }
        return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY };
    }

    let minimapScale = 1;
    let minimapOffsetX = 0;
    let minimapOffsetY = 0;
    let minimapBounds = { minX: 0, minY: 0 };

    function updateMinimap() {
        if (!minimapCanvas || !canvas) return;

        minimapCtx.clearRect(0, 0, minimapCanvas.width, minimapCanvas.height);

        const bounds = getCanvasBounds();
        minimapBounds = bounds;

        // Scale to fit bounds in minimap
        const scale = Math.min(minimapCanvas.width / bounds.width, minimapCanvas.height / bounds.height);
        minimapScale = scale;

        const offsetX = (minimapCanvas.width - bounds.width * scale) / 2;
        const offsetY = (minimapCanvas.height - bounds.height * scale) / 2;
        minimapOffsetX = offsetX;
        minimapOffsetY = offsetY;

        minimapCtx.save();
        minimapCtx.translate(offsetX, offsetY);
        minimapCtx.scale(scale, scale);
        minimapCtx.translate(-bounds.minX, -bounds.minY);

        // Render all objects to minimap
        // Draw all objects correctly handling selections
        const activeObj = canvas.getActiveObject();
        canvas.getObjects().forEach(obj => {
            if (obj.visible !== false && (!activeObj || activeObj.type !== 'activeSelection' || !activeObj.contains(obj))) {
                 obj.render(minimapCtx);
            }
        });

        // Render active selection group if it exists
        if (activeObj && activeObj.type === 'activeSelection') {
             activeObj.render(minimapCtx);
        }

        minimapCtx.restore();

        // Calculate viewport indicator box
        const zoom = canvas.getZoom();
        const vpt = canvas.viewportTransform;
        const viewLeft = -vpt[4] / zoom;
        const viewTop = -vpt[5] / zoom;
        const viewWidth = canvas.getWidth() / zoom;
        const viewHeight = canvas.getHeight() / zoom;

        const mapLeft = offsetX + (viewLeft - bounds.minX) * scale;
        const mapTop = offsetY + (viewTop - bounds.minY) * scale;
        const mapWidth = viewWidth * scale;
        const mapHeight = viewHeight * scale;

        minimapViewport.style.left = `${mapLeft}px`;
        minimapViewport.style.top = `${mapTop}px`;
        minimapViewport.style.width = `${mapWidth}px`;
        minimapViewport.style.height = `${mapHeight}px`;
    }

    let isDraggingMinimap = false;

    function handleMinimapEvent(e) {
        if (!isDraggingMinimap && e.type !== 'mousedown' && e.type !== 'touchstart') return;

        const rect = minimapContainer.getBoundingClientRect();
        let x, y;

        if (e.touches && e.touches.length > 0) {
            x = e.touches[0].clientX - rect.left;
            y = e.touches[0].clientY - rect.top;
        } else {
            x = e.clientX - rect.left;
            y = e.clientY - rect.top;
        }

        const absX = (x - minimapOffsetX) / minimapScale + minimapBounds.minX;
        const absY = (y - minimapOffsetY) / minimapScale + minimapBounds.minY;

        const zoom = canvas.getZoom();
        const vpt = canvas.viewportTransform;

        // Update viewport to center on clicked position
        vpt[4] = -(absX * zoom) + (canvas.getWidth() / 2);
        vpt[5] = -(absY * zoom) + (canvas.getHeight() / 2);

        canvas.requestRenderAll();
        updateMinimap();
    }

    minimapContainer.addEventListener('mousedown', (e) => {
        isDraggingMinimap = true;
        handleMinimapEvent(e);
    });

    window.addEventListener('mousemove', (e) => {
        if (isDraggingMinimap) {
            handleMinimapEvent(e);
        }
    });

    window.addEventListener('mouseup', () => {
        isDraggingMinimap = false;
    });

    minimapContainer.addEventListener('touchstart', (e) => {
        isDraggingMinimap = true;
        handleMinimapEvent(e);
        e.preventDefault();
    }, {passive: false});

    window.addEventListener('touchmove', (e) => {
        if (isDraggingMinimap) {
            handleMinimapEvent(e);
            e.preventDefault();
        }
    }, {passive: false});

    window.addEventListener('touchend', () => {
        isDraggingMinimap = false;
    });
    // --- End Minimap Logic ---

        window.addEventListener('resize', () => {
            canvas.setWidth(window.innerWidth);
            canvas.setHeight(window.innerHeight);
            canvas.renderAll();
        });

        // Infinite Canvas: Zoom
        canvas.on('after:render', updateMinimap);
        canvas.on('mouse:wheel', function(opt) {
            var delta = opt.e.deltaY;
            var zoom = canvas.getZoom();
            zoom *= 0.999 ** delta;
            if (zoom > 20) zoom = 20;
            if (zoom < 0.01) zoom = 0.01;
            canvas.zoomToPoint({ x: opt.e.offsetX, y: opt.e.offsetY }, zoom);
            opt.e.preventDefault();
            opt.e.stopPropagation();
        });

        // Infinite Canvas: Pan
        let isDragging = false;
        let lastPosX = 0;
        let lastPosY = 0;

        canvas.on('mouse:down', function(opt) {
            var evt = opt.e;
            if (evt.altKey === true || evt.button === 1) {
                isDragging = true;
                canvas.selection = false;
                lastPosX = evt.clientX;
                lastPosY = evt.clientY;
            }
        });

        canvas.on('mouse:move', function(opt) {
            if (isDragging) {
                var e = opt.e;
                var vpt = canvas.viewportTransform;
                vpt[4] += e.clientX - lastPosX;
                vpt[5] += e.clientY - lastPosY;
                canvas.requestRenderAll();
                lastPosX = e.clientX;
                lastPosY = e.clientY;
            }
        });

        canvas.on('mouse:up', function(opt) {
            canvas.setViewportTransform(canvas.viewportTransform);
            isDragging = false;
            canvas.selection = true;
        });


        // Connect WebSocket
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        ws = new WebSocket(`${protocol}//${window.location.host}/ws/${boardId}/${nickname}`);

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
                handleRemoteUpdate(message.action, message.object, message.sender);
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
            updatePropertiesPanel();
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
            updatePropertiesPanel();
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
            updatePropertiesPanel();
        });


        document.getElementById("btn-line").addEventListener("click", () => {
            const id = uuidv4();
            const vpt = canvas.viewportTransform;
            const x = (canvas.width / 2 - vpt[4]) / vpt[0];
            const y = (canvas.height / 2 - vpt[5]) / vpt[3];

            const line = new fabric.Line([x, y, x + 100, y + 100], {
                stroke: 'black',
                strokeWidth: 5,
                id: id
            });
            canvas.add(line);
            canvas.setActiveObject(line);
            updatePropertiesPanel();
        });

        document.getElementById("btn-arrow").addEventListener("click", () => {
             // simplified arrow as a triangle on a line
             const id = uuidv4();
             const vpt = canvas.viewportTransform;
             const x = (canvas.width / 2 - vpt[4]) / vpt[0];
             const y = (canvas.height / 2 - vpt[5]) / vpt[3];

             const line = new fabric.Line([0, 0, 100, 0], {
                stroke: 'black',
                strokeWidth: 5
             });
             const triangle = new fabric.Triangle({
                width: 20,
                height: 20,
                fill: 'black',
                left: 100,
                top: -10,
                angle: 90
             });
             const group = new fabric.Group([line, triangle], {
                 left: x,
                 top: y,
                 id: id
             });
             canvas.add(group);
             canvas.setActiveObject(group);
        });

        document.getElementById("btn-polygon").addEventListener("click", () => {
             const id = uuidv4();
             const vpt = canvas.viewportTransform;
             const x = (canvas.width / 2 - vpt[4]) / vpt[0];
             const y = (canvas.height / 2 - vpt[5]) / vpt[3];

             const poly = new fabric.Polygon([
                {x: 0, y: 0},
                {x: 50, y: -50},
                {x: 100, y: 0},
                {x: 100, y: 50},
                {x: 0, y: 50}
             ], {
                left: x,
                top: y,
                fill: 'purple',
                id: id
             });
             canvas.add(poly);
             canvas.setActiveObject(poly);
        });

        const btnFreehand = document.getElementById("btn-freehand");
        btnFreehand.addEventListener("click", () => {
             canvas.isDrawingMode = !canvas.isDrawingMode;
             btnFreehand.style.backgroundColor = canvas.isDrawingMode ? '#ccc' : '#f0f0f0';
        });

        // Add ID to freehand paths
        canvas.on('path:created', (e) => {
             const path = e.path;
             path.set({ id: uuidv4() });
             // object:added will fire shortly after this and handle the actual broadcast.
        });


        document.getElementById("btn-group").addEventListener("click", () => {
             if (!canvas.getActiveObject()) return;
             if (canvas.getActiveObject().type !== 'activeSelection') return;

             const group = canvas.getActiveObject().toGroup();
             group.set({ id: uuidv4() });

             // In a real robust system, we would handle nested items better,
             // but for MVP we will remove the individual items from DB and add the group
             group.getObjects().forEach(obj => {
                 ws.send(JSON.stringify({ action: 'remove', object: { id: obj.id } }));
             });
             ws.send(JSON.stringify({ action: 'add', object: group.toObject(['id', 'z_index']) }));

             canvas.requestRenderAll();
        });

        document.getElementById("btn-ungroup").addEventListener("click", () => {
             if (!canvas.getActiveObject()) return;
             if (canvas.getActiveObject().type !== 'group') return;

             const group = canvas.getActiveObject();
             const groupId = group.id;

             // Convert group to activeSelection BEFORE sending updates
             // so they have absolute coordinates in their .left / .top
             const activeSelection = group.toActiveSelection();

             ws.send(JSON.stringify({ action: 'remove', object: { id: groupId } }));

             activeSelection.getObjects().forEach(obj => {
                 if (!obj.id) obj.id = uuidv4();
                 // Now obj.left / obj.top are absolute coordinates
                 ws.send(JSON.stringify({ action: 'add', object: obj.toObject(['id', 'z_index']) }));
             });

             canvas.requestRenderAll();
        });


        document.getElementById("btn-front").addEventListener("click", () => {
             const activeObject = canvas.getActiveObject();
             if (activeObject) {
                 canvas.bringToFront(activeObject);
                 updateZIndices();
             }
        });

        document.getElementById("btn-back").addEventListener("click", () => {
             const activeObject = canvas.getActiveObject();
             if (activeObject) {
                 canvas.sendToBack(activeObject);
                 updateZIndices();
             }
        });

        function updateZIndices() {
             const objects = canvas.getObjects();
             objects.forEach((obj, index) => {
                 if (obj.z_index !== index) {
                     obj.z_index = index;
                     ws.send(JSON.stringify({
                         action: 'modify',
                         object: { id: obj.id, z_index: index }
                     }));
                 }
             });
        }

        document.getElementById("btn-clear").addEventListener("click", () => {
            canvas.discardActiveObject();
            canvas.requestRenderAll();
        });

        // Canvas events -> WebSocket
        canvas.on('object:added', (e) => {
            if (isProcessingSync || isUndoRedo) return;
            const obj = e.target;
            if (!obj.id) obj.id = uuidv4(); // fallback

            const objData = obj.toObject(['id', 'z_index']);
            pushHistory('add', null, objData);

            ws.send(JSON.stringify({
                action: 'add',
                object: objData
            }));
        });

        canvas.on('mouse:down', (e) => {
            if (e.target && e.target.type !== 'activeSelection') {
                e.target._originalState = e.target.toObject(['id', 'z_index']);
            } else if (e.target && e.target.type === 'activeSelection') {
                e.target.getObjects().forEach(o => {
                    o._originalState = o.toObject(['id', 'z_index']);
                });
            }
        });

        canvas.on('object:modified', (e) => {
            if (isProcessingSync || isUndoRedo) return;
            const obj = e.target;

            if (obj.type === 'activeSelection') {
                const activeSelection = canvas.getActiveObject();
                const objs = activeSelection.getObjects();

                // Convert coordinates while keeping selection active
                objs.forEach(function(o) {
                    // Compute absolute coordinates using the active selection's transformation matrix
                    const matrix = o.calcTransformMatrix();
                    const point = fabric.util.qrDecompose(matrix);

                    const newState = {
                        id: o.id,
                        left: point.translateX,
                        top: point.translateY,
                        scaleX: point.scaleX,
                        scaleY: point.scaleY,
                        angle: point.angle
                    };

                    if (o._originalState) {
                        pushHistory('modify', o._originalState, Object.assign({}, o._originalState, newState));
                        o._originalState = null;
                    }

                    ws.send(JSON.stringify({
                        action: 'modify',
                        object: newState
                    }));
                });
            } else {
                const newState = obj.toObject(['id', 'z_index']);
                if (obj._originalState) {
                    pushHistory('modify', obj._originalState, newState);
                    obj._originalState = null;
                }
                ws.send(JSON.stringify({
                    action: 'modify',
                    object: newState
                }));
            }
        });

        // Handle deletion via keyboard

        // Handle drag and drop images
        const canvasContainerEl = document.getElementById("canvas-container");
        canvasContainerEl.addEventListener('dragover', (e) => {
            e.preventDefault();
        });

        canvasContainerEl.addEventListener('drop', (e) => {
            e.preventDefault();
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                const file = e.dataTransfer.files[0];
                uploadAndAddImage(file, e.clientX, e.clientY);
            }
        });

        // Handle paste images
        window.addEventListener('paste', (e) => {
            const items = (e.clipboardData || e.originalEvent.clipboardData).items;
            for (let index in items) {
                const item = items[index];
                if (item.kind === 'file') {
                    const blob = item.getAsFile();
                    // Paste in center of viewport
                    const vpt = canvas.viewportTransform;
                    const centerX = (canvas.width / 2 - vpt[4]) / vpt[0];
                    const centerY = (canvas.height / 2 - vpt[5]) / vpt[3];
                    uploadAndAddImage(blob, centerX, centerY, true);
                }
            }
        });

        async function uploadAndAddImage(file, x, y, isCanvasCoords=false) {
            if (!file.type.startsWith('image/') && file.type !== 'application/pdf') return;

            const formData = new FormData();
            formData.append("file", file);

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();

                let canvasX = x;
                let canvasY = y;

                if (!isCanvasCoords) {
                    const pointer = canvas.getPointer({clientX: x, clientY: y});
                    canvasX = pointer.x;
                    canvasY = pointer.y;
                }

                let urlsToLoad = [];
                if (data.urls) {
                    urlsToLoad = data.urls;
                } else if (data.url) {
                    urlsToLoad = [data.url];
                }

                let currentY = canvasY;

                for (const url of urlsToLoad) {
                    await new Promise((resolve) => {
                        fabric.Image.fromURL(url, (img) => {
                            const id = uuidv4();
                            img.set({
                                id: id,
                                left: canvasX,
                                top: currentY,
                                originX: 'center',
                                originY: 'center',
                                z_index: getMaxZIndex() + 1
                            });

                            // Optional: scale down if image is too large
                            if (img.width > 1000) {
                                img.scaleToWidth(1000);
                            }

                            canvas.add(img);
                            saveState('add', img);

                            // Move Y down for the next page if there is one
                            currentY += (img.height * img.scaleY) + 20; // 20px padding
                            resolve();
                        }, { crossOrigin: 'anonymous' });
                    });
                }

            } catch (err) {
                console.error("Upload failed", err);
            }
        }


        let clipboard = null;

        function copy() {
            if (canvas.getActiveObject()) {
                // Ignore if we are currently editing text
                if (canvas.getActiveObject().isEditing) return;

                canvas.getActiveObject().clone((cloned) => {
                    clipboard = cloned;
                });
            }
        }

        function paste() {
            if (!clipboard) return;
            // Ignore if we are currently editing text
            if (canvas.getActiveObject() && canvas.getActiveObject().isEditing) return;

            clipboard.clone((clonedObj) => {
                canvas.discardActiveObject();
                clonedObj.set({
                    left: clonedObj.left + 10,
                    top: clonedObj.top + 10,
                    evented: true
                });

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
                    clonedObj.set({
                        id: uuidv4(),
                        z_index: getMaxZIndex() + 1
                    });
                    canvas.add(clonedObj);
                    const objData = clonedObj.toObject(['id', 'z_index']);
                    pushHistory('add', null, objData);
                    ws.send(JSON.stringify({
                        action: 'add',
                        object: objData
                    }));
                    canvas.setActiveObject(clonedObj);
                }

                clipboard.top += 10;
                clipboard.left += 10;
                canvas.requestRenderAll();
            });
        }

        window.addEventListener('keydown', (e) => {
             if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') {
                 if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;
                 copy();
                 e.preventDefault();
             } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v') {
                 if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;
                 paste();
                 e.preventDefault();
             } else if (e.key === 'Delete' || e.key === 'Backspace') {
                 // Check if we are editing text, if so don't delete the whole object
                 if (canvas.getActiveObject() && canvas.getActiveObject().isEditing) {
                     return;
                 }

                 const activeObjects = canvas.getActiveObjects();
                 if (activeObjects.length) {
                     const removedObjects = [];
                     activeObjects.forEach(obj => {
                         if (isProcessingSync) return;
                         removedObjects.push(obj.toObject(['id', 'z_index']));
                         ws.send(JSON.stringify({
                             action: 'remove',
                             object: { id: obj.id }
                         }));
                         canvas.remove(obj);
                     });
                     if (removedObjects.length > 0) {
                         pushHistory('remove', removedObjects, null);
                     }
                     canvas.discardActiveObject();
                 }
             } else if (e.key === 'z' && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
                 e.preventDefault();
                 performUndo();
             } else if ((e.key === 'y' && (e.ctrlKey || e.metaKey)) || (e.key === 'z' && (e.ctrlKey || e.metaKey) && e.shiftKey)) {
                 e.preventDefault();
                 performRedo();
             }
        });

        document.getElementById("btn-undo").addEventListener("click", () => {
            performUndo();
        });

        document.getElementById("btn-redo").addEventListener("click", () => {
            performRedo();
        });
    }

    function addShapeToCanvas(shapeData) {
        fabric.util.enlivenObjects([shapeData], (objects) => {
            const origRenderOnAddRemove = canvas.renderOnAddRemove;
            canvas.renderOnAddRemove = false;

            objects.forEach((obj) => {
                if (shapeData.z_index !== undefined) obj.z_index = shapeData.z_index;
                canvas.add(obj);
            });

            canvas.renderOnAddRemove = origRenderOnAddRemove;
            canvas.renderAll();
        });
    }


        // Chat Logic
        chatSend.addEventListener('click', sendChatMessage);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendChatMessage();
        });

        function sendChatMessage() {
            const msg = chatInput.value.trim();
            if (msg && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ action: 'chat', object: { message: msg } }));
                appendChatMessage(nickname, msg);
                chatInput.value = '';
            }
        }

        function appendChatMessage(sender, msg) {
            const div = document.createElement('div');
            div.className = 'chat-message';
            div.innerHTML = `<strong>${sender}</strong> ${msg}`;
            chatMessages.appendChild(div);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // Cursor Logic
        canvas.on('mouse:move', (opt) => {
            if (ws.readyState !== WebSocket.OPEN) return;
            const now = Date.now();
            if (now - lastCursorSend > 50) { // Throttle 20fps
                const pointer = canvas.getPointer(opt.e);
                ws.send(JSON.stringify({
                    action: 'cursor',
                    object: { x: pointer.x, y: pointer.y }
                }));
                lastCursorSend = now;
            }
        });

        canvas.on('after:render', () => {
             // Update all remote cursor positions based on viewport transform
             Object.keys(activeUsers).forEach(user => {
                  const data = activeUsers[user];
                  if (data.cursorEl && data.x !== undefined && data.y !== undefined) {
                      updateCursorDOM(data.cursorEl, data.x, data.y);
                  }
             });
        });

        function updateRemoteCursor(sender, pos) {
            if (!activeUsers[sender]) {
                const color = getRandomColor();
                const el = document.createElement('div');
                el.className = 'remote-cursor';
                el.style.color = color;
                el.innerHTML = `
                    <svg viewBox="0 0 16 16"><path d="M0,0 L16,5 L9,8 L13,15 L10,16 L6,9 L1,14 Z"></path></svg>
                    <div class="remote-cursor-label">${sender}</div>
                `;
                cursorsContainer.appendChild(el);
                activeUsers[sender] = { color: color, cursorEl: el, x: pos.x, y: pos.y };
            }
            activeUsers[sender].x = pos.x;
            activeUsers[sender].y = pos.y;
            updateCursorDOM(activeUsers[sender].cursorEl, pos.x, pos.y);
        }

        function updateCursorDOM(el, x, y) {
            const pt = fabric.util.transformPoint(new fabric.Point(x, y), canvas.viewportTransform);
            el.style.left = pt.x + 'px';
            el.style.top = pt.y + 'px';
        }

        function getRandomColor() {
            const letters = '0123456789ABCDEF';
            let color = '#';
            for (let i = 0; i < 6; i++) {
                color += letters[Math.floor(Math.random() * 16)];
            }
            return color;
        }

        // Selection Logic
        canvas.on('selection:created', handleSelection);
        canvas.on('selection:updated', handleSelection);
        canvas.on('selection:cleared', handleDeselection);

        let currentSelection = [];


    // Properties Panel Logic
    const propertiesPanel = document.getElementById("properties-panel");
    const propFill = document.getElementById("prop-fill");
    const propStroke = document.getElementById("prop-stroke");
    const propStrokeWidth = document.getElementById("prop-stroke-width");
    const propFontFamily = document.getElementById("prop-font-family");

    window.updatePropertiesPanel = function updatePropertiesPanel() {
        const activeObject = canvas.getActiveObject();
        if (!activeObject || activeObject.type === 'activeSelection') {
            propertiesPanel.style.display = 'none';
            return;
        }

        propertiesPanel.style.display = 'flex';

        // Populate current values
        if (activeObject.fill) propFill.value = activeObject.fill;
        if (activeObject.stroke) propStroke.value = activeObject.stroke;
        if (activeObject.strokeWidth !== undefined) propStrokeWidth.value = activeObject.strokeWidth;

        if (activeObject.type === 'i-text' || activeObject.type === 'text') {
            propFontFamily.parentElement.style.display = 'flex';
            if (activeObject.fontFamily) propFontFamily.value = activeObject.fontFamily;
        } else {
            propFontFamily.parentElement.style.display = 'none';
        }
    }

    [propFill, propStroke, propStrokeWidth, propFontFamily].forEach(input => {
        input.addEventListener('change', (e) => {
            const activeObject = canvas.getActiveObject();
            if (!activeObject) return;

            const prop = e.target.id.replace('prop-', '');
            let val = e.target.value;

            if (prop === 'stroke-width') val = parseInt(val, 10);

            const originalState = activeObject.toObject(['id', 'z_index']);

            if (prop === 'fill') activeObject.set('fill', val);
            if (prop === 'stroke') activeObject.set('stroke', val);
            if (prop === 'stroke-width') activeObject.set('strokeWidth', val);
            if (prop === 'font-family') activeObject.set('fontFamily', val);

            const newState = activeObject.toObject(['id', 'z_index']);
            pushHistory('modify', originalState, newState);

            canvas.renderAll();

            ws.send(JSON.stringify({
                action: 'modify',
                object: newState
            }));
        });
    });

function handleSelection(opt) {
            if (isProcessingSync) return;
            const newSelection = opt.selected || [];
            newSelection.forEach(obj => {
                if (obj.id && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ action: 'select', object: { id: obj.id } }));
                }
            });

            // Handle deselected from updated
            const deselected = opt.deselected || [];
            deselected.forEach(obj => {
                if (obj.id && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ action: 'deselect', object: { id: obj.id } }));
                }
            });
            currentSelection = newSelection;
            updatePropertiesPanel();
        }

        function handleDeselection(opt) {
            if (isProcessingSync) return;
            const deselected = opt.deselected || currentSelection || [];
            deselected.forEach(obj => {
                if (obj.id && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ action: 'deselect', object: { id: obj.id } }));
                }
            });
            currentSelection = [];
            propertiesPanel.style.display = "none";
        }

        // Apply property changes
        function applyPropertyChange(propName, value) {
            const activeObj = canvas.getActiveObject();
            if (!activeObj || activeObj.type === 'activeSelection') return;

            let numVal = value;
            if (propName === 'strokeWidth' || propName === 'fontSize') {
                numVal = parseInt(value, 10);
            }

            activeObj.set(propName, numVal);
            canvas.renderAll();
            canvas.fire('object:modified', { target: activeObj });
        }

        propFill.addEventListener('input', (e) => applyPropertyChange('fill', e.target.value));
        propFill.addEventListener('change', (e) => applyPropertyChange('fill', e.target.value));

        propStroke.addEventListener('input', (e) => applyPropertyChange('stroke', e.target.value));
        propStroke.addEventListener('change', (e) => applyPropertyChange('stroke', e.target.value));

        propStrokeWidth.addEventListener('input', (e) => applyPropertyChange('strokeWidth', e.target.value));
        propStrokeWidth.addEventListener('change', (e) => applyPropertyChange('strokeWidth', e.target.value));

        propFontFamily.addEventListener('change', (e) => applyPropertyChange('fontFamily', e.target.value));

        propFontSize.addEventListener('input', (e) => applyPropertyChange('fontSize', e.target.value));
        propFontSize.addEventListener('change', (e) => applyPropertyChange('fontSize', e.target.value));

    function handleRemoteUpdate(action, objData, sender) {
        if (action === "disconnect") {
            if (activeUsers[sender]) {
                if (activeUsers[sender].cursorEl) activeUsers[sender].cursorEl.remove();
                delete activeUsers[sender];
            }
            // Unlock objects this user had selected
            canvas.getObjects().forEach(o => {
                if (o.lockedBy === sender) {
                    delete o.lockedBy;
                    o.selectable = true;
                    o.set('opacity', 1);
                    o.set('stroke', null);
                    o.set('strokeWidth', null);
                }
            });
            canvas.requestRenderAll();
            return;
        }

        if (action === "cursor") {
            updateRemoteCursor(sender, objData);
            return;
        }

        if (action === "chat") {
            appendChatMessage(sender, objData.message);
            return;
        }

        if (action === "select") {
            let o = canvas.getObjects().find(o => o.id === objData.id);
            if (o) {
                o.lockedBy = sender;
                o.selectable = false;
                o.set('opacity', 0.5);
                o.set('stroke', activeUsers[sender]?.color || 'red');
                o.set('strokeWidth', 2);
                canvas.requestRenderAll();
            }
            return;
        }

        if (action === "deselect") {
            let o = canvas.getObjects().find(o => o.id === objData.id);
            if (o && o.lockedBy === sender) {
                delete o.lockedBy;
                o.selectable = true;
                o.set('opacity', 1);
                o.set('stroke', null);
                o.set('strokeWidth', null);
                canvas.requestRenderAll();
            }
            return;
        }

        isProcessingSync = true;

        if (action === 'add') {
             addShapeToCanvas(objData);
        } else if (action === 'modify') {
            const obj = getObjectById(objData.id);
            if (obj) {
                obj.set(objData);
                obj.setCoords();
                if (objData.z_index !== undefined) {
                     canvas.moveTo(obj, objData.z_index);
                }
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
