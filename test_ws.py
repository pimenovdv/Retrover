import asyncio
import websockets
import json

async def test():
    async with websockets.connect("ws://localhost:8000/ws/tester1") as ws1:
        # Client 1 connects, should get 'init' message with 0 shapes initially
        res = await ws1.recv()
        print("ws1 received:", res)

        async with websockets.connect("ws://localhost:8000/ws/tester2") as ws2:
            res = await ws2.recv()
            print("ws2 received:", res)

            # Tester1 sends a shape
            await ws1.send(json.dumps({
                "action": "add",
                "object": {
                    "id": "123",
                    "type": "rect",
                    "left": 10,
                    "top": 10,
                    "width": 100,
                    "height": 100,
                    "fill": "red"
                }
            }))

            # Tester2 should receive it
            res = await ws2.recv()
            print("ws2 received after ws1 send:", res)

asyncio.run(test())
