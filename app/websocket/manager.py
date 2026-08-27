from typing import Dict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Structure: { conversation_id: { user_id: WebSocket } }
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, conversation_id: str, user_id: str):
        await websocket.accept()
        conversation_id = str(conversation_id)
        user_id = str(user_id)

        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = {}
        
        self.active_connections[conversation_id][user_id] = websocket

    def disconnect(self, conversation_id: str, user_id: str):
        conversation_id = str(conversation_id)
        user_id = str(user_id)

        if conversation_id in self.active_connections:
            self.active_connections[conversation_id].pop(user_id, None)
            if not self.active_connections[conversation_id]:
                del self.active_connections[conversation_id]

    async def broadcast_to_conversation(
        self, conversation_id: str, message: dict, exclude_user_id: str = None
    ):
        conversation_id = str(conversation_id)
        if conversation_id in self.active_connections:
            for user_id, connection in list(self.active_connections[conversation_id].items()):
                if exclude_user_id and str(user_id) == str(exclude_user_id):
                    continue
                try:
                    await connection.send_json(message)
                except Exception:
                    # Stale connection clean up
                    self.disconnect(conversation_id, user_id)

connection_manager = ConnectionManager()