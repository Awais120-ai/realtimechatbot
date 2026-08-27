import asyncio
import json
import websockets


USER_1_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODcyMDUwNzMsInN1YiI6IjEiLCJ0eXBlIjoiYWNjZXNzIn0.zvnpbGblEmbHahZiSYEJ3_gmNK9fjekw0w6xnVSe0ag"
USER_2_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODcyMDUxMjYsInN1YiI6IjIiLCJ0eXBlIjoiYWNjZXNzIn0.kh-uZAT6ZFRQB5MixZd2I10k3g1sEirlmEyOslHXxI0"

URL = "ws://localhost:8001/api/v1/ws"


async def receive_message(user_name, websocket):
    try:
        message = await websocket.recv()

        print(f"\n[{user_name}] Received:")
        print(message)

        return json.loads(message)

    except Exception as e:
        print(f"\n[{user_name}] Error ({type(e).__name__}): {e}")
        return None


async def test():

    user_1_url = f"{URL}?token={USER_1_TOKEN}"
    user_2_url = f"{URL}?token={USER_2_TOKEN}"

    print("Connecting User 1...")

    async with websockets.connect(
        user_1_url,
        open_timeout=10,
    ) as user_1:

        print("User 1 connected successfully!")

        print("Connecting User 2...")

        async with websockets.connect(
            user_2_url,
            open_timeout=10,
        ) as user_2:

            print("User 2 connected successfully!")

            # --------------------------------
            # USER 1 START TYPING
            # --------------------------------

            print("\n--- User 1 starts typing ---")

            typing_listener = asyncio.create_task(
                receive_message("USER 2", user_2)
            )

            await asyncio.sleep(1)

            typing_event = {
                "type": "typing",
                "conversation_id": 1,
            }

            await user_1.send(
                json.dumps(typing_event)
            )

            print("[USER 1] Typing event sent:")
            print(typing_event)

            try:
                response = await asyncio.wait_for(
                    typing_listener,
                    timeout=10,
                )
            except asyncio.TimeoutError:
                print("❌ User 2 did not receive typing event.")
                return

            if (
                response
                and response.get("type") in ["user_typing", "typing"]
                and (response.get("conversationId") == 1 or response.get("conversation_id") == 1)
                and (response.get("userId") == 1 or response.get("user_id") == 1)
            ):
                print("✅ TYPING EVENT TEST PASSED")
            else:
                print("❌ Unexpected typing event:")
                print(response)
                return

            # --------------------------------
            # USER 1 STOPS TYPING
            # --------------------------------

            print("\n--- User 1 stops typing ---")

            stop_typing_listener = asyncio.create_task(
                receive_message("USER 2", user_2)
            )

            await asyncio.sleep(1)

            stop_typing_event = {
                "type": "stop_typing",
                "conversation_id": 1,
            }

            await user_1.send(
                json.dumps(stop_typing_event)
            )

            print("[USER 1] Stop typing event sent:")
            print(stop_typing_event)

            try:
                response = await asyncio.wait_for(
                    stop_typing_listener,
                    timeout=10,
                )
            except asyncio.TimeoutError:
                print("❌ User 2 did not receive stop_typing event.")
                return

            if (
                response
                and response.get("type") in ["user_stopped_typing", "stop_typing"]
                and (response.get("conversationId") == 1 or response.get("conversation_id") == 1)
                and (response.get("userId") == 1 or response.get("user_id") == 1)
            ):
                print("✅ STOP TYPING EVENT TEST PASSED")
            else:
                print("❌ Unexpected stop_typing event:")
                print(response)
                return

            print("\n===================================")
            print("TYPING + STOP TYPING TEST PASSED!")
            print("===================================")


if __name__ == "__main__":
    asyncio.run(test())