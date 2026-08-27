import asyncio
import json

import websockets


USER_1_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODcyMjY1ODQsInN1YiI6IjEiLCJ0eXBlIjoiYWNjZXNzIn0.vRef6xv7HmISxgvxsuotym29ZLlAtV_KRyWjprSNr24"
USER_2_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODcyMjY1NDYsInN1YiI6IjIiLCJ0eXBlIjoiYWNjZXNzIn0.vixtG26tMzOCJjIMpAAP4F51MxkV1i4ztvSNpPOyPKc"

URL = "ws://localhost:8001/api/v1/ws"


async def receive_event(websocket, expected_type, expected_user_id):
    try:
        while True:
            response = await asyncio.wait_for(
                websocket.recv(),
                timeout=10,
            )

            print("\n[RECEIVED]")
            print(response)

            data = json.loads(response)

            if (
                data.get("type") == expected_type
                and data.get("user_id") == expected_user_id
            ):
                return data

    except asyncio.TimeoutError:
        return None


async def test():

    user_1_url = f"{URL}?token={USER_1_TOKEN}"
    user_2_url = f"{URL}?token={USER_2_TOKEN}"

    # =========================================================
    # USER 2 CONNECTS FIRST
    # =========================================================

    print("Connecting User 2 first...")

    async with websockets.connect(
        user_2_url,
        open_timeout=10,
    ) as user_2:

        print("User 2 connected successfully!")

        # =====================================================
        # USER 1 CONNECTS SECOND
        # =====================================================

        print("\nConnecting User 1...")

        async with websockets.connect(
            user_1_url,
            open_timeout=10,
        ) as user_1:

            print("User 1 connected successfully!")

            # =================================================
            # TEST USER 1 ONLINE EVENT
            # =================================================

            print("\n--- Testing User 1 online event ---")

            online_event = await receive_event(
                user_2,
                "user_online",
                1,
            )

            if online_event:

                print("\n✅ USER ONLINE EVENT PASSED")

                print("\nOnline event:")
                print(online_event)

            else:

                print(
                    "\n❌ USER ONLINE EVENT NOT RECEIVED"
                )

            # =================================================
            # CLOSE USER 1
            # =================================================

            print(
                "\n--- Closing User 1 connection ---"
            )

            await user_1.close()

            print(
                "User 1 connection closed."
            )

        # =====================================================
        # TEST USER 1 OFFLINE EVENT
        # =====================================================

        print(
            "\n--- Waiting for User 1 offline event ---"
        )

        offline_event = await receive_event(
            user_2,
            "user_offline",
            1,
        )

        if offline_event:

            print(
                "\n✅ USER OFFLINE EVENT PASSED"
            )

            if offline_event.get("last_seen"):

                print("\nLast seen:")
                print(
                    offline_event["last_seen"]
                )

            else:

                print(
                    "\n⚠️ last_seen missing!"
                )

        else:

            print(
                "\n❌ USER OFFLINE EVENT NOT RECEIVED"
            )

        # =====================================================
        # FINAL RESULT
        # =====================================================

        print(
            "\n==================================="
        )

        print(
            "ONLINE / OFFLINE TEST COMPLETED!"
        )

        print(
            "===================================")


if __name__ == "__main__":
    asyncio.run(test())