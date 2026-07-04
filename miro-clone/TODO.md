# TODO for Miro Clone

## 1. Canvas Functionality
- [x] Implement true infinite canvas (zoom in/out, panning support).
- [x] Add support for image uploads and dragging images onto canvas.
- [x] Support shape grouping and multi-selection movement.
- [x] Add more shape types (arrows, polygons, lines, freehand drawing).
- [x] Add support for z-index (bring to front, send to back).

## 2. Collaborative Features
- [x] Display other users' cursors in real-time.
- [x] Show who is currently selecting/editing an object to avoid conflicts.
- [x] Add a chat or comment system.

## 3. Backend & Database
- [x] Optimize database writes (batch updates instead of per-event writes).
- [x] Add Redis for faster WebSocket broadcast and state management.
- [x] Implement Board models (allow creating multiple different boards, currently there is only one global board).

## 4. UI/UX
- [ ] Improve toolbar design and add property panels (change colors, fonts, stroke width).
- [ ] Add undo/redo functionality.
- [ ] Make UI responsive for mobile devices.
