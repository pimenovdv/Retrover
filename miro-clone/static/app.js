document.addEventListener("DOMContentLoaded", () => {
    const loginModal = document.getElementById("login-modal");
    const registerBtn = document.getElementById("register-btn");
    const loginBtn = document.getElementById("login-btn");
    const passwordInput = document.getElementById("password-input");
    const authError = document.getElementById("auth-error");
    const boardIdInput = document.getElementById("board-id-input");
    const nicknameInput = document.getElementById("nickname-input");

    // Check URL parameters for board ID
    const urlParams = new URLSearchParams(window.location.search);
    const urlBoardId = urlParams.get('board');
    if (urlBoardId) {
        boardIdInput.value = urlBoardId;
    }
    const toolbar = document.getElementById("toolbar");
    const canvasContainer = document.getElementById("canvas-container");
    const chatPanel = document.getElementById("chat-panel");
    const chatInput = document.getElementById("chat-input");
    const chatSend = document.getElementById("chat-send");
    const chatMessages = document.getElementById("chat-messages");
    const cursorsContainer = document.getElementById("cursors-container");

    let activeUsers = {};
    let lastCursorSend = 0;
    let lastLaserSend = 0;


    const TO_OBJECT_PROPS = ['id', 'z_index', 'globalCompositeOperation', 'selectable', 'evented', 'is_background', 'locked', 'lockMovementX', 'lockMovementY', 'lockRotation', 'lockScalingX', 'lockScalingY', 'hasControls'];
    window.TO_OBJECT_PROPS = TO_OBJECT_PROPS;

    let canvas;
    window.canvas = canvas;
    let ws;
    let nickname;
    let boardId = "default";
    let isProcessingSync = false;
    let canEdit = true;
    let isOwner = false;
    let isUndoRedo = false;
    let undoStack = [];
    let redoStack = [];
    let isEraserMode = false;
    let isLaserMode = false;

    window.isEraserMode = isEraserMode;
    window.isLaserMode = isLaserMode;
    window.undoStack = undoStack;
    window.redoStack = redoStack;

    function pushHistory(actionType, prevData, newData) {
        if (isProcessingSync || isUndoRedo) return;
        undoStack.push({ type: actionType, prev: prevData, next: newData });
        redoStack.length = 0; // Clear redo stack on new action
        updateHistoryPanel();
    }

    function performUndo() {
        if (undoStack.length === 0) return;
        const action = undoStack.pop();
        redoStack.push(action);
        applyAction(action, true);
        updateHistoryPanel();
    }

    function performRedo() {
        if (redoStack.length === 0) return;
        const action = redoStack.pop();
        undoStack.push(action);
        applyAction(action, false);
        updateHistoryPanel();
    }

    window.performUndo = performUndo;
    window.performRedo = performRedo;

    function updateHistoryPanel() {
        const historyList = document.getElementById("history-list");
        if (!historyList) return;
        historyList.innerHTML = "";

        // Combine undo and redo stacks for a full view (optional, but requested recent actions)
        // Let's just show undoStack to keep it simple, or both
        let allActions = [...undoStack];

        // Show last 20 actions
        const recentActions = allActions.slice(-20).reverse();

        recentActions.forEach((action, index) => {
            const li = document.createElement("li");
            let desc = "Action: " + action.type;
            if (action.next && action.next.type) {
                desc += " (" + action.next.type + ")";
            } else if (action.prev && action.prev.type) {
                desc += " (" + action.prev.type + ")";
            }
            li.textContent = desc;
            historyList.appendChild(li);
        });
    }

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

    async function authenticate(endpoint) {
        nickname = nicknameInput.value.trim();
        boardId = boardIdInput.value.trim() || "default";
        const password = passwordInput.value;

        if (nickname && password) {
            try {
                const response = await fetch(endpoint, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ username: nickname, password: password })
                });

                if (response.ok) {
                    const data = await response.json();
                    localStorage.setItem("token", data.access_token);

                    loginModal.style.display = "none";
                    canvasContainer.style.display = "block";
                    document.getElementById("minimap-container").style.display = "block";
                    document.getElementById("chat-panel").style.display = "flex";
                    initApp();
                } else {
                    const errData = await response.json();
                    authError.innerText = errData.detail || "Authentication failed";
                }
            } catch (err) {
                authError.innerText = "Error connecting to server";
            }
        } else {
            authError.innerText = "Please enter Nickname and Password.";
        }
    }

    registerBtn.addEventListener("click", () => authenticate("/register"));
    loginBtn.addEventListener("click", () => authenticate("/login"));

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

        initSmartGuides();

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

        // Zoom Controls
        document.getElementById("btn-zoom-in").addEventListener("click", () => {
            let zoom = canvas.getZoom();
            zoom *= 1.2;
            if (zoom > 20) zoom = 20;
            canvas.zoomToPoint({ x: canvas.getWidth() / 2, y: canvas.getHeight() / 2 }, zoom);
        });

        document.getElementById("btn-zoom-out").addEventListener("click", () => {
            let zoom = canvas.getZoom();
            zoom /= 1.2;
            if (zoom < 0.01) zoom = 0.01;
            canvas.zoomToPoint({ x: canvas.getWidth() / 2, y: canvas.getHeight() / 2 }, zoom);
        });

        document.getElementById("btn-zoom-reset").addEventListener("click", () => {
            canvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
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

        // Grid Snapping
        const chkGridSnap = document.getElementById("chk-grid-snap");
        let gridSnapEnabled = chkGridSnap ? chkGridSnap.checked : false;
        const GRID_SIZE = 20;

        if (chkGridSnap) {
            chkGridSnap.addEventListener('change', (e) => {
                gridSnapEnabled = e.target.checked;
            });
        }

        canvas.on('object:moving', function(options) {
            if (!gridSnapEnabled) return;
            const target = options.target;
            target.set({
                left: Math.round(target.left / GRID_SIZE) * GRID_SIZE,
                top: Math.round(target.top / GRID_SIZE) * GRID_SIZE
            });
        });

        canvas.on('object:rotating', function(e) {
            updatePropertiesPanel();
        });

        // Connect WebSocket
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const token = localStorage.getItem("token") || "";
        ws = new WebSocket(`${protocol}//${window.location.host}/ws/${boardId}/${nickname}?token=${token}`);
        window.ws = ws; // Expose for testing

        ws.onopen = () => {
            console.log("Connected to WS");
        };

        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);

            if (message.type === "init") {
                // Set access controls
                canEdit = message.can_edit;
                isOwner = message.is_owner;

                if (!canEdit) {
                    toolbar.classList.add("hidden");
                    document.getElementById("properties-panel").style.display = "none";
                    canvas.selection = false;
                } else {
                    toolbar.classList.remove("hidden");
                }

                if (isOwner) {
                    document.getElementById("share-access-container").style.display = "block";
                    document.getElementById("share-access-select").value = message.public_access || "edit";
                }

                // Load existing shapes
                isProcessingSync = true;
                message.data.forEach(shapeData => {
                    if (!canEdit) {
                        shapeData.selectable = false;
                        shapeData.evented = false;
                    }
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
            const text = new fabric.Textbox('Hello World', {
                left: 300,
                top: 300,
                fontSize: 40,
                fill: 'blue',
                width: 250,
                splitByGrapheme: true,
                id: id
            });
            canvas.add(text);
            canvas.setActiveObject(text);
            updatePropertiesPanel();
        });


        document.getElementById("btn-cluster-stickies").addEventListener("click", () => {
            if (!canEdit) return;

            // Find all stickies on the board
            const allObjects = canvas.getObjects();
            const stickies = allObjects.filter(obj => {
                if (obj.type !== 'group') return false;
                const objectsInGroup = obj.getObjects();
                const hasRect = objectsInGroup.some(child => child.type === 'rect' && child.fill === '#FFFF88');
                const hasText = objectsInGroup.some(child => child.type === 'textbox');
                return hasRect && hasText;
            });

            if (stickies.length <= 1) return; // Nothing to cluster

            // Use the first sticky's coordinates as the starting point for the cluster
            const startX = stickies[0].left;
            const startY = stickies[0].top;

            // Sort stickies to have a consistent order (optional, by creation time or just arbitrary)
            // Default array order is fine.

            const padding = 20;
            const stickyWidth = stickies[0].width;
            const stickyHeight = stickies[0].height;

            const cols = Math.ceil(Math.sqrt(stickies.length)); // Try to make a square grid

            const prevStates = [];
            const nextStates = [];

            stickies.forEach((sticky, index) => {
                prevStates.push(sticky.toObject(TO_OBJECT_PROPS));

                const row = Math.floor(index / cols);
                const col = index % cols;

                const newLeft = startX + (col * (stickyWidth + padding));
                const newTop = startY + (row * (stickyHeight + padding));

                sticky.set({ left: newLeft, top: newTop });
                sticky.setCoords();

                nextStates.push(sticky.toObject(TO_OBJECT_PROPS));

                // Broadcast modifications
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        action: 'modify',
                        object: sticky.toObject(TO_OBJECT_PROPS)
                    }));
                }
            });

            canvas.renderAll();
            updatePropertiesPanel();

            // Push history for bulk modify
            pushHistory('modify', prevStates, nextStates);
        });

        document.getElementById("btn-sticky").addEventListener("click", () => {
            const id = uuidv4();
            const rect = new fabric.Rect({
                left: 0,
                top: 0,
                width: 150,
                height: 150,
                fill: '#FFFF88', // Light yellow
                rx: 5,
                ry: 5,
                shadow: new fabric.Shadow({
                    color: 'rgba(0,0,0,0.3)',
                    blur: 5,
                    offsetX: 2,
                    offsetY: 2
                })
            });
            const text = new fabric.Textbox('Sticky Note', {
                left: 75,
                top: 75,
                width: 130,
                fontSize: 20,
                fill: '#333333',
                fontFamily: 'Arial',
                originX: 'center',
                originY: 'center',
                textAlign: 'center',
                splitByGrapheme: true
            });

            const group = new fabric.Group([rect, text], {
                left: 300,
                top: 300,
                id: id
            });

            canvas.add(group);
            canvas.setActiveObject(group);
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
        const btnEraser = document.getElementById("btn-eraser");
        const btnLaser = document.getElementById("btn-laser");

        btnFreehand.addEventListener("click", () => {
             isEraserMode = false;
             isLaserMode = false;
             window.isEraserMode = isEraserMode;
             window.isLaserMode = isLaserMode;
             canvas.isDrawingMode = !canvas.isDrawingMode;
             btnFreehand.style.backgroundColor = canvas.isDrawingMode ? '#ccc' : '#f0f0f0';
             btnEraser.style.backgroundColor = '#f0f0f0';
             btnLaser.style.backgroundColor = '#f0f0f0';
        });

        btnEraser.addEventListener("click", () => {
             isEraserMode = !isEraserMode;
             isLaserMode = false;
             window.isEraserMode = isEraserMode;
             window.isLaserMode = isLaserMode;
             canvas.isDrawingMode = isEraserMode;
             btnEraser.style.backgroundColor = isEraserMode ? '#ccc' : '#f0f0f0';
             btnFreehand.style.backgroundColor = '#f0f0f0';
             btnLaser.style.backgroundColor = '#f0f0f0';
        });

        btnLaser.addEventListener("click", () => {
             isLaserMode = !isLaserMode;
             isEraserMode = false;
             window.isLaserMode = isLaserMode;
             window.isEraserMode = isEraserMode;
             canvas.isDrawingMode = false;
             btnLaser.style.backgroundColor = isLaserMode ? '#ccc' : '#f0f0f0';
             btnFreehand.style.backgroundColor = '#f0f0f0';
             btnEraser.style.backgroundColor = '#f0f0f0';
             if (isLaserMode) {
                 canvas.discardActiveObject();
                 canvas.requestRenderAll();
             }
        });

        // Add ID to freehand paths
        canvas.on('path:created', (e) => {
             const path = e.path;
             path.set({ id: uuidv4() });
             if (isEraserMode) {
                 path.set({ globalCompositeOperation: 'destination-out' });
             }
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
             ws.send(JSON.stringify({ action: 'add', object: group.toObject(TO_OBJECT_PROPS) }));

             canvas.requestRenderAll();
        });

        document.getElementById("btn-ungroup").addEventListener("click", () => {
             if (!canvas.getActiveObject()) return;
             if (canvas.getActiveObject().type !== 'group') return;

             const group = canvas.getActiveObject();
             const groupId = group.id;

             // Extract true absolute coordinates manually before toActiveSelection changes state
             const objectsToAdd = [];
             group.getObjects().forEach(obj => {
                 const matrix = obj.calcTransformMatrix();
                 const point = fabric.util.qrDecompose(matrix);

                 if (!obj.id) obj.id = uuidv4();

                 const objData = obj.toObject(TO_OBJECT_PROPS);
                 objData.left = point.translateX;
                 objData.top = point.translateY;
                 objData.scaleX = point.scaleX;
                 objData.scaleY = point.scaleY;
                 objData.angle = point.angle;

                 objectsToAdd.push(objData);
             });

             const activeSelection = group.toActiveSelection();

             ws.send(JSON.stringify({ action: 'remove', object: { id: groupId } }));

             objectsToAdd.forEach(objData => {
                 ws.send(JSON.stringify({ action: 'add', object: objData }));
             });

             canvas.requestRenderAll();
        });


        const imageUploadInput = document.getElementById("image-upload-input");
        document.getElementById("btn-image").addEventListener("click", () => {
             imageUploadInput.click();
        });

        imageUploadInput.addEventListener("change", async (e) => {
             if (e.target.files && e.target.files.length > 0) {
                 const file = e.target.files[0];

                 const formData = new FormData();
                 formData.append("file", file);

                 try {
                     const response = await fetch('/upload', {
                         method: 'POST',
                         body: formData
                     });
                     const data = await response.json();

                     let urlsToLoad = [];
                     if (data.urls) {
                         urlsToLoad = data.urls;
                     } else if (data.url) {
                         urlsToLoad = [data.url];
                     }

                     if (urlsToLoad.length > 0) {
                         let currentY = 100;
                         const padding = 20;

                         const loadPromises = urlsToLoad.map(url => {
                             return new Promise((resolve) => {
                                 fabric.Image.fromURL(url, (img) => {
                                     const id = uuidv4();
                                     img.set({
                                         id: id,
                                         left: 100,
                                         top: currentY,
                                         z_index: canvas.getObjects().length,
                                         selectable: true,
                                         evented: true,
                                         is_background: false
                                     });

                                     // Add default crossOrigin
                                     img.crossOrigin = "anonymous";

                                     // Scale down if too large
                                     if (img.width > 800) {
                                         img.scaleToWidth(800);
                                     }

                                     currentY += (img.height * img.scaleY) + padding;

                                     canvas.add(img);

                                     const objData = img.toObject(TO_OBJECT_PROPS);
                                     pushHistory('add', null, objData);
                                     ws.send(JSON.stringify({ action: 'add', object: objData }));

                                     resolve(img);
                                 }, { crossOrigin: 'anonymous' });
                             });
                         });

                         await Promise.all(loadPromises);
                         canvas.renderAll();
                     }
                 } catch (err) {
                     console.error("Error uploading image:", err);
                     alert("Failed to upload image");
                 }
             }
             imageUploadInput.value = '';
        });

        const bgUploadInput = document.getElementById("bg-upload-input");

        document.getElementById("btn-set-bg").addEventListener("click", () => {
             bgUploadInput.click();
        });

        bgUploadInput.addEventListener("change", async (e) => {
             if (e.target.files && e.target.files.length > 0) {
                 const file = e.target.files[0];

                 const formData = new FormData();
                 formData.append("file", file);

                 try {
                     const response = await fetch('/upload', {
                         method: 'POST',
                         body: formData
                     });
                     const data = await response.json();

                     let urlsToLoad = [];
                     if (data.urls) {
                         urlsToLoad = data.urls;
                     } else if (data.url) {
                         urlsToLoad = [data.url];
                     }

                     if (urlsToLoad.length > 0) {
                         // We will only use the first image as background
                         const url = urlsToLoad[0];

                         fabric.Image.fromURL(url, (img) => {
                             // Remove existing background
                             const objects = canvas.getObjects();
                             const existingBgs = objects.filter(o => o.is_background === true);
                             existingBgs.forEach(bg => {
                                 canvas.remove(bg);
                                 ws.send(JSON.stringify({ action: 'remove', object: { id: bg.id } }));
                             });

                             const id = uuidv4();
                             img.set({
                                 id: id,
                                 left: 0,
                                 top: 0,
                                 originX: 'center',
                                 originY: 'center',
                                 z_index: -9999,
                                 selectable: false,
                                 evented: false,
                                 is_background: true
                             });

                             canvas.add(img);
                             canvas.sendToBack(img);

                             const objData = img.toObject(TO_OBJECT_PROPS);
                             pushHistory('add', null, objData);

                             ws.send(JSON.stringify({
                                 action: 'add',
                                 object: objData
                             }));
                         }, { crossOrigin: 'anonymous' });
                     }
                 } catch (err) {
                     console.error("Upload failed", err);
                 }
             }
             e.target.value = ""; // Reset input
        });

        document.getElementById("btn-clear-bg").addEventListener("click", () => {
             const objects = canvas.getObjects();
             const existingBgs = objects.filter(o => o.is_background === true);

             if (existingBgs.length > 0) {
                 const removedObjects = [];
                 existingBgs.forEach(bg => {
                     removedObjects.push(bg.toObject(TO_OBJECT_PROPS));
                     canvas.remove(bg);
                     ws.send(JSON.stringify({ action: 'remove', object: { id: bg.id } }));
                 });
                 pushHistory('remove', removedObjects, null);
                 canvas.requestRenderAll();
             }
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

        document.getElementById("btn-duplicate")?.addEventListener("click", duplicate);

        document.getElementById("btn-lock")?.addEventListener("click", () => {
            const activeObject = canvas.getActiveObject();
            if (!activeObject) return;

            const isLocked = activeObject.locked || activeObject.lockMovementX;
            const newLockedState = !isLocked;

            const originalState = activeObject.toObject(TO_OBJECT_PROPS);

            if (activeObject.type === 'activeSelection') {
                activeObject.forEachObject((obj) => {
                    obj.set({
                        locked: newLockedState,
                        lockMovementX: newLockedState,
                        lockMovementY: newLockedState,
                        lockRotation: newLockedState,
                        lockScalingX: newLockedState,
                        lockScalingY: newLockedState,
                        hasControls: !newLockedState
                    });
                });
            }

            activeObject.set({
                locked: newLockedState,
                lockMovementX: newLockedState,
                lockMovementY: newLockedState,
                lockRotation: newLockedState,
                lockScalingX: newLockedState,
                lockScalingY: newLockedState,
                hasControls: !newLockedState
            });

            const newState = activeObject.toObject(TO_OBJECT_PROPS);
            pushHistory('modify', originalState, newState);

            canvas.fire('object:modified', { target: activeObject });
            canvas.requestRenderAll();
        });

        document.getElementById("btn-clear").addEventListener("click", () => {
            canvas.discardActiveObject();
            canvas.requestRenderAll();
        });

        function alignObjects(alignment) {
            const activeObject = canvas.getActiveObject();
            if (!activeObject || activeObject.type !== 'activeSelection') {
                return;
            }

            const objects = activeObject.getObjects();
            if (objects.length < 2) return;

            // Get global bounding box before ungrouping
            const groupBounds = activeObject.getBoundingRect(true, true);

            // Discard selection so objects return to global coordinates
            canvas.discardActiveObject();

            const prevData = objects.map(o => o.toObject(TO_OBJECT_PROPS));

            objects.forEach(obj => {
                const objBounds = obj.getBoundingRect(true, true);

                switch(alignment) {
                    case 'left':
                        // We set left, but consider originX
                        obj.set({ left: groupBounds.left });
                        break;
                    case 'center':
                        obj.set({ left: groupBounds.left + groupBounds.width / 2 - (obj.width * obj.scaleX) / 2 });
                        break;
                    case 'right':
                        obj.set({ left: groupBounds.left + groupBounds.width - (obj.width * obj.scaleX) });
                        break;
                    case 'top':
                        obj.set({ top: groupBounds.top });
                        break;
                    case 'middle':
                        obj.set({ top: groupBounds.top + groupBounds.height / 2 - (obj.height * obj.scaleY) / 2 });
                        break;
                    case 'bottom':
                        obj.set({ top: groupBounds.top + groupBounds.height - (obj.height * obj.scaleY) });
                        break;
                }
                obj.setCoords();
            });

            const modifiedData = [];
            objects.forEach(obj => {
                const objData = obj.toObject(TO_OBJECT_PROPS);
                modifiedData.push(objData);
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        action: 'modify',
                        object: objData
                    }));
                }
            });

            pushHistory('align', prevData, modifiedData);

            // Re-select the objects
            const newSel = new fabric.ActiveSelection(objects, {canvas: canvas});
            canvas.setActiveObject(newSel);
            canvas.requestRenderAll();
        }

        document.getElementById("btn-align-left").addEventListener("click", () => alignObjects('left'));
        document.getElementById("btn-align-center").addEventListener("click", () => alignObjects('center'));
        document.getElementById("btn-align-right").addEventListener("click", () => alignObjects('right'));
        document.getElementById("btn-align-top").addEventListener("click", () => alignObjects('top'));
        document.getElementById("btn-align-middle").addEventListener("click", () => alignObjects('middle'));
        document.getElementById("btn-align-bottom").addEventListener("click", () => alignObjects('bottom'));

        document.getElementById("btn-clear-board").addEventListener("click", () => {
            if (window.confirm("Are you sure you want to clear the entire board?")) {
                const objects = canvas.getObjects();
                if (objects.length > 0) {
                    const removedObjects = [];
                    objects.forEach(obj => {
                        removedObjects.push(obj.toObject(TO_OBJECT_PROPS));
                        canvas.remove(obj);
                        ws.send(JSON.stringify({ action: 'remove', object: { id: obj.id } }));
                    });
                    pushHistory('remove', removedObjects, null);
                    canvas.requestRenderAll();
                    updateMinimap();
                }
            }
        });

        // Canvas events -> WebSocket
        canvas.on('object:added', (e) => {
            if (isProcessingSync || isUndoRedo) return;
            const obj = e.target;
            if (!obj.id) obj.id = uuidv4(); // fallback

            const objData = obj.toObject(TO_OBJECT_PROPS);
            pushHistory('add', null, objData);

            ws.send(JSON.stringify({
                action: 'add',
                object: objData
            }));
        });

        canvas.on('mouse:down', (e) => {
            if (e.target && e.target.type !== 'activeSelection') {
                e.target._originalState = e.target.toObject(TO_OBJECT_PROPS);
            } else if (e.target && e.target.type === 'activeSelection') {
                e.target.getObjects().forEach(o => {
                    o._originalState = o.toObject(TO_OBJECT_PROPS);
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
                const newState = obj.toObject(TO_OBJECT_PROPS);
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

                            const objData = img.toObject(TO_OBJECT_PROPS);
                            pushHistory('add', null, objData);
                            ws.send(JSON.stringify({
                                action: 'add',
                                object: objData
                            }));

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


        window.duplicate = duplicate;
        function duplicate() {
            const activeObject = canvas.getActiveObject();
            if (!activeObject) return;

            // Ignore if we are currently editing text
            if (activeObject.isEditing) return;

            activeObject.clone((clonedObj) => {
                canvas.discardActiveObject();
                clonedObj.set({
                    left: clonedObj.left + 20,
                    top: clonedObj.top + 20,
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
                        const objData = obj.toObject(TO_OBJECT_PROPS);
                        ws.send(JSON.stringify({ action: 'add', object: objData }));
                    });
                    clonedObj.setCoords();
                    canvas.setActiveObject(clonedObj);
                } else {
                    clonedObj.set({
                        id: uuidv4(),
                        z_index: getMaxZIndex() + 1
                    });
                    canvas.add(clonedObj);
                    const objData = clonedObj.toObject(TO_OBJECT_PROPS);
                    ws.send(JSON.stringify({ action: 'add', object: objData }));
                    canvas.setActiveObject(clonedObj);
                }
                canvas.requestRenderAll();

            });
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

                        const objData = obj.toObject(TO_OBJECT_PROPS);
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
                    const objData = clonedObj.toObject(TO_OBJECT_PROPS);
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

             } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'd') {
                 if (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA') return;
                 duplicate();
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
                         removedObjects.push(obj.toObject(TO_OBJECT_PROPS));
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

        document.getElementById("btn-dark-mode").addEventListener("click", (e) => {
            const isDark = document.body.classList.toggle("dark-mode");
            e.target.textContent = isDark ? "Light Mode" : "Dark Mode";
            canvas.backgroundColor = isDark ? "#121212" : "#f5f5f5";
            canvas.renderAll();
        });

        document.getElementById("btn-history").addEventListener("click", () => {
            const historyPanel = document.getElementById("history-panel");
            if (historyPanel.style.display === "none") {
                historyPanel.style.display = "block";
                updateHistoryPanel();
            } else {
                historyPanel.style.display = "none";
            }
        });

        document.getElementById("btn-export").addEventListener("click", () => {
            const dataURL = canvas.toDataURL({
                format: 'png',
                quality: 1
            });
            const link = document.createElement('a');
            link.download = `board-${boardId}-export.png`;
            link.href = dataURL;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });

        document.getElementById("btn-export-pdf").addEventListener("click", () => {
            const dataURL = canvas.toDataURL({
                format: 'png',
                quality: 1
            });
            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF({
                orientation: "landscape",
                unit: "px",
                format: [canvas.width, canvas.height]
            });
            pdf.addImage(dataURL, 'PNG', 0, 0, canvas.width, canvas.height);
            pdf.save(`board-${boardId}-export.pdf`);
        });

        document.getElementById("btn-export-svg").addEventListener("click", () => {
            const svgData = canvas.toSVG();
            const blob = new Blob([svgData], { type: "image/svg+xml;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.download = `board-${boardId}-export.svg`;
            link.href = url;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
        });

        document.getElementById("btn-export-json").addEventListener("click", () => {
            const objects = canvas.getObjects().map(obj => obj.toObject(TO_OBJECT_PROPS));
            const jsonString = JSON.stringify(objects, null, 2);
            const blob = new Blob([jsonString], { type: "application/json" });
            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.download = `board-${boardId}-export.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });

        document.getElementById("btn-import-json").addEventListener("click", () => {
            document.getElementById("json-upload-input").click();
        });

        document.getElementById("json-upload-input").addEventListener("change", (e) => {
            const file = e.target.files[0];
            if (!file) return;

            if (window.confirm("Importing a JSON file will overwrite the current board. Are you sure you want to continue?")) {
                const reader = new FileReader();
                reader.onload = function(event) {
                    try {
                        const jsonObjects = JSON.parse(event.target.result);

                        // Clear existing objects first
                        const existingObjects = canvas.getObjects();
                        if (existingObjects.length > 0) {
                            const removedObjects = [];
                            existingObjects.forEach(obj => {
                                removedObjects.push(obj.toObject(TO_OBJECT_PROPS));
                                ws.send(JSON.stringify({ action: 'remove', object: { id: obj.id } }));
                            });
                            canvas.clear();
                            pushHistory('remove', removedObjects, null);
                        }

                        // Add new objects
                        fabric.util.enlivenObjects(jsonObjects, function(objects) {
                            const addedObjects = [];
                            objects.forEach(function(o) {
                                // Important: ensure IDs are preserved or generated
                                if (!o.id) o.id = uuidv4();
                                canvas.add(o);
                                const objData = o.toObject(TO_OBJECT_PROPS);
                                addedObjects.push(objData);
                                ws.send(JSON.stringify({ action: 'add', object: objData }));
                            });
                            canvas.requestRenderAll();
                            pushHistory('add', null, addedObjects);

                        });

                    } catch (error) {
                        console.error("Failed to parse JSON", error);
                        alert("Invalid JSON file.");
                    }
                };
                reader.readAsText(file);
            }
            // Reset input value to allow importing the same file again
            e.target.value = "";
        });
    }

    function addShapeToCanvas(shapeData) {
        if (!canEdit) {
            shapeData.selectable = false;
            shapeData.evented = false;
        }
        fabric.util.enlivenObjects([shapeData], (objects) => {
            const origRenderOnAddRemove = canvas.renderOnAddRemove;
            canvas.renderOnAddRemove = false;

            objects.forEach((obj) => {
                if (shapeData.z_index !== undefined) obj.z_index = shapeData.z_index;
                if (shapeData.selectable !== undefined) obj.selectable = shapeData.selectable;
                if (shapeData.evented !== undefined) obj.evented = shapeData.evented;
                if (shapeData.is_background !== undefined) obj.is_background = shapeData.is_background;
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
        window.drawLaserPoint = function(x, y, color) {
            const circle = new fabric.Circle({
                left: x,
                top: y,
                radius: 5,
                fill: color || 'red',
                opacity: 0.8,
                originX: 'center',
                originY: 'center',
                selectable: false,
                evented: false,
                is_background: true // Avoid history tracking
            });
            canvas.add(circle);

            // Animate opacity and then remove
            circle.animate('opacity', 0, {
                duration: 1000,
                onChange: canvas.requestRenderAll.bind(canvas),
                onComplete: () => {
                    canvas.remove(circle);
                }
            });
        };

        let isLaserDrawing = false;
        canvas.on('mouse:down', function(opt) {
            if (isLaserMode) {
                isLaserDrawing = true;
            }
        });

        canvas.on('mouse:up', function(opt) {
            if (isLaserMode) {
                isLaserDrawing = false;
            }
        });

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

            if (isLaserMode && isLaserDrawing) {
                if (now - lastLaserSend > 50) {
                    const pointer = canvas.getPointer(opt.e);
                    // Draw locally
                    const userColor = activeUsers[nickname] ? activeUsers[nickname].color : 'red';
                    window.drawLaserPoint(pointer.x, pointer.y, userColor);
                    // Broadcast laser action
                    if (ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({
                            action: 'laser',
                            object: { x: pointer.x, y: pointer.y, color: userColor }
                        }));
                    }
                    lastLaserSend = now;
                }
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
                const initials = sender.substring(0, 2).toUpperCase();
                el.innerHTML = `
                    <svg viewBox="0 0 16 16"><path d="M0,0 L16,5 L9,8 L13,15 L10,16 L6,9 L1,14 Z"></path></svg>
                    <div class="remote-cursor-label">
                        <div class="cursor-avatar" style="color: ${color};">${initials}</div>
                        <span>${sender}</span>
                    </div>
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
    const propAngle = document.getElementById("prop-angle");
    const propTextFormats = document.getElementById("prop-text-formats");
    const btnBold = document.getElementById("btn-bold");
    const btnItalic = document.getElementById("btn-italic");
    const btnUnderline = document.getElementById("btn-underline");

    window.updatePropertiesPanel = function updatePropertiesPanel() {
        let activeObject = canvas.getActiveObject();
        if (!activeObject || activeObject.type === 'activeSelection') {
            propertiesPanel.style.display = 'none';
            return;
        }

        // If it's a group, look for a text child to show text formatting tools
        let textObject = null;
        if (activeObject.type === 'i-text' || activeObject.type === 'text' || activeObject.type === 'textbox') {
            textObject = activeObject;
        } else if (activeObject.type === 'group') {
            textObject = activeObject.getObjects().find(o => o.type === 'i-text' || o.type === 'text' || o.type === 'textbox');
        }

        propertiesPanel.style.display = 'flex';

        // Populate current values
        if (activeObject.fill) propFill.value = activeObject.fill;
        if (activeObject.stroke) propStroke.value = activeObject.stroke;
        if (activeObject.strokeWidth !== undefined) propStrokeWidth.value = activeObject.strokeWidth;
        if (activeObject.angle !== undefined) propAngle.value = Math.round(activeObject.angle);

        if (textObject) {
            propFontFamily.parentElement.style.display = 'flex';
            propTextFormats.style.display = 'block';
            if (textObject.fontFamily) propFontFamily.value = textObject.fontFamily;

            btnBold.style.backgroundColor = textObject.fontWeight === 'bold' ? '#ccc' : '';
            btnItalic.style.backgroundColor = textObject.fontStyle === 'italic' ? '#ccc' : '';
            btnUnderline.style.backgroundColor = textObject.underline ? '#ccc' : '';
        } else {
            propFontFamily.parentElement.style.display = 'none';
            propTextFormats.style.display = 'none';
        }
    }

    [propFill, propStroke, propStrokeWidth, propFontFamily].forEach(input => {
        input.addEventListener('change', (e) => {
            const activeObject = canvas.getActiveObject();
            if (!activeObject) return;

            const prop = e.target.id.replace('prop-', '');
            let val = e.target.value;

            if (prop === 'stroke-width') val = parseInt(val, 10);

            const originalState = activeObject.toObject(TO_OBJECT_PROPS);

            if (prop === 'fill') activeObject.set('fill', val);
            if (prop === 'stroke') activeObject.set('stroke', val);
            if (prop === 'stroke-width') activeObject.set('strokeWidth', val);
            if (prop === 'font-family') activeObject.set('fontFamily', val);

            const newState = activeObject.toObject(TO_OBJECT_PROPS);
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

        if (typeof propFontSize !== 'undefined') {
            propFontSize.addEventListener('input', (e) => applyPropertyChange('fontSize', e.target.value));
            propFontSize.addEventListener('change', (e) => applyPropertyChange('fontSize', e.target.value));
        }

        propAngle.addEventListener('input', (e) => applyPropertyChange('angle', parseFloat(e.target.value)));
        propAngle.addEventListener('change', (e) => applyPropertyChange('angle', parseFloat(e.target.value)));

        function applyTextFormat(formatType) {
            let activeObj = canvas.getActiveObject();
            if (!activeObj || activeObj.type === 'activeSelection') return;

            let textObj = null;
            if (activeObj.type === 'i-text' || activeObj.type === 'text' || activeObj.type === 'textbox') {
                textObj = activeObj;
            } else if (activeObj.type === 'group') {
                textObj = activeObj.getObjects().find(o => o.type === 'i-text' || o.type === 'text' || o.type === 'textbox');
            }

            if (textObj) {
                const originalState = activeObj.toObject(TO_OBJECT_PROPS);

                if (formatType === 'bold') {
                    textObj.set('fontWeight', textObj.fontWeight === 'bold' ? 'normal' : 'bold');
                } else if (formatType === 'italic') {
                    textObj.set('fontStyle', textObj.fontStyle === 'italic' ? 'normal' : 'italic');
                } else if (formatType === 'underline') {
                    textObj.set('underline', !textObj.underline);
                }

                // If active object is a group, we modify the internal text object but need to fire events for the whole group
                const newState = activeObj.toObject(TO_OBJECT_PROPS);
                pushHistory('modify', originalState, newState);

                canvas.renderAll();
                canvas.fire('object:modified', { target: activeObj }); // Triggers WS sync
                updatePropertiesPanel();
            }
        }

        btnBold.addEventListener('click', () => applyTextFormat('bold'));
        btnItalic.addEventListener('click', () => applyTextFormat('italic'));
        btnUnderline.addEventListener('click', () => applyTextFormat('underline'));

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

        if (action === "laser") {
            if (window.drawLaserPoint) {
                window.drawLaserPoint(objData.x, objData.y, objData.color);
            }
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

    // --- Share Logic ---
    const shareModal = document.getElementById("share-modal");
    const btnShare = document.getElementById("btn-share");
    const closeShareBtn = document.getElementById("close-share-btn");
    const copyShareBtn = document.getElementById("copy-share-btn");
    const shareLinkInput = document.getElementById("share-link-input");
    const saveAccessBtn = document.getElementById("save-access-btn");
    const shareAccessSelect = document.getElementById("share-access-select");
    const shareMsg = document.getElementById("share-msg");

    if (btnShare) {
        btnShare.addEventListener("click", () => {
            shareLinkInput.value = window.location.origin + "/?board=" + boardId;
            shareModal.style.display = "flex";
            shareMsg.style.display = "none";
        });
    }

    if (closeShareBtn) {
        closeShareBtn.addEventListener("click", () => {
            shareModal.style.display = "none";
        });
    }

    if (copyShareBtn) {
        copyShareBtn.addEventListener("click", () => {
            shareLinkInput.select();
            document.execCommand("copy");
            shareMsg.style.display = "block";
        });
    }

    if (saveAccessBtn) {
        saveAccessBtn.addEventListener("click", async () => {
            const token = localStorage.getItem("token");
            if (!token) return;

            const access = shareAccessSelect.value;
            try {
                const res = await fetch(`/boards/${boardId}/access`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        token: token,
                        public_access: access
                    })
                });

                if (res.ok) {
                    shareMsg.textContent = "Settings saved!";
                    shareMsg.style.display = "block";
                    setTimeout(() => {
                        shareMsg.textContent = "Copied to clipboard!";
                        shareMsg.style.display = "none";
                    }, 2000);
                } else {
                    const data = await res.json();
                    alert("Failed to save settings: " + (data.detail || "Unknown error"));
                }
            } catch (err) {
                console.error("Error saving access settings", err);
                alert("Failed to save settings");
            }
        });
    }

function initSmartGuides() {
    let guideLines = [];
    let isSmartGuidesEnabled = false;
    const chkSmartGuides = document.getElementById("chk-smart-guides");

    if (chkSmartGuides) {
        chkSmartGuides.addEventListener("change", (e) => {
            isSmartGuidesEnabled = e.target.checked;
        });
    }

    canvas.on('object:moving', function(e) {
        if (!isSmartGuidesEnabled) return;

        const obj = e.target;
        const objects = canvas.getObjects().filter(o => o !== obj && o.visible !== false && !o.is_background && o.type !== 'activeSelection');

        guideLines = [];
        const threshold = 10;
        let snappedX = false;
        let snappedY = false;

        const objBounds = obj.getBoundingRect();
        const objCenterX = objBounds.left + objBounds.width / 2;
        const objCenterY = objBounds.top + objBounds.height / 2;

        for (let target of objects) {
            const tBounds = target.getBoundingRect();
            const tCenterX = tBounds.left + tBounds.width / 2;
            const tCenterY = tBounds.top + tBounds.height / 2;

            // X-axis snapping (centers)
            if (!snappedX && Math.abs(objCenterX - tCenterX) < threshold) {
                obj.left = tCenterX - (objBounds.width / 2);
                snappedX = true;
                guideLines.push({ x1: tCenterX, y1: Math.min(objBounds.top, tBounds.top), x2: tCenterX, y2: Math.max(objBounds.top + objBounds.height, tBounds.top + tBounds.height) });
            }

            // Y-axis snapping (centers)
            if (!snappedY && Math.abs(objCenterY - tCenterY) < threshold) {
                obj.top = tCenterY - (objBounds.height / 2);
                snappedY = true;
                guideLines.push({ x1: Math.min(objBounds.left, tBounds.left), y1: tCenterY, x2: Math.max(objBounds.left + objBounds.width, tBounds.left + tBounds.width), y2: tCenterY });
            }

            // Snapping left edge to left edge
            if (!snappedX && Math.abs(objBounds.left - tBounds.left) < threshold) {
                obj.left = tBounds.left;
                snappedX = true;
                guideLines.push({ x1: tBounds.left, y1: Math.min(objBounds.top, tBounds.top), x2: tBounds.left, y2: Math.max(objBounds.top + objBounds.height, tBounds.top + tBounds.height) });
            }

            // Snapping right edge to right edge
            if (!snappedX && Math.abs((objBounds.left + objBounds.width) - (tBounds.left + tBounds.width)) < threshold) {
                obj.left = tBounds.left + tBounds.width - objBounds.width;
                snappedX = true;
                guideLines.push({ x1: tBounds.left + tBounds.width, y1: Math.min(objBounds.top, tBounds.top), x2: tBounds.left + tBounds.width, y2: Math.max(objBounds.top + objBounds.height, tBounds.top + tBounds.height) });
            }

            // Snapping top edge to top edge
            if (!snappedY && Math.abs(objBounds.top - tBounds.top) < threshold) {
                obj.top = tBounds.top;
                snappedY = true;
                guideLines.push({ x1: Math.min(objBounds.left, tBounds.left), y1: tBounds.top, x2: Math.max(objBounds.left + objBounds.width, tBounds.left + tBounds.width), y2: tBounds.top });
            }

            // Snapping bottom edge to bottom edge
            if (!snappedY && Math.abs((objBounds.top + objBounds.height) - (tBounds.top + tBounds.height)) < threshold) {
                obj.top = tBounds.top + tBounds.height - objBounds.height;
                snappedY = true;
                guideLines.push({ x1: Math.min(objBounds.left, tBounds.left), y1: tBounds.top + tBounds.height, x2: Math.max(objBounds.left + objBounds.width, tBounds.left + tBounds.width), y2: tBounds.top + tBounds.height });
            }
        }
    });

    canvas.on('after:render', function() {
        if (!isSmartGuidesEnabled || guideLines.length === 0) return;
        const ctx = canvas.getContext();
        ctx.save();
        ctx.strokeStyle = 'rgba(255, 0, 0, 0.5)';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);

        // Handle viewport transform (zoom/pan)
        const vpt = canvas.viewportTransform;
        ctx.transform(vpt[0], vpt[1], vpt[2], vpt[3], vpt[4], vpt[5]);

        for (let line of guideLines) {
            ctx.beginPath();
            ctx.moveTo(line.x1, line.y1);
            ctx.lineTo(line.x2, line.y2);
            ctx.stroke();
        }
        ctx.restore();
    });

    canvas.on('mouse:up', function() {
        if (guideLines.length > 0) {
            guideLines = [];
            canvas.requestRenderAll();
        }
    });
}
