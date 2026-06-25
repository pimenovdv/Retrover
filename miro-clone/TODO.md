# TODO for Miro Clone

## 1. Canvas Functionality
- [ ] Implement true infinite canvas (zoom in/out, panning support).
- [ ] Add support for image uploads and dragging images onto canvas.
- [ ] Support shape grouping and multi-selection movement.
- [ ] Add more shape types (arrows, polygons, lines, freehand drawing).
- [ ] Add support for z-index (bring to front, send to back).

## 2. Collaborative Features
- [ ] Display other users' cursors in real-time.
- [ ] Show who is currently selecting/editing an object to avoid conflicts.
- [ ] Add a chat or comment system.

## 3. Backend & Database
- [ ] Optimize database writes (batch updates instead of per-event writes).
- [ ] Add Redis for faster WebSocket broadcast and state management.
- [ ] Implement Board models (allow creating multiple different boards, currently there is only one global board).

## 4. UI/UX
- [ ] Improve toolbar design and add property panels (change colors, fonts, stroke width).
- [ ] Add undo/redo functionality.
- [ ] Make UI responsive for mobile devices.
