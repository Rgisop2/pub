# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import traceback
from pyrogram.types import Message
from pyrogram import Client, filters
from asyncio.exceptions import TimeoutError
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid
)
from config import API_ID, API_HASH
from plugins.database import db_instances
from plugins.link_changer import link_changer
from bot import Bot
import os

SESSION_STRING_SIZE = 351

# Helper to fetch the correct DB for the current bot/client
def get_db_for_client(client):
    db_instance = getattr(client, "db", None)
    if db_instance is not None:
        return db_instance
    bot_instance = Bot.instances.get(getattr(client, "bot_token", None))
    if bot_instance:
        return bot_instance.db
    version = getattr(client, "version", "v1")
    return db_instances.get(version)

@Client.on_message(filters.private & ~filters.forwarded & filters.command(["logout"]))
async def logout(client, message):
    user_id = message.from_user.id
    # Get the bot instance that received this command
    bot_instance = Bot.instances.get(client.bot_token)
    if not bot_instance:
        await message.reply("Bot configuration error.")
        return
    
    # Use the database instance associated with this bot
    db = bot_instance.db
    sessions = await db.get_all_sessions(user_id)
    
    if not sessions:
        await message.reply("**You are not logged in.**")
        return
    
    if len(sessions) == 1:
        # Only one session, logout that one
        phone = list(sessions.keys())[0]
        await db.remove_session(user_id, phone)
        await message.reply(f"**Logged out from {phone} successfully** ♦")
    else:
        # Multiple sessions, ask which one to logout
        buttons = []
        for phone in sessions.keys():
            buttons.append([InlineKeyboardButton(phone, callback_data=f"logout_{phone}")])
        buttons.append([InlineKeyboardButton("Logout All", callback_data="logout_all")])
        
        await message.reply(
            "**You have multiple accounts logged in. Which one do you want to logout?**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

@Client.on_callback_query(filters.regex("^logout_"))
async def logout_callback(client, callback_query):
    """Handle logout button clicks"""
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    db = get_db_for_client(client)
    
    if data == "logout_all":
        # Logout all accounts
        sessions = await db.get_all_sessions(user_id)
        for phone in sessions.keys():
            # Delete session file if it exists
            session_file = f"sessions/{phone}"
            if os.path.exists(session_file):
                os.remove(session_file)
        
        await db.remove_all_sessions(user_id)
        await db.set_active_id(user_id, None)
        await callback_query.answer("All accounts logged out", show_alert=True)
        await callback_query.message.edit_text("**All accounts logged out successfully** ♦")
    else:
        # Logout specific account
        phone = data.replace("logout_", "")
        
        # Delete session file if it exists
        session_file = f"sessions/{phone}"
        if os.path.exists(session_file):
            os.remove(session_file)
        
        await db.remove_session(user_id, phone)
        
        # If this was the active ID, clear it
        active_id = await db.get_active_id(user_id)
        if active_id == phone:
            await db.set_active_id(user_id, None)
        
        await callback_query.answer(f"Logged out from {phone}", show_alert=True)
        await callback_query.message.edit_text(f"**Logged out from {phone} successfully** ♦")

@Client.on_message(filters.private & ~filters.forwarded & filters.command(["login"]))
async def main(bot: Client, message: Message):
    user_id = int(message.from_user.id)
    phone_number_msg = await bot.ask(chat_id=user_id, text="<b>Please send your phone number which includes country code</b>\n<b>Example:</b> <code>+13124562345, +9171828181889</code>")
    if phone_number_msg.text=='/cancel':
        return await phone_number_msg.reply('<b>process cancelled !</b>')
    phone_number = phone_number_msg.text
    
    db = get_db_for_client(bot)
    existing_session = await db.get_session(user_id, phone_number)
    if existing_session:
        await phone_number_msg.reply(f"**This phone number ({phone_number}) is already logged in. Use /logout to logout first.**")
        return
    
    client = Client(":memory:", API_ID, API_HASH)
    await client.connect()
    await phone_number_msg.reply("Sending OTP...")
    try:
        code = await client.send_code(phone_number)
        phone_code_msg = await bot.ask(user_id, "Please check for an OTP in official telegram account. If you got it, send OTP here after reading the below format. \n\nIf OTP is `12345`, **please send it as** `1 2 3 4 5`.\n\n**Enter /cancel to cancel The Procces**", filters=filters.text, timeout=600)
    except PhoneNumberInvalid:
        await phone_number_msg.reply('`PHONE_NUMBER` **is invalid.**')
        return
    if phone_code_msg.text=='/cancel':
        return await phone_code_msg.reply('<b>process cancelled !</b>')
    try:
        phone_code = phone_code_msg.text.replace(" ", "")
        await client.sign_in(phone_number, code.phone_code_hash, phone_code)
    except PhoneCodeInvalid:
        await phone_code_msg.reply('**OTP is invalid.**')
        return
    except PhoneCodeExpired:
        await phone_code_msg.reply('**OTP is expired.**')
        return
    except SessionPasswordNeeded:
        two_step_msg = await bot.ask(user_id, '**Your account has enabled two-step verification. Please provide the password.\n\nEnter /cancel to cancel The Procces**', filters=filters.text, timeout=300)
        if two_step_msg.text=='/cancel':
            return await two_step_msg.reply('<b>process cancelled !</b>')
        try:
            password = two_step_msg.text
            await client.check_password(password=password)
        except PasswordHashInvalid:
            await two_step_msg.reply('**Invalid Password Provided**')
            return
    string_session = await client.export_session_string()
    await client.disconnect()
    if len(string_session) < SESSION_STRING_SIZE:
        return await message.reply('<b>invalid session sring</b>')
    try:
        uclient = Client(":memory:", session_string=string_session, api_id=API_ID, api_hash=API_HASH)
        await uclient.connect()
        await db.add_session(message.from_user.id, phone_number, string_session)
        await uclient.disconnect()
    except Exception as e:
        return await message.reply_text(f"<b>ERROR IN LOGIN:</b> `{e}`")
    await bot.send_message(message.from_user.id, f"<b>Account {phone_number} logged in successfully!\n\nYou can now add channels with /pubchannel</b>")

@Client.on_message(filters.private & ~filters.forwarded & filters.command(["setid"]))
async def setid(client, message):
    """Set which account to use for channel management"""
    user_id = message.from_user.id
    db = get_db_for_client(client)
    sessions = await db.get_all_sessions(user_id)
    
    if not sessions:
        await message.reply("**You are not logged in. Use /login first.**")
        return
    
    if len(sessions) == 1:
        # Only one session, set it as active
        phone = list(sessions.keys())[0]
        await db.set_active_id(user_id, phone)
        await message.reply(f"✅ **Active account set to:** `{phone}`")
    else:
        # Multiple sessions, show buttons
        buttons = []
        for phone in sessions.keys():
            buttons.append([InlineKeyboardButton(phone, callback_data=f"setid_{phone}")])
        
        await message.reply(
            "**Select which account to use for channel management:**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

@Client.on_callback_query(filters.regex("^setid_"))
async def setid_callback(client, callback_query):
    """Handle setid button clicks"""
    user_id = callback_query.from_user.id
    phone = callback_query.data.replace("setid_", "")
    
    db = get_db_for_client(client)
    await db.set_active_id(user_id, phone)
    await callback_query.answer(f"Active account set to {phone}", show_alert=True)
    await callback_query.message.edit_text(f"✅ **Active account set to:** `{phone}`")

@Client.on_message(filters.private & ~filters.forwarded & filters.command(["pubchannel"]))
async def add_pubchannel(client, message):
    """Add a channel for automatic link rotation"""
    user_id = message.from_user.id
    
    db = get_db_for_client(client)
    # Get all sessions for this user
    sessions = await db.get_all_sessions(user_id)
    if not sessions:
        await message.reply("**You are not logged in. Use /login first.**")
        return
    
    try:
        parts = message.command[1:]
        if len(parts) < 3:
            await message.reply("**Usage:** `/pubchannel <channel_id> <base_username> <interval> [phone_number]`\n\n**Example:** `/pubchannel -1002265253583 You_are_Ms_Servant_in_hindi_i 400`\n\nOptionally specify phone number to use a specific account.")
            return
        
        channel_id = int(parts[0])
        base_username = parts[1]
        interval = int(parts[2])
        
        # Check if a specific phone number was provided
        phone_number = parts[3] if len(parts) > 3 else None
        
        # If no specific phone number, use the first available session
        if not phone_number:
            phone_number = list(sessions.keys())[0]
        elif phone_number not in sessions:
            await message.reply(f"**Phone number {phone_number} is not logged in.**")
            return
        
        # Check if channel already exists
        existing = await db.get_channel(channel_id)
        if existing:
            await message.reply(f"**Channel {channel_id} is already being managed.**")
            return
        
        # Add the channel to the database first with ownership information
        await db.add_channel(user_id, channel_id, base_username, interval)
        await db.update_channel_owner(channel_id, phone_number)
        
        # Start the channel rotation
        success, result = await link_changer.start_channel_rotation(
            user_id, 
            channel_id, 
            base_username, 
            interval,
            phone_number,
            getattr(client, "version", "v1")
        )
        
        if success:
            await message.reply(f"✅ **Channel {channel_id} added successfully!**\n\n**Base Username:** `{base_username}`\n**Interval:** `{interval}s`\n**Using account:** `{phone_number}`")
        else:
            await message.reply(f"❌ **Failed to add channel:** `{result}`")
    except ValueError:
        await message.reply("**Invalid parameters. Channel ID and interval must be numbers.**")
    except Exception as e:
        await message.reply(f"❌ **Error:** `{e}`")

@Client.on_message(filters.private & ~filters.forwarded & filters.command(["list"]))
async def list_channels(client, message):
    """List all channels being managed"""
    user_id = message.from_user.id
    
    db = get_db_for_client(client)
    channels = await db.get_user_channels(user_id)
    
    if not channels:
        await message.reply("**You have no active channels.**")
        return
    
    text = "**Your Active Channels:**\n\n"
    for i, channel in enumerate(channels, 1):
        text += f"{i}. **Channel ID:** `{channel['channel_id']}`\n"
        text += f"   **Base Username:** `{channel['base_username']}`\n"
        text += f"   **Interval:** `{channel['interval']}s`\n"
        text += f"   **Status:** {'🟢 Active' if channel['is_active'] else '🔴 Stopped'}\n\n"
    
    await message.reply(text)

@Client.on_message(filters.private & ~filters.forwarded & filters.command(["stop"]))
async def stop_channel(client, message):
    """Stop link rotation for a channel"""
    user_id = message.from_user.id
    
    db = get_db_for_client(client)
    try:
        if len(message.command) < 2:
            await message.reply("**Usage:** `/stop <channel_id>`")
            return
        
        channel_id = int(message.command[1])
        
        success, result = await link_changer.stop_channel_rotation(
            user_id, channel_id, phone_number=None, version=getattr(client, "version", "v1")
        )
        
        if success:
            await db.stop_channel(channel_id)
            await message.reply(f"✅ **Channel {channel_id} rotation stopped.**")
        else:
            await message.reply(f"❌ **Error:** `{result}`")
    except ValueError:
        await message.reply("**Channel ID must be a number.**")
    except Exception as e:
        await message.reply(f"❌ **Error:** `{e}`")

@Client.on_message(filters.private & ~filters.forwarded & filters.command(["resume"]))
async def resume_channel(client, message):
    """Resume link rotation for a channel"""
    user_id = message.from_user.id
    
    db = get_db_for_client(client)
    # Get all sessions for this user
    sessions = await db.get_all_sessions(user_id)
    if not sessions:
        await message.reply("**You are not logged in. Use /login first.**")
        return
    
    try:
        parts = message.command[1:]
        if len(parts) < 1:
            await message.reply("**Usage:** `/resume <channel_id> [phone_number]`\n\nOptionally specify phone number to use a specific account.")
            return
        
        channel_id = int(parts[0])
        
        channel = await db.get_channel(channel_id)
        if not channel:
            await message.reply(f"**Channel {channel_id} not found.**")
            return
        
        # Check if a specific phone number was provided
        phone_number = parts[1] if len(parts) > 1 else None
        
        # If no phone number specified, check if channel has an owner
        if not phone_number:
            channel_owner = await db.get_channel_owner(channel_id)
            if channel_owner and channel_owner in sessions:
                phone_number = channel_owner
                await message.reply(f"**Using channel's original owner: {phone_number}**")
            else:
                # Use first available session if no owner or owner not logged in
                phone_number = list(sessions.keys())[0]
        elif phone_number not in sessions:
            await message.reply(f"**Phone number {phone_number} is not logged in.**")
            return
        
        # Update channel owner if different from current
        current_owner = await db.get_channel_owner(channel_id)
        if current_owner != phone_number:
            await db.update_channel_owner(channel_id, phone_number)
        
        # Start rotation again with version awareness
        success, result = await link_changer.start_channel_rotation(
            user_id,
            channel_id,
            channel['base_username'],
            channel['interval'],
            phone_number,
            getattr(client, "version", "v1")
        )
        
        if success:
            await db.resume_channel(channel_id)
            await message.reply(f"✅ **Channel {channel_id} rotation resumed using account {phone_number}.**")
        else:
            await message.reply(f"❌ **Error:** `{result}`")
    except ValueError:
        await message.reply("**Channel ID must be a number.**")
    except Exception as e:
        await message.reply(f"❌ **Error:** `{e}`")

@Client.on_message(filters.private & ~filters.forwarded & filters.command(["status"]))
async def status(client, message):
    """Show bot status and active accounts"""
    user_id = message.from_user.id
    
    db = get_db_for_client(client)
    sessions = await db.get_all_sessions(user_id)
    active_id = await db.get_active_id(user_id)
    channels = await db.get_user_channels(user_id)
    
    text = "**Bot Status:**\n\n"
    text += f"**Logged In Accounts:** `{len(sessions)}`\n"
    
    if sessions:
        text += "\n**Accounts:**\n"
        for phone in sessions.keys():
            indicator = "🟢" if phone == active_id else "⚪"
            text += f"{indicator} `{phone}`\n"
    
    text += f"\n**Active Channels:** `{len(channels)}`\n"
    
    await message.reply(text)

@Client.on_message(filters.private & ~filters.forwarded & filters.command(["showlogin"]))
async def showlogin(client, message):
    """Show all logged-in accounts"""
    user_id = message.from_user.id
    
    db = get_db_for_client(client)
    sessions = await db.get_all_sessions(user_id)
    active_id = await db.get_active_id(user_id)
    
    if not sessions:
        await message.reply("**You are not logged in.**")
        return
    
    text = "**Your Logged-In Accounts:**\n\n"
    for phone in sessions.keys():
        indicator = "✅" if phone == active_id else "⭕"
        text += f"{indicator} `{phone}`\n"
    
    await message.reply(text)

@Client.on_message(filters.private & ~filters.forwarded & filters.command(["help"]))
async def help_command(client, message):
    """Show help message"""
    help_text = """
**VJ Link Changer Bot - Help**

**Commands:**

/login - Login to your Telegram account
/logout - Logout from your account(s)
/setid - Select which account to use for channel management
/pubchannel - Add a channel for automatic link rotation
/list - List all your active channels
/stop - Stop link rotation for a channel
/resume - Resume link rotation for a channel
/status - Show bot status and active accounts
/showlogin - Show all logged-in accounts
/help - Show this help message

**Usage Example:**

1. /login - Login with your phone number
2. /setid - Select which account to use
3. /pubchannel -1002265253583 base_username 400 - Add channel with 400s interval
4. /list - View your channels
5. /stop -1002265253583 - Stop rotation for a channel
6. /resume -1002265253583 - Resume rotation for a channel

**Bot by:** @VJ_Botz
"""
    await message.reply(help_text)

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
