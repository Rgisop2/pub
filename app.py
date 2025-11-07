import asyncio
from flask import Flask
from bot import Bot
from config import BOTS
from plugins.database import db_instances

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'TechVJ Multi-Bot System'

async def start_bots():
    """Start all configured bots"""
    # Create and start all bot instances
    for bot_config in BOTS:
        version = bot_config.get("version", "v1")
        token = bot_config.get("token")
        db_name = bot_config.get("db_name")
        
        # Get the database instance for this bot
        db = db_instances.get(version)
        if not db:
            print(f"[ERROR] Database instance not found for {version}")
            continue
            
        # Create and start the bot
        bot = Bot(bot_token=token, db_instance=db, version=version)
        await bot.start()
    
    # Keep the program running
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    # Run the Flask app in a separate thread
    from threading import Thread
    flask_thread = Thread(target=lambda: app.run(host='0.0.0.0', port=8080))
    flask_thread.daemon = True
    flask_thread.start()
    
    # Run the bot in the main thread
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_bots())
    except KeyboardInterrupt:
        # Stop all bot instances
        for instance_name, bot_instance in Bot.instances.items():
            loop.run_until_complete(bot_instance.stop())
        print("Bots stopped")
