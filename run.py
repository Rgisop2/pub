import asyncio
from bot import Bot
from config import BOTS
from plugins.database import db_instances

async def main():
    print("Starting TechVJ Multi-Bot System...")

    bots = []

    # Initialize bot instances
    for bot_config in BOTS:
        version = bot_config.get("version", "v1")
        token = bot_config.get("token")

        db = db_instances.get(version)
        if not db:
            print(f"[ERROR] Database instance not found for {version}")
            continue
        if not token:
            print(f"[ERROR] Bot token missing for {version}")
            continue

        bot = Bot(bot_token=token, db_instance=db, version=version)
        bots.append(bot)
        print(f"Prepared bot {version}")

    if not bots:
        print("No bots to start. Check your config.")
        return

    # Start all bots concurrently
    try:
        await asyncio.gather(*(b.start() for b in bots))
        print("All bots started successfully!")

        # Keep the program running until interrupted
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        # Graceful shutdown path
        pass
    finally:
        # Stop all bots concurrently
        await asyncio.gather(*(b.stop() for b in bots), return_exceptions=True)
        print("All bots stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting...")