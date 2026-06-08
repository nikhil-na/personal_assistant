import asyncio
from client.assistant import assistant

if __name__ == "__main__":
    print("🚀 Starting Personal Assistant App...")
    # This boots up the entire client/server lifecycle from one central place
    asyncio.run(assistant())