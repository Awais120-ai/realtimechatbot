import asyncio
import json
import websockets 


USER_1_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODcyMDUwNzMsInN1YiI6IjEiLCJ0eXBlIjoiYWNjZXNzIn0.zvnpbGblEmbHahZiSYEJ3_gmNK9fjekw0w6xnVSe0ag"
USER_2_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODcyMDUxMjYsInN1YiI6IjIiLCJ0eXBlIjoiYWNjZXNzIn0.kh-uZAT6ZFRQB5MixZd2I10k3g1sEirlmEyOslHXxI0"

URL = "ws://localhost:8001/api/v1/ws"


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

            # User 2 listens for typing event
            listener = asyncio.create_task(
                user_2.recv()
            )

            await asyncio.sleep(1)

            typing_payload = {
                "type": "typing",
                "conversation_id": 1,
            }

            await user_1.send(
                json.dumps(typing_payload)
            )

            print("\n[USER 1] Typing event sent:")
            print(typing_payload)

            try:
                response = await asyncio.wait_for(
                    listener,
                    timeout=10,
                )

                print("\n[USER 2] Received:")
                print(response)

                data = json.loads(response)

                if (
                    data.get("type") in ["user_typing", "typing"]
                    and (data.get("conversationId") == 1 or data.get("conversation_id") == 1)
                    and (data.get("userId") == 1 or data.get("user_id") == 1)
                ):
                    print(
                        "\n✅ TYPING INDICATOR TEST PASSED"
                    )

                    print(
                        "\n==================================="
                    )
                    print(
                        "TYPING INDICATOR TEST PASSED!"
                    )
                    print(
                        "==================================="
                    )

                else:
                    print(
                        "\n❌ Unexpected response:"
                    )
                    print(data)

            except asyncio.TimeoutError:
                print(
                    "\n❌ User 2 did not receive "
                    "typing event."
                )


if __name__ == "__main__":
    asyncio.run(test())