# TODO for Miro Clone

## 1. Authentication & Users
- [ ] Replace simple nickname login with proper JWT-based authentication.
- [ ] Add User registration and login flow.
- [ ] Add session management.

## 2. Canvas Functionality
- [ ] Implement true infinite canvas (zoom in/out, panning support).
- [ ] Add support for image uploads and dragging images onto canvas.
- [ ] Support shape grouping and multi-selection movement.
- [ ] Add more shape types (arrows, polygons, lines, freehand drawing).
- [ ] Add support for z-index (bring to front, send to back).

## 3. Collaborative Features
- [ ] Display other users' cursors in real-time.
- [ ] Show who is currently selecting/editing an object to avoid conflicts.
- [ ] Add a chat or comment system.

## 4. Backend & Database
- [ ] Optimize database writes (batch updates instead of per-event writes).
- [ ] Add Redis for faster WebSocket broadcast and state management.
- [ ] Implement Board models (allow creating multiple different boards, currently there is only one global board).

## 5. UI/UX
- [ ] Improve toolbar design and add property panels (change colors, fonts, stroke width).
- [ ] Add undo/redo functionality.
- [ ] Make UI responsive for mobile devices.
