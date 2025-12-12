import os
import asyncio
from fastapi import WebSocket
from datetime import datetime

LOG_ROOT = "logs"


async def stream_log(websocket: WebSocket, module: str):
    await websocket.accept()
    today = datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(LOG_ROOT, module, f"{today}.log")

    if not os.path.exists(file_path):
        await websocket.close()
        return

    # Datei öffnen + ans Ende springen
    with open(file_path, "r", encoding="utf-8") as f:
        f.seek(0, os.SEEK_END)

        while True:
            line = f.readline()
            if not line:
                await asyncio.sleep(0.5)
                continue

            await websocket.send_text(line)
