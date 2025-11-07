import motor.motor_asyncio
from config import DATABASE_URL, BOTS

# Database instances will be initialized at the end of the file

class Database:
    
    def __init__(self, uri, database_name, version="v1"):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.users_col = self.db.users
        self.channels_col = self.db.channels
        self.version = version  # Add version identifier for logging

    def new_user(self, id, name):
        return dict(
            id = id,
            name = name,
            sessions = {},  # Changed from single session to dict of sessions {phone: session_string}
            current_active_id = None,  # Track which account is active for channel management
        )
    
    def new_channel(self, user_id, channel_id, base_username, interval):
        return dict(
            user_id = user_id,
            channel_id = channel_id,
            base_username = base_username,
            interval = interval,
            is_active = True,
            last_changed = None,
            owner_phone = None,  # Store which phone number owns this channel
        )
    
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.users_col.insert_one(user)
    
    async def is_user_exist(self, id):
        user = await self.users_col.find_one({'id':int(id)})
        return bool(user)
    
    async def total_users_count(self):
        count = await self.users_col.count_documents({})
        return count

    async def get_all_users(self):
        return self.users_col.find({})

    async def delete_user(self, user_id):
        await self.users_col.delete_many({'id': int(user_id)})

    async def add_session(self, user_id, phone_number, session_string):
        """Add or update a session for a specific phone number"""
        await self.users_col.update_one(
            {'id': int(user_id)}, 
            {'$set': {f'sessions.{phone_number}': session_string}}
        )

    async def get_session(self, user_id, phone_number=None):
        """Get session for a user. If phone_number is None, return first available session"""
        user = await self.users_col.find_one({'id': int(user_id)})
        if not user:
            return None
        
        sessions = user.get('sessions', {})
        if not sessions:
            return None
        
        if phone_number:
            return sessions.get(phone_number)
        else:
            # Return first available session
            return next(iter(sessions.values())) if sessions else None

    async def get_all_sessions(self, user_id):
        """Get all sessions for a user"""
        user = await self.users_col.find_one({'id': int(user_id)})
        if not user:
            return {}
        return user.get('sessions', {})

    async def remove_session(self, user_id, phone_number):
        """Remove a specific session"""
        await self.users_col.update_one(
            {'id': int(user_id)},
            {'$unset': {f'sessions.{phone_number}': 1}}
        )
        await self.users_col.update_one(
            {'id': int(user_id)},
            {'$unset': {'sessions': ''}}
        )

    async def remove_all_sessions(self, user_id):
        """Remove all sessions for a user"""
        await self.users_col.update_one(
            {'id': int(user_id)},
            {'$set': {'sessions': {}}}
        )

    async def set_active_id(self, user_id, phone_number):
        """Set which account is active for channel management"""
        await self.users_col.update_one(
            {'id': int(user_id)},
            {'$set': {'current_active_id': phone_number}}
        )
        
    async def get_active_id(self, user_id):
        """Get the active account for channel management"""
        user = await self.users_col.find_one({'id': int(user_id)})
        if not user:
            return None
        return user.get('current_active_id')

    async def set_session(self, id, session, phone_number=None):
        """Deprecated: Use add_session or remove_session instead"""
        if session is None:
            if phone_number:
                await self.remove_session(id, phone_number)
            else:
                await self.remove_all_sessions(id)
        else:
            await self.add_session(id, phone_number or "default", session)

    async def add_channel(self, user_id, channel_id, base_username, interval):
        channel = self.new_channel(user_id, channel_id, base_username, interval)
        await self.channels_col.insert_one(channel)

    async def get_user_channels(self, user_id):
        return await self.channels_col.find({'user_id': int(user_id), 'is_active': True}).to_list(None)

    async def get_all_active_channels(self):
        return await self.channels_col.find({'is_active': True}).to_list(None)

    async def stop_channel(self, channel_id):
        await self.channels_col.update_one({'channel_id': int(channel_id)}, {'$set': {'is_active': False}})

    async def resume_channel(self, channel_id):
        await self.channels_col.update_one({'channel_id': int(channel_id)}, {'$set': {'is_active': True}})

    async def delete_channel(self, channel_id):
        await self.channels_col.delete_one({'channel_id': int(channel_id)})

    async def update_last_changed(self, channel_id, timestamp):
        await self.channels_col.update_one({'channel_id': int(channel_id)}, {'$set': {'last_changed': timestamp}})

    async def get_channel(self, channel_id):
        return await self.channels_col.find_one({'channel_id': int(channel_id)})
        
    async def update_channel_owner(self, channel_id, phone_number):
        """Update which phone number owns this channel"""
        await self.channels_col.update_one(
            {'channel_id': int(channel_id)}, 
            {'$set': {'owner_phone': phone_number}}
        )
        
    async def get_channel_owner(self, channel_id):
        """Get the phone number that owns this channel"""
        channel = await self.get_channel(channel_id)
        if not channel:
            return None
        return channel.get('owner_phone')

# Create database instances for each bot configuration
db_instances = {}
for bot_config in BOTS:
    db_name = bot_config.get("db_name", "vjlinkchangerbot")
    version = bot_config.get("version", "v1")
    db_instances[version] = Database(DATABASE_URL, db_name, version)

# For backward compatibility
if "v1" in db_instances:
    db = db_instances["v1"]
elif BOTS:
    db = Database(DATABASE_URL, BOTS[0]["db_name"])
else:
    db = Database(DATABASE_URL, "vjlinkchangerbot")
