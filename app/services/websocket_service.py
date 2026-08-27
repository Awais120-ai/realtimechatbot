from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import WebSocket
from sqlalchemy import update

from app.database.session import AsyncSessionLocal
from app.models.user import User


class ConnectionManager:

    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    # =========================================================
    # CONNECT USER
    # =========================================================

    async def connect(
        self,
        user_id: int,
        websocket: WebSocket,
    ):
        print("========== WS CONNECT ==========")
        print("Connecting user:", user_id)

        # User is considered offline before this connection
        was_offline = user_id not in self.active_connections

        # Accept WebSocket
        await websocket.accept()

        # Create connection list for user
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []

        # Prevent duplicate websocket object
        if websocket not in self.active_connections[user_id]:
            self.active_connections[user_id].append(websocket)

        print(
            "User connected:",
            user_id,
            "connections:",
            len(self.active_connections[user_id]),
        )

        print(
            "Active users:",
            list(self.active_connections.keys()),
        )

        # =====================================================
        # MARK USER ONLINE
        # =====================================================

        async with AsyncSessionLocal() as db:

            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    is_online=True,
                )
            )

            await db.commit()

        # =====================================================
        # BROADCAST USER ONLINE
        # =====================================================

        if was_offline:

            for connected_user_id in list(
                self.active_connections.keys()
            ):

                if connected_user_id == user_id:
                    continue

                await self.send_to_user(
                    user_id=connected_user_id,
                    message={
                        "type": "user_online",
                        "user_id": user_id,
                    },
                )

        print("================================")

    # =========================================================
    # DISCONNECT USER
    # =========================================================

    async def disconnect(
        self,
        user_id: int,
        websocket: Optional[WebSocket] = None,
    ):
        print("========== WS DISCONNECT ==========")
        print("Disconnecting user:", user_id)

        if user_id not in self.active_connections:
            print(
                "User has no active connection:",
                user_id,
            )
            print("==================================")
            return

        # =====================================================
        # REMOVE SPECIFIC CONNECTION
        # =====================================================

        if websocket is not None:

            if websocket in self.active_connections[user_id]:

                self.active_connections[user_id].remove(
                    websocket
                )

                print(
                    "Removed one websocket for user:",
                    user_id,
                )

            # -------------------------------------------------
            # User still has another connection
            # -------------------------------------------------

            if self.active_connections[user_id]:

                print(
                    "User still has active connections:",
                    len(
                        self.active_connections[user_id]
                    ),
                )

                print("==================================")
                return

            # -------------------------------------------------
            # No connections left
            # -------------------------------------------------

            self.active_connections.pop(
                user_id,
                None,
            )

        # =====================================================
        # REMOVE ALL CONNECTIONS
        # =====================================================

        else:

            self.active_connections.pop(
                user_id,
                None,
            )

        # =====================================================
        # MARK USER OFFLINE
        # =====================================================

        last_seen = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as db:

            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    is_online=False,
                    last_seen=last_seen,
                )
            )

            await db.commit()

        print(
            "User marked offline:",
            user_id,
        )

        # =====================================================
        # BROADCAST OFFLINE EVENT
        # =====================================================

        for connected_user_id in list(
            self.active_connections.keys()
        ):

            if connected_user_id == user_id:
                continue

            await self.send_to_user(
                user_id=connected_user_id,
                message={
                    "type": "user_offline",
                    "user_id": user_id,
                    "last_seen": last_seen.isoformat(),
                },
            )

        print(
            "Active users after disconnect:",
            list(self.active_connections.keys()),
        )

        print("==================================")

    # =========================================================
    # SEND MESSAGE TO SPECIFIC USER
    # =========================================================

    async def send_to_user(
        self,
        user_id: int,
        message: dict,
    ):
        print("========== SEND TO USER ==========")

        print(
            "Target user_id:",
            user_id,
        )

        print(
            "Event type:",
            message.get("type"),
        )

        print(
            "Active connection users:",
            list(
                self.active_connections.keys()
            ),
        )

        # =====================================================
        # USER NOT CONNECTED
        # =====================================================

        if user_id not in self.active_connections:

            print(
                "NO ACTIVE CONNECTION FOR USER:",
                user_id,
            )

            print("=================================")

            return

        # =====================================================
        # GET USER CONNECTIONS
        # =====================================================

        connections = list(
            self.active_connections[user_id]
        )

        print(
            "Connections for user:",
            user_id,
            "count:",
            len(connections),
        )

        # =====================================================
        # SEND TO ALL USER CONNECTIONS
        # =====================================================

        dead_connections: List[WebSocket] = []

        for websocket in connections:

            try:

                await websocket.send_json(
                    message
                )

                print(
                    "MESSAGE SENT SUCCESSFULLY TO USER:",
                    user_id,
                )

            except Exception as exc:

                print(
                    "MESSAGE SEND FAILED:",
                    "user_id=",
                    user_id,
                    "error=",
                    repr(exc),
                )

                dead_connections.append(
                    websocket
                )

        # =====================================================
        # REMOVE DEAD CONNECTIONS
        # =====================================================

        for websocket in dead_connections:

            # Remove directly from list first
            # so disconnect() does not interfere
            # with currently iterating connections.

            if (
                user_id in self.active_connections
                and websocket
                in self.active_connections[user_id]
            ):

                self.active_connections[
                    user_id
                ].remove(websocket)

        # =====================================================
        # IF USER HAS NO CONNECTIONS LEFT
        # THEN FULLY DISCONNECT USER
        # =====================================================

        if (
            user_id in self.active_connections
            and not self.active_connections[user_id]
        ):

            self.active_connections.pop(
                user_id,
                None,
            )

            last_seen = datetime.now(
                timezone.utc
            )

            async with AsyncSessionLocal() as db:

                await db.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(
                        is_online=False,
                        last_seen=last_seen,
                    )
                )

                await db.commit()

            print(
                "User had no live connections. "
                "Marked offline:",
                user_id,
            )

        print("=================================")

    # =========================================================
    # BROADCAST MESSAGE TO ALL USERS
    # =========================================================

    async def broadcast(
        self,
        message: dict,
    ):
        print("========== BROADCAST ==========")

        print(
            "Event type:",
            message.get("type"),
        )

        for user_id in list(
            self.active_connections.keys()
        ):

            await self.send_to_user(
                user_id=user_id,
                message=message,
            )

        print("================================")


# =============================================================
# GLOBAL CONNECTION MANAGER
# =============================================================

manager = ConnectionManager()