import json
import logging
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, UploadFile, File
import aiofiles
import os
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .database import engine, Base, get_db
from .models import Shape, Board

import asyncio
from .database import AsyncSessionLocal
from collections import OrderedDict
from .redis_manager import redis_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

os.makedirs("uploads", exist_ok=True)

class ConnectionManager:
    def __init__(self):
        # Maps board_id -> {nickname -> WebSocket}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, board_id: str, nickname: str):
        await websocket.accept()
        if board_id not in self.active_connections:
            self.active_connections[board_id] = {}
        self.active_connections[board_id][nickname] = websocket
        logger.info(f"User {nickname} connected to board {board_id}")

    def disconnect(self, board_id: str, nickname: str):
        if board_id in self.active_connections and nickname in self.active_connections[board_id]:
            del self.active_connections[board_id][nickname]
            logger.info(f"User {nickname} disconnected from board {board_id}")
            if not self.active_connections[board_id]:
                del self.active_connections[board_id]

    async def local_broadcast(self, board_id: str, message: dict, exclude: str = None):
        logger.info(f"Local broadcasting to board {board_id}: {message} excluding {exclude}")
        if board_id in self.active_connections:
            for nickname, connection in self.active_connections[board_id].items():
                if nickname != exclude:
                    try:
                        await connection.send_text(json.dumps(message))
                    except Exception as e:
                        logger.error(f"Failed to send to {nickname}: {e}")

    async def broadcast(self, message: dict, exclude: str = None):
        # Tell redis manager to publish.
        # It will broadcast across instances, and each instance will local_broadcast
        await redis_manager.publish(message)

manager = ConnectionManager()


class DatabaseBatcher:
    def __init__(self):
        self.queue = OrderedDict() # id -> (action, obj_data)
        self.lock = asyncio.Lock()

    async def push(self, action: str, obj_data: dict, board_id: str = "default"):
        obj_id = obj_data.get("id")
        if not obj_id:
            return

        # Inject board_id into obj_data for processing later
        obj_data["board_id"] = board_id

        async with self.lock:
            if action == "remove":
                self.queue[obj_id] = (action, obj_data)
            else:
                # If modifying an already queued "add", keep it as "add" and merge data
                # If modifying a "modify", merge data
                if obj_id in self.queue:
                    prev_action, prev_data = self.queue[obj_id]
                    if prev_action == "add" and action == "modify":
                        # Merge into the 'add'
                        merged_data = prev_data.copy()
                        merged_data.update(obj_data)
                        self.queue[obj_id] = ("add", merged_data)
                    elif prev_action == "modify" and action == "modify":
                        merged_data = prev_data.copy()
                        merged_data.update(obj_data)
                        self.queue[obj_id] = ("modify", merged_data)
                    elif prev_action == "remove" and action in ["add", "modify"]:
                        # Edge case: object removed then re-added/modified before sync. Unlikely but possible.
                        self.queue[obj_id] = (action, obj_data)
                    else:
                        self.queue[obj_id] = (action, obj_data)
                else:
                    self.queue[obj_id] = (action, obj_data)

    async def process_batch(self):
        async with self.lock:
            if not self.queue:
                return
            batch = self.queue
            self.queue = OrderedDict()

        async with AsyncSessionLocal() as session:
            try:
                for obj_id, (action, obj_data) in batch.items():
                    if action == "add":
                        new_shape = Shape(
                            id=obj_id,
                            board_id=obj_data.get("board_id", "default"),
                            type=obj_data.get("type"),
                            left=obj_data.get("left", 0),
                            top=obj_data.get("top", 0),
                            width=obj_data.get("width"),
                            height=obj_data.get("height"),
                            fill=obj_data.get("fill"),
                            radius=obj_data.get("radius"),
                            text=obj_data.get("text"),
                            fontSize=obj_data.get("fontSize"),
                            z_index=obj_data.get("z_index", 0),
                            properties={k: v for k, v in obj_data.items() if k not in ["id", "board_id", "type", "left", "top", "width", "height", "fill", "radius", "text", "fontSize", "z_index"]}
                        )
                        session.add(new_shape)
                    elif action == "modify":
                        result = await session.execute(select(Shape).filter(Shape.id == obj_id))
                        db_shape = result.scalars().first()
                        if db_shape:
                            if "left" in obj_data: db_shape.left = obj_data["left"]
                            if "top" in obj_data: db_shape.top = obj_data["top"]
                            if "width" in obj_data: db_shape.width = obj_data["width"]
                            if "height" in obj_data: db_shape.height = obj_data["height"]
                            if "fill" in obj_data: db_shape.fill = obj_data["fill"]
                            if "radius" in obj_data: db_shape.radius = obj_data["radius"]
                            if "text" in obj_data: db_shape.text = obj_data["text"]
                            if "fontSize" in obj_data: db_shape.fontSize = obj_data["fontSize"]
                            if "z_index" in obj_data: db_shape.z_index = obj_data["z_index"]

                            current_props = dict(db_shape.properties or {})
                            for k, v in obj_data.items():
                                if k not in ["id", "board_id", "type", "left", "top", "width", "height", "fill", "radius", "text", "fontSize", "z_index"]:
                                    current_props[k] = v
                            db_shape.properties = current_props
                    elif action == "remove":
                        result = await session.execute(select(Shape).filter(Shape.id == obj_id))
                        db_shape = result.scalars().first()
                        if db_shape:
                            await session.delete(db_shape)
                await session.commit()
            except Exception as e:
                logger.error(f"Error processing database batch: {e}")
                await session.rollback()

