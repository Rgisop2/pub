# Link Auto-Changer Core Functionality
import asyncio
import random
import string
import time
import queue
import threading
from pyrogram import Client
from plugins.database import db, db_instances
from config import LOG_CHANNEL, API_ID, API_HASH, BOTS

# Global variable to store pending log messages per bot version
pending_logs = {}
for bot_config in BOTS:
    version = bot_config.get("version", "v1")
    pending_logs[version] = []

# Function to safely send log messages
def send_log(message, version="v1"):
    """Add a message to the log queue for a specific bot version"""
    print(message)  # Always print to console
    if LOG_CHANNEL:
        # Store the message for later processing by the main thread
        if version not in pending_logs:
            pending_logs[version] = []
        pending_logs[version].append(message)

# Function to process pending logs from the main thread
async def process_pending_logs(bot):
    """Process any pending log messages using the main bot instance"""
    global pending_logs
    
    if not LOG_CHANNEL:
        return
    
    version = bot.version
    if version not in pending_logs or not pending_logs[version]:
        return
    
    # Process all pending logs for this bot version
    logs_to_process = pending_logs[version].copy()
    pending_logs[version] = []
    
    for message in logs_to_process:
        try:
            await bot.send_message(LOG_CHANNEL, message)
        except Exception as e:
            print(f"[{version}] Error sending log message: {e}")
            # If failed, add back to pending logs
            pending_logs[version].append(message)

class LinkChanger:
    def __init__(self):
        self.active_tasks = {}
        self.client_instances = {}  # Store client instances per phone number
        self.client_locks = {}  # Locks to prevent concurrent access to client instances

    def generate_random_suffix(self):
        """Generate random 2 characters (letters or digits)"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=2))

    async def get_client(self, user_id, phone_number, version="v1"):
        """Get or create a client instance for a phone number"""
        client_key = f"{version}_{user_id}_{phone_number}"
        
        # Create a lock for this client if it doesn't exist
        if client_key not in self.client_locks:
            self.client_locks[client_key] = asyncio.Lock()
        
        # Acquire the lock to prevent concurrent access
        async with self.client_locks[client_key]:
            if client_key not in self.client_instances or self.client_instances[client_key] is None:
                # Get the database instance for this bot version
                db = db_instances.get(version)
                if not db:
                    print(f"[{version}] No database instance found for version {version}")
                    return None
                
                # Get the session string
                user_session = await db.get_session(user_id, phone_number)
                if not user_session:
                    return None
                
                # Create a new client instance
                client = Client(
                    f"session_{version}_{phone_number}",  # Use a unique name with version
                    session_string=user_session,
                    api_id=API_ID,
                    api_hash=API_HASH,
                    in_memory=True
                )
                await client.connect()
                self.client_instances[client_key] = client
            
            return self.client_instances[client_key]

    async def change_channel_link(self, user_id, channel_id, base_username, phone_number, version="v1"):
        """Change the channel's public link with random suffix"""
        try:
            # Get the client for this phone number
            client = await self.get_client(user_id, phone_number, version)
            if not client:
                return False, "Failed to get client instance"
            
            # Generate new username
            new_suffix = self.generate_random_suffix()
            new_username = f"{base_username}{new_suffix}"
            
            # Try to set the new username
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    await client.set_chat_username(channel_id, new_username)
                    db_inst = db_instances.get(version, db)
                    await db_inst.update_last_changed(channel_id, time.time())
                    return True, new_username
                except Exception as e:
                    if "USERNAME_OCCUPIED" in str(e) or "occupied" in str(e).lower():
                        # Username taken, try another
                        new_suffix = self.generate_random_suffix()
                        new_username = f"{base_username}{new_suffix}"
                        continue
                    else:
                        return False, str(e)
            
            return False, "Could not find available username after 5 attempts"
        except Exception as e:
            return False, str(e)

    async def start_channel_rotation(self, user_id, channel_id, base_username, interval, phone_number, version="v1"):
        """Start automatic link rotation for a channel"""
        # Use phone_number in task_key to make it unique per phone number
        task_key = f"{version}_{phone_number}_{channel_id}"
        
        if task_key in self.active_tasks:
            return False, "Channel rotation already active"
        
        try:
            # Verify the client can be created
            client = await self.get_client(user_id, phone_number, version)
            if not client:
                return False, "User session not found"
            
            # Store the channel ownership in the database
            db_inst = db_instances.get(version, db)
            await db_inst.update_channel_owner(channel_id, phone_number)
            
            async def rotation_loop():
                while True:
                    try:
                        success, result = await self.change_channel_link(user_id, channel_id, base_username, phone_number, version)
                        if success:
                            log_message = f"[{version}] ✅ Link changed for channel {channel_id} by {phone_number} → {result}"
                            send_log(log_message, version)
                        else:
                            log_message = f"[{version}] ⚠ Failed to update link for channel {channel_id} by {phone_number} ({result})"
                            send_log(log_message, version)
                        await asyncio.sleep(interval)
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        send_log(f"[{version}] Error in rotation loop: {e}", version)
                        await asyncio.sleep(interval)
            
            # Create a new task for this channel rotation
            task = asyncio.create_task(rotation_loop())
            self.active_tasks[task_key] = task
            
            # Log resumption
            send_log(f"[{version}] 🔄 Resumed rotation for channel {channel_id} by {phone_number}", version)
                    
            return True, "Channel rotation started"
        except Exception as e:
            return False, str(e)

    async def stop_channel_rotation(self, user_id, channel_id, phone_number=None, version="v1"):
        """Stop automatic link rotation for a channel"""
        # Use phone_number in task_key to make it unique per phone number
        if phone_number:
            task_key = f"{version}_{phone_number}_{channel_id}"
            
            if task_key not in self.active_tasks:
                return False, "Channel rotation not active"
            
            try:
                self.active_tasks[task_key].cancel()
                del self.active_tasks[task_key]
                return True, "Channel rotation stopped"
            except Exception as e:
                return False, str(e)
        else:
            # Stop all rotations for this channel under this version
            matching_keys = [k for k in list(self.active_tasks.keys()) if k.endswith(f"_{channel_id}") and k.startswith(f"{version}_")]
            if not matching_keys:
                return False, "Channel rotation not active"
            try:
                for k in matching_keys:
                    self.active_tasks[k].cancel()
                    del self.active_tasks[k]
                return True, "Channel rotation stopped"
            except Exception as e:
                return False, str(e)

    async def resume_channel_rotation(self, user_id, channel_id, base_username, interval, phone_number=None, version="v1"):
        """Resume automatic link rotation for a channel"""
        return await self.start_channel_rotation(user_id, channel_id, base_username, interval, phone_number, version)

    async def get_active_channels_for_user(self, user_id):
        """Get all active channels for a user"""
        return await db.get_user_channels(user_id)

link_changer = LinkChanger()
