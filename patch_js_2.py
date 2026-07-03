import re

with open("miro-clone/static/app.js", "r") as f:
    code = f.read()

# Modify handleRemoteUpdate to intercept cursor, chat, disconnect, select, deselect
handle_remote_update_sig = "function handleRemoteUpdate(action, objData) {"
new_handle_remote_update = """function handleRemoteUpdate(action, objData, sender) {
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
"""
code = code.replace(handle_remote_update_sig, new_handle_remote_update)

ws_onmessage = """            } else if (message.type === "update") {
                handleRemoteUpdate(message.action, message.object, message.sender);
            }"""
code = re.sub(r'\} else if \(message\.type === "update"\) \{\s*handleRemoteUpdate\(message\.action, message\.object\);\s*\}', ws_onmessage, code)


# Append extra logic at the end of initApp()
extra_logic = """
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
        }
"""
code = code.replace("function handleRemoteUpdate(", extra_logic + "\n    function handleRemoteUpdate(")


with open("miro-clone/static/app.js", "w") as f:
    f.write(code)
