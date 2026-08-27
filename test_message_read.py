import asyncio
import json

import websockets


USER_1_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODcyMDUwNzMsInN1YiI6IjEiLCJ0eXBlIjoiYWNjZXNzIn0.zvnpbGblEmbHahZiSYEJ3_gmNK9fjekw0w6xnVSe0ag"

USER_2_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODcyMDUxMjYsInN1YiI6IjIiLCJ0eXBlIjoiYWNjZXNzIn0.kh-uZAT6ZFRQB5MixZd2I10k3g1sEirlmEyOslHXxI0"

URL = "ws://localhost:8001/api/v1/ws"


async def receive_until(
    websocket,
    expected_type,
    expected_message_id=None,
    timeout=10,
):
    """
    Keep receiving messages until the expected event arrives.
    Ignore unrelated WebSocket events.
    """

    while True:

        response = await asyncio.wait_for(
            websocket.recv(),
            timeout=timeout,
        )

        print("\n[RECEIVED]")
        print(response)

        data = json.loads(response)

        # Check event type
        if data.get("type") != expected_type:
            print(
                f"[INFO] Ignoring event: {data.get('type')}"
            )
            continue

        # If message_id is required, check it
        if expected_message_id is not None:

            if data.get("message_id") != expected_message_id:
                print(
                    f"[INFO] Ignoring message_id: "
                    f"{data.get('message_id')}"
                )
                continue

        return data


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

            # ==========================================
            # USER 1 SENDS MESSAGE
            # ==========================================

            message = {
                "conversation_id": 1,
                "content": "Read this message!",
            }

            await user_1.send(
                json.dumps(message)
            )

            print("\n[USER 1] Message sent:")
            print(message)

            # ==========================================
            # USER 2 RECEIVES MESSAGE
            # ==========================================

            message_data = await receive_until(
                user_2,
                expected_type="message",
                timeout=10,
            )

            print("\n[USER 2] Message received:")
            print(message_data)

            message_id = message_data.get("id")

            if not message_id:
                print(
                    "\n❌ Message ID was not received."
                )
                return

            print(
                f"\n[USER 2] Message ID: {message_id}"
            )

            # ==========================================
            # USER 2 MARKS MESSAGE AS READ
            # ==========================================

            read_event = {
                "type": "message_read",
                "message_id": message_id,
            }

            await user_2.send(
                json.dumps(read_event)
            )

            print(
                "\n[USER 2] Read event sent:"
            )
            print(read_event)

            # ==========================================
            # USER 1 WAITS FOR MESSAGE_READ EVENT
            # ==========================================

            read_data = await receive_until(
                user_1,
                expected_type="message_read",
                expected_message_id=message_id,
                timeout=10,
            )

            print(
                "\n[USER 1] Read event received:"
            )
            print(read_data)

            # ==========================================
            # VERIFY
            # ==========================================

            if (
                read_data.get("type") == "message_read"
                and read_data.get("message_id") == message_id
                and read_data.get("user_id") == 2
            ):

                print(
                    "\n✅ MESSAGE READ EVENT TEST PASSED"
                )

            else:

                print(
                    "\n❌ MESSAGE READ EVENT FAILED"
                )

                print(
                    "Expected:"
                )

                print(
                    {
                        "type": "message_read",
                        "message_id": message_id,
                        "user_id": 2,
                    }
                )

                print(
                    "Received:"
                )

                print(read_data)

                return

            # ==========================================
            # FINAL RESULT
            # ==========================================

            print("\n===================================")
            print("MESSAGE READ / SEEN TEST PASSED!")
            print("===================================")


if __name__ == "__main__":
    asyncio.run(test())