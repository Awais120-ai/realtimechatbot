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

        # User 1 is already connected.
        # Now connect User 2 and listen for User 2's online event.
        user_1_listener = asyncio.create_task(
            user_1.recv()
        )

        print("Connecting User 2...")

        async with websockets.connect(
            user_2_url,
            open_timeout=10,
        ) as user_2:

            print("User 2 connected successfully!")

            try:
                message = await asyncio.wait_for(
                    user_1_listener,
                    timeout=10,
                )

                print("\n[USER 1] Received:")
                print(message)

                data = json.loads(message)

                if (
                    data.get("type") == "user_online"
                    and data.get("user_id") == 2
                ):
                    print(
                        "\n✅ USER 2 ONLINE EVENT TEST PASSED"
                    )
                else:
                    print(
                        "\n❌ Unexpected online event:"
                    )
                    print(data)
                    return

            except asyncio.TimeoutError:
                print(
                    "\n❌ User 1 did not receive "
                    "User 2 online event."
                )
                return

            # Keep User 2 connected briefly
            await asyncio.sleep(2)

        # User 2 connection is now closed.
        # User 1 should receive offline event.
        print("\nUser 2 disconnected.")

        try:
            while True:
                message = await asyncio.wait_for(
                    user_1.recv(),
                    timeout=10,
                )

                print("\n[USER 1] Received:")
                print(message)

                data = json.loads(message)

                if (
                    data.get("type") == "user_offline"
                    and data.get("user_id") == 2
                ):
                    print(
                        "\n✅ USER 2 OFFLINE EVENT TEST PASSED"
                    )

                    print("\n===================================")
                    print(
                        "ONLINE/OFFLINE EVENT TEST PASSED!"
                    )
                    print("===================================")

                    return

        except asyncio.TimeoutError:
            print(
                "\n❌ User 1 did not receive "
                "User 2 offline event."
            )


if __name__ == "__main__":
    asyncio.run(test())