db_batcher = DatabaseBatcher()



db_worker_task = None

async def db_writer_worker():
    while True:
        await asyncio.sleep(1) # Process batch every 1 second
        try:
            await db_batcher.process_batch()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in db_writer_worker: {e}")

@app.on_event("startup")
async def startup_event():
    global db_worker_task
    db_worker_task = asyncio.create_task(db_writer_worker())
    await redis_manager.connect()
    await redis_manager.start_listening(manager)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("shutdown")
async def shutdown_event():
    await redis_manager.close()
    if db_worker_task:
        db_worker_task.cancel()
        try:
            await db_worker_task
        except asyncio.CancelledError:
            pass
    # Flush remaining batch
    await db_batcher.process_batch()

@app.get("/")
async def get():
    return FileResponse("static/index.html")

@app.websocket("/ws/{board_id}/{nickname}")
async def websocket_endpoint(websocket: WebSocket, board_id: str, nickname: str, db: AsyncSession = Depends(get_db)):
    await manager.connect(websocket, board_id, nickname)

    # Ensure board exists
    from sqlalchemy.exc import IntegrityError
    board_result = await db.execute(select(Board).filter(Board.id == board_id))
    board = board_result.scalars().first()
    if not board:
        try:
            board = Board(id=board_id, name=f"Board {board_id}")
            db.add(board)
            await db.commit()
        except IntegrityError:
            await db.rollback()
            # Board was created by another concurrent request, which is fine
            pass

    # Ensure all pending db writes are flushed before querying existing shapes
    await db_batcher.process_batch()

    # Send all existing shapes to the newly connected user
    result = await db.execute(select(Shape).filter(Shape.board_id == board_id).order_by(Shape.z_index.asc()))
    shapes = result.scalars().all()

    initial_shapes = []
    for s in shapes:
        shape_data = {
            "id": s.id,
            "type": s.type,
            "left": s.left,
            "top": s.top,
            "z_index": s.z_index,
        }
        if s.width is not None: shape_data["width"] = s.width
        if s.height is not None: shape_data["height"] = s.height
        if s.fill is not None: shape_data["fill"] = s.fill
        if s.radius is not None: shape_data["radius"] = s.radius
        if s.text is not None: shape_data["text"] = s.text
        if s.fontSize is not None: shape_data["fontSize"] = s.fontSize

        # merge any extra properties
        if s.properties:
            shape_data.update(s.properties)

        initial_shapes.append(shape_data)

    await websocket.send_text(json.dumps({
        "type": "init",
        "data": initial_shapes
    }))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Message format: {"action": "add"|"modify"|"remove", "object": {...}}

            action = message.get("action")
            obj_data = message.get("object", {})
            obj_id = obj_data.get("id")

            if action in ["add", "modify", "remove"]:
                await db_batcher.push(action, obj_data, board_id=board_id)
            elif action in ["cursor", "select", "deselect", "chat"]:
                # Transient actions, no DB update
                pass

            # Broadcast the change to everyone else
            await manager.broadcast({
                "type": "update",
                "action": action,
                "object": obj_data,
                "sender": nickname,
                "board_id": board_id
            }, exclude=nickname)

    except WebSocketDisconnect:
        manager.disconnect(board_id, nickname)
        await manager.broadcast({
            "type": "update",
            "action": "disconnect",
            "sender": nickname,
            "board_id": board_id
        })

from fastapi import HTTPException
@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    import uuid
    import fitz

    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only images and PDFs are allowed.")

    ext = file.filename.split('.')[-1].lower() if '.' in file.filename else 'png'
    if ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf']:
        raise HTTPException(status_code=400, detail="Invalid file extension.")

    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join("uploads", filename)

    async with aiofiles.open(filepath, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)

    if ext == 'pdf':
        urls = []
        doc = fitz.open(filepath)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap()
            page_filename = f"{uuid.uuid4()}.png"
            page_filepath = os.path.join("uploads", page_filename)
            pix.save(page_filepath)
            urls.append(f"/uploads/{page_filename}")
        doc.close()

        # Clean up the original pdf
        os.remove(filepath)

        return {"urls": urls}

    return {"url": f"/uploads/{filename}"}
