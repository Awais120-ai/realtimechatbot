
import asyncio
import json
import websockets


USER_1_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODcxNDQ1MjEsInN1YiI6IjEiLCJ0eXBlIjoiYWNjZXNzIn0.ELHosA7AoyXz8f9n2WsOkGxY3eQLvDO8VtkY3MsmTFs"
USER_2_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODcxNDQ1NjUsInN1YiI6IjIiLCJ0eXBlIjoiYWNjZXNzIn0.YbRzVSHgCDPVsP9l3CT_FrELENFZbKatzfPSxNZDuqQ"

URL = "ws://localhost:8001/api/v1/ws"


async def receive_expected_message(
    user_name,
    websocket,
    expected_sender_id,
    expected_content,
):
    try:
        while True:
            message = await asyncio.wait_for(
                websocket.recv(),
                timeout=10,
            )

            print(f"\n[{user_name}] Received:")
            print(message)

            data = json.loads(message)

            # Ignore non-message responses
            if data.get("type") != "message":
                continue

            # Check sender
            if data.get("sender_id") != expected_sender_id:
                print(
                    f"[{user_name}] Ignoring message from "
                    f"sender {data.get('sender_id')}"
                )
                continue

            # Check content
            if data.get("content") != expected_content:
                print(
                    f"[{user_name}] Ignoring unexpected content."
                )
                continue

            print(
                f"[{user_name}] Expected message received successfully!"
            )

            return data

    except asyncio.TimeoutError:
        print(
            f"\n[ERROR] {user_name} did not receive "
            f"the expected message within 10 seconds."
        )
        return None

    except Exception as e:
        print(
            f"\n[{user_name}] Error "
            f"({type(e).__name__}): {e}"
        )
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

            # ==========================================
            # USER 1 -> USER 2
            # ==========================================

            print("\n--- User 1 -> User 2 ---")

            expected_message_1 = (
                "Hello from User 1!"
            )

            user_2_listener = asyncio.create_task(
                receive_expected_message(
                    "USER 2",
                    user_2,
                    expected_sender_id=1,
                    expected_content=expected_message_1,
                )
            )

            await asyncio.sleep(1)

            message_1 = {
                "conversation_id": 1,
                "content": expected_message_1,
            }

            await user_1.send(
                json.dumps(message_1)
            )

            print("[USER 1] Sent:")
            print(message_1)

            received_1 = await user_2_listener

            if received_1 is None:
                print("\n❌ USER 1 -> USER 2 TEST FAILED")
                return

            print(
                "\n✅ USER 1 -> USER 2 TEST PASSED"
            )

            # ==========================================
            # USER 2 -> USER 1
            # ==========================================

            print("\n--- User 2 -> User 1 ---")

            expected_message_2 = (
                "Hello from User 2!"
            )

            user_1_listener = asyncio.create_task(
                receive_expected_message(
                    "USER 1",
                    user_1,
                    expected_sender_id=2,
                    expected_content=expected_message_2,
                )
            )

            await asyncio.sleep(1)

            message_2 = {
                "conversation_id": 1,
                "content": expected_message_2,
            }

            await user_2.send(
                json.dumps(message_2)
            )

            print("[USER 2] Sent:")
            print(message_2)

            received_2 = await user_1_listener

            if received_2 is None:
                print("\n❌ USER 2 -> USER 1 TEST FAILED")
                return

            print(
                "\n✅ USER 2 -> USER 1 TEST PASSED"
            )

            # ==========================================
            # FINAL RESULT
            # ==========================================

            print("\n===================================")
            print("TWO-WAY REAL-TIME CHAT TEST PASSED!")
            print("===================================")


if __name__ == "__main__":
    asyncio.run(test())

