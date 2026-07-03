import re

with open("miro-clone/src/main.py", "r") as f:
    code = f.read()

# Update WebSocketDisconnect handling
old_disconnect = """    except WebSocketDisconnect:
        manager.disconnect(nickname)"""
new_disconnect = """    except WebSocketDisconnect:
        manager.disconnect(nickname)
        await manager.broadcast({
            "type": "update",
            "action": "disconnect",
            "sender": nickname
        })"""
code = code.replace(old_disconnect, new_disconnect)

# Update the action handling block
old_action_logic = """            elif action == "remove":
                result = await db.execute(select(Shape).filter(Shape.id == obj_id))
                db_shape = result.scalars().first()
                if db_shape:
                    await db.delete(db_shape)
                    await db.commit()

            # Broadcast the change to everyone else"""
new_action_logic = """            elif action == "remove":
                result = await db.execute(select(Shape).filter(Shape.id == obj_id))
                db_shape = result.scalars().first()
                if db_shape:
                    await db.delete(db_shape)
                    await db.commit()
            elif action in ["cursor", "select", "deselect", "chat"]:
                # Transient actions, no DB update
                pass

            # Broadcast the change to everyone else"""
code = code.replace(old_action_logic, new_action_logic)

with open("miro-clone/src/main.py", "w") as f:
    f.write(code)
