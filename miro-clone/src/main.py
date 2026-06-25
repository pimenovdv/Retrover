import json
import logging
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .database import engine, Base, get_db
from .models import Shape

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

class ConnectionManager:
    def __init__(self):
        # Maps nickname to their WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, nickname: str):
        await websocket.accept()
        self.active_connections[nickname] = websocket
        logger.info(f"User {nickname} connected")

    def disconnect(self, nickname: str):
        if nickname in self.active_connections:
            del self.active_connections[nickname]
            logger.info(f"User {nickname} disconnected")

    async def broadcast(self, message: dict, exclude: str = None):
        logger.info(f"Broadcasting: {message} excluding {exclude}")
        for nickname, connection in self.active_connections.items():
            if nickname != exclude:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Failed to send to {nickname}: {e}")

manager = ConnectionManager()

@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def get():
    return FileResponse("static/index.html")

@app.websocket("/ws/{nickname}")
async def websocket_endpoint(websocket: WebSocket, nickname: str, db: AsyncSession = Depends(get_db)):
    await manager.connect(websocket, nickname)

    # Send all existing shapes to the newly connected user
    result = await db.execute(select(Shape))
    shapes = result.scalars().all()

    initial_shapes = []
    for s in shapes:
        shape_data = {
            "id": s.id,
            "type": s.type,
            "left": s.left,
            "top": s.top,
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

            if action == "add":
                # Save to DB
                new_shape = Shape(
                    id=obj_id,
                    type=obj_data.get("type"),
                    left=obj_data.get("left", 0),
                    top=obj_data.get("top", 0),
                    width=obj_data.get("width"),
                    height=obj_data.get("height"),
                    fill=obj_data.get("fill"),
                    radius=obj_data.get("radius"),
                    text=obj_data.get("text"),
                    fontSize=obj_data.get("fontSize"),
                    properties={k: v for k, v in obj_data.items() if k not in ["id", "type", "left", "top", "width", "height", "fill", "radius", "text", "fontSize"]}
                )
                db.add(new_shape)
                await db.commit()

            elif action == "modify":
                result = await db.execute(select(Shape).filter(Shape.id == obj_id))
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

                    # Update properties
                    current_props = dict(db_shape.properties or {})
                    for k, v in obj_data.items():
                         if k not in ["id", "type", "left", "top", "width", "height", "fill", "radius", "text", "fontSize"]:
                             current_props[k] = v
                    db_shape.properties = current_props

                    await db.commit()

            elif action == "remove":
                result = await db.execute(select(Shape).filter(Shape.id == obj_id))
                db_shape = result.scalars().first()
                if db_shape:
                    await db.delete(db_shape)
                    await db.commit()

            # Broadcast the change to everyone else
            await manager.broadcast({
                "type": "update",
                "action": action,
                "object": obj_data,
                "sender": nickname
            }, exclude=nickname)

    except WebSocketDisconnect:
        manager.disconnect(nickname)
