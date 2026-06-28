"""
Auto DM Forward Bot - Telegram Bot
Advanced Features: OTP Spacing, Back Buttons, All DMs, Pending Requests, Joined Members
"""
import logging
import os
import asyncio
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

from config import BOT_TOKEN, ADMIN_IDS, get_random_emoji, get_emoji_markup
from database import db
from telethon_manager import manager
from keyboards import *

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ CONVERSATION STATES ============
(STATE_PHONE, STATE_OTP, STATE_2FA, STATE_MESSAGE, STATE_PAYMENT_UTR,
 STATE_PAYMENT_SCREENSHOT, STATE_REDEEM, STATE_REFER, STATE_DM_CONFIRM) = range(9)

# Temp storage for conversation data
user_temp = {}

# ============ HELPER FUNCTIONS ============
def e():
    """Quick emoji getter for HTML text (uses tg-emoji)"""
    return get_emoji_markup()

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_premium_text(user_id):
    days = db.get_premium_status(user_id)
    if days:
        return f"{e()} Status: <b>{days} Days Premium</b>"
    return f"{e()} Status: <b>Free Plan</b>"

def format_otp(code):
    """Format OTP with spaces between digits: 123456 -> 1 2 3 4 5 6"""
    return ' '.join(code)

def get_user_info_text(user_id, username):
    user = db.get_user(user_id)
    dm_remaining = db.get_dm_limit(user_id)
    premium_text = get_premium_text(user_id)

    text = f"""{e()} <b>Auto DMs Bot</b>\n----------------------\n{e()} <b>Your ID:</b> <code>{user_id}</code>\n{e()} <b>Username:</b> @{username or 'None'}\n{e()} <b>DM Remaining:</b> {'Unlimited' if dm_remaining == float('inf') else dm_remaining}\n{premium_text}\n----------------------\n\n{e()} The fastest mass DM tool on Telegram\n\n{e()} Send to all your DMs at once\n{e()} To contacts & channel pending requests.\n{e()} Blazing-fast delivery\n{e()} Free Plan: 100 sends\n{e()} Premium Plan: Unlimited sends\n\n----------------------\nTap <b>Add Account</b> to get started! {e()}"""
    return text

# ============ /START COMMAND ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    # Check force join
    try:
        member = await context.bot.get_chat_member(FORCE_JOIN_CHANNEL, user_id)
        if member.status in ['left', 'kicked']:
            await update.message.reply_text(
                f"{e()} <b>Please join our channel first!</b>\n"
                f"{e()} <a href='https://t.me/{FORCE_JOIN_CHANNEL.lstrip('@')}'>Click here to join</a>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"{rocket_emoji()} Join Channel", url=f"https://t.me/{FORCE_JOIN_CHANNEL.lstrip('@')}")
                ]])
            )
            return
    except Exception:
        pass

    # Add user to DB
    db.add_user(user_id, user.username, user.first_name)

    # Check refer
    args = context.args
    if args and args[0].startswith("ref_"):
        try:
            ref_id = int(args[0].split("_")[1])
            if ref_id != user_id and not db.get_user(user_id).get("referred_by"):
                db.update_user(user_id, referred_by=ref_id)
                db.update_user(ref_id, refer_count=db.get_user(ref_id).get("refer_count", 0) + 1)
        except:
            pass

    welcome_text = f"""{e()} <b>Welcome to Auto DM Forward Bot</b> {e()}\n{e()} The most advanced Telegram automation tool is now in your hands.\nConnect your account and start running campaigns seamlessly.\n\n<b>Master Features</b>\n- {e()} Auto-Profile Update\n- {e()} Smart Auto-Forwarder\n- {e()} Global Login (OTP & 2FA)"""

    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=welcome_keyboard()
    )

# ============ CALLBACK HANDLER ============
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "open_dashboard":
        await show_dashboard(query, context)
    elif data == "how_to_use":
        await show_how_to_use(query, context)
    elif data == "add_account":
        await start_add_account(query, context)
    elif data == "set_message":
        await start_set_message(query, context)
    elif data == "preview_message":
        await preview_message(query, context)
    elif data == "dm_contacts":
        await start_dm_contacts(query, context)
    elif data == "dm_pending":
        await start_dm_pending(query, context)
    elif data == "dm_joined":
        await start_dm_joined(query, context)
    elif data == "buy_premium":
        await show_premium_plans(query, context)
    elif data == "redeem_code":
        await start_redeem(query, context)
    elif data == "refer_earn":
        await show_refer(query, context)
    elif data.startswith("plan_"):
        await process_plan_selection(query, context, data)
    elif data.startswith("approve_pay_"):
        await approve_payment(query, context, data)
    elif data.startswith("disapprove_pay_"):
        await disapprove_payment(query, context, data)
    elif data.startswith("select_channel_"):
        await process_channel_selection(query, context, data)
    elif data.startswith("action_pending_"):
        await process_channel_action(query, context, data, "pending")
    elif data.startswith("action_joined_"):
        await process_channel_action(query, context, data, "joined")
    elif data == "confirm_dm_contacts":
        await execute_dm_contacts(query, context)
    elif data == "confirm_dm_pending":
        await execute_dm_pending(query, context)
    elif data == "confirm_dm_joined":
        await execute_dm_joined(query, context)
    elif data == "refresh_channels":
        await refresh_channels(query, context)
    elif data == "filter_all":
        await filter_channels(query, context, "all")
    elif data == "sort_recent":
        await sort_channels(query, context, "recent")

async def show_dashboard(query, context):
    user_id = query.from_user.id
    username = query.from_user.username
    text = get_user_info_text(user_id, username)

    try:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=dashboard_keyboard())
    except:
        await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=dashboard_keyboard())

async def show_how_to_use(query, context):
    how_text = f"""{e()} <b>How to Use</b>\n{e()} <b>Step 1:</b> Click "Add Account" and login with your Telegram account.\n\n{e()} <b>Step 2:</b> Set your DM message using "Set Message".\n\n{e()} <b>Step 3:</b> Choose "DM to Contacts" or "DM to Pending Requests" or "DM to Joined Members".\n\n{e()} <b>Step 4:</b> Sit back and watch the bot send mass DMs!\n\n{e()} <b>Need more sends?</b> Buy Premium or use Refer & Earn!"""

    await query.edit_message_text(how_text, parse_mode=ParseMode.HTML, reply_markup=back_keyboard())


# ============ ADD ACCOUNT (LOGIN) ============
async def start_add_account(query, context):
    user_id = query.from_user.id
    text = f"""{e()} <b>Add Your Telegram Account</b>
----------------------

<b>Step 1 of 3 - Phone Number</b>

Enter your phone number with country code:
Example: <code>+91XXXXXXXXXX</code>

{e()} Your account is only used to send DMs - we never access personal data."""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return STATE_PHONE

async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    phone = update.message.text.strip()

    if not phone.startswith("+") or not phone[1:].isdigit():
        await update.message.reply_text(
            f"{e()} <b>Invalid phone number!</b>\nPlease enter in format: <code>+91XXXXXXXXXX</code>",
            parse_mode=ParseMode.HTML
        )
        return STATE_PHONE

    # Send OTP via Telethon
    result = await manager.send_code(phone)

    if result["success"]:
        user_temp[user_id] = {
            "phone": phone,
            "phone_code_hash": result["phone_code_hash"],
            "session_string": result["session_string"]
        }
        await update.message.reply_text(
            f"{e()} <b>OTP Sent!</b>\n"
            f"Please check your Telegram app and enter the code you received.\n"
            f"{e()} <b>Tip:</b> Type OTP with spaces like: <code>1 2 3 4 5 6</code>",
            parse_mode=ParseMode.HTML
        )
        return STATE_OTP
    else:
        await update.message.reply_text(
            f"{e()} <b>Error:</b> {result.get('error', 'Unknown error')}\nTry again later.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

async def receive_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip().replace(" ", "")
    temp = user_temp.get(user_id, {})

    if not temp:
        await update.message.reply_text(f"{e()} Session expired. Please start again.", parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    result = await manager.verify_code(
        temp["phone"], code, temp["phone_code_hash"], temp["session_string"]
    )

    if result.get("success"):
        db.update_user(user_id, 
            phone_number=temp["phone"],
            session_string=result["session_string"],
            is_logged_in=1
        )
        await update.message.reply_text(
            f"{e()} <b>Login Successful!</b> {e()}\n"
            f"Your account has been connected.",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )
        del user_temp[user_id]
        return ConversationHandler.END

    elif result.get("need_2fa"):
        user_temp[user_id]["session_string"] = result["session_string"]
        await update.message.reply_text(
            f"{e()} <b>2FA Required!</b>\n"
            f"Your account has two-factor authentication enabled.\n"
            f"Please enter your 2FA password:",
            parse_mode=ParseMode.HTML
        )
        return STATE_2FA
    else:
        await update.message.reply_text(
            f"{e()} <b>Invalid OTP Code!</b>\nPlease try again.",
            parse_mode=ParseMode.HTML
        )
        return STATE_OTP

async def receive_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    password = update.message.text.strip()
    temp = user_temp.get(user_id, {})

    if not temp:
        await update.message.reply_text(f"{e()} Session expired.", parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    result = await manager.verify_2fa(temp["phone"], password, temp["session_string"])

    if result["success"]:
        db.update_user(user_id,
            phone_number=temp["phone"],
            session_string=result["session_string"],
            is_logged_in=1
        )
        await update.message.reply_text(
            f"{e()} <b>Login Successful!</b> {e()}\n"
            f"Your account has been connected with 2FA.",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )
        del user_temp[user_id]
    else:
        await update.message.reply_text(
            f"{e()} <b>Incorrect 2FA Password!</b>\nPlease try again.",
            parse_mode=ParseMode.HTML
        )
        return STATE_2FA

    return ConversationHandler.END

# ============ SET MESSAGE ============
async def start_set_message(query, context):
    user_id = query.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get("is_logged_in"):
        await query.edit_message_text(
            f"{e()} <b>Please login first!</b>\nUse \"Add Account\" to login.",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )
        return

    await query.edit_message_text(
        f"{e()} <b>Set Your DM Message</b>\n"
        f"Send your message text or media (image/video).\n"
        f"You can use emojis and formatting.",
        parse_mode=ParseMode.HTML
    )
    return STATE_MESSAGE

async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        caption = update.message.caption or ""
        db.update_user(user_id, message_media=file_id, message_text=caption)
        await update.message.reply_text(
            f"{e()} <b>Message Saved!</b>\n"
            f"Image + caption has been set.",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )
    else:
        text = update.message.text
        db.update_user(user_id, message_text=text, message_media=None)
        await update.message.reply_text(
            f"{e()} <b>Message Saved!</b>\n"
            f"Your text message has been set.",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )

    return ConversationHandler.END

async def preview_message(query, context):
    user_id = query.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get("message_text"):
        await query.edit_message_text(
            f"{e()} <b>No message set!</b>\nPlease set a message first.",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )
        return

    if user.get("message_media"):
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=user["message_media"],
            caption=f"{e()} <b>Preview:</b>\n{user['message_text']}",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )
    else:
        await query.edit_message_text(
            f"{e()} <b>Preview:</b>\n{user['message_text']}",
            parse_mode=ParseMode.HTML,
            reply_markup=back_keyboard()
        )


# ============ DM TO ALL PERSONAL DMs (Updated from just contacts) ============
async def start_dm_contacts(query, context):
    user_id = query.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get("is_logged_in"):
        await query.edit_message_text(
            f"{e()} <b>Please login first!</b>",
            parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
        )
        return

    if not user.get("message_text"):
        await query.edit_message_text(
            f"{e()} <b>Set a message first!</b>",
            parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
        )
        return

    await query.edit_message_text(
        f"{e()} <b>Fetching all your personal DMs...</b>\nPlease wait.",
        parse_mode=ParseMode.HTML
    )

    # Use new method to get ALL personal DMs
    all_dms = await manager.get_all_personal_dms(user["session_string"])

    if not all_dms:
        await query.edit_message_text(
            f"{e()} <b>No DMs found!</b>\n"
            f"Make sure you have active conversations.",
            parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
        )
        return

    user_temp[user_id] = {"contacts": all_dms, "type": "contacts"}

    dm_limit = db.get_dm_limit(user_id)
    total = len(all_dms)

    # Show breakdown by type
    private_count = sum(1 for d in all_dms if d['type'] == 'private')
    group_count = sum(1 for d in all_dms if d['type'] in ['group', 'supergroup'])
    channel_count = sum(1 for d in all_dms if d['type'] == 'channel')

    await query.edit_message_text(
        f"{e()} <b>All DMs Found: {total}</b>\n"
        f"{user_emoji()} Private Chats: {private_count}\n"
        f"{group_emoji()} Groups: {group_count}\n"
        f"{channel_emoji()} Channels: {channel_count}\n"
        f"{e()} DM Limit: {'Unlimited' if dm_limit == float('inf') else dm_limit}\n"
        f"Do you want to start sending?",
        parse_mode=ParseMode.HTML,
        reply_markup=confirm_keyboard("confirm_dm_contacts", "open_dashboard")
    )

async def execute_dm_contacts(query, context):
    user_id = query.from_user.id
    temp = user_temp.get(user_id, {})

    if not temp or temp.get("type") != "contacts":
        await query.edit_message_text(f"{e()} Session expired.", parse_mode=ParseMode.HTML)
        return

    user = db.get_user(user_id)
    contacts = temp["contacts"]
    dm_limit = db.get_dm_limit(user_id)

    if dm_limit != float('inf'):
        contacts = contacts[:dm_limit]

    await query.edit_message_text(
        f"{e()} <b>Starting DM Campaign...</b>\n"
        f"Targets: {len(contacts)}\n"
        f"Please wait, this may take a while.",
        parse_mode=ParseMode.HTML
    )

    # Download media if exists
    media_path = None
    if user.get("message_media"):
        try:
            file = await context.bot.get_file(user["message_media"])
            media_path = f"/tmp/dm_media_{user_id}.jpg"
            await file.download_to_drive(media_path)
        except:
            pass

    results = await manager.send_bulk_messages(
        user["session_string"], contacts, user["message_text"], media_path, delay=3
    )

    # Update DM used
    if dm_limit != float('inf'):
        db.use_dm(user_id, results["success"])

    # Log
    for contact in contacts[:results["success"]]:
        db.log_sent(user_id, "contact", contact["id"], True)

    await query.edit_message_text(
        f"{e()} <b>Campaign Completed!</b>\n"
        f"Success: {results['success']}\n"
        f"Failed: {results['failed']}\n"
        f"{e()} Thank you for using Auto DM Bot!",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )

    if media_path and os.path.exists(media_path):
        os.remove(media_path)
    del user_temp[user_id]


# ============ DM TO PENDING REQUESTS (Updated) ============
async def start_dm_pending(query, context):
    user_id = query.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get("is_logged_in"):
        await query.edit_message_text(
            f"{e()} <b>Please login first!</b>",
            parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
        )
        return

    if not user.get("message_text"):
        await query.edit_message_text(
            f"{e()} <b>Set a message first!</b>",
            parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
        )
        return

    await query.edit_message_text(
        f"{e()} <b>Fetching your admin channels...</b>\n"
        f"{e()} Using advanced channel detection...",
        parse_mode=ParseMode.HTML
    )

    # Use advanced channel fetching
    channels = await manager.get_admin_channels(user["session_string"], refresh=True)

    if not channels:
        await query.edit_message_text(
            f"{e()} <b>No admin channels found!</b>\n"
            f"You must be an admin in at least one channel.",
            parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
        )
        return

    user_temp[user_id] = {"channels": channels, "type": "pending"}

    await query.edit_message_text(
        f"{e()} <b>Select Channel:</b>\n"
        f"Choose a channel to manage pending requests.\n"
        f"{e()} <b>Found {len(channels)} admin channels</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=channel_select_keyboard(channels, "select_channel")
    )

async def process_channel_selection(query, context, data):
    user_id = query.from_user.id
    temp = user_temp.get(user_id, {})

    if not temp or temp.get("type") != "pending":
        await query.edit_message_text(f"{e()} Session expired.", parse_mode=ParseMode.HTML)
        return

    selection = data.replace("select_channel_", "")
    user = db.get_user(user_id)

    if selection == "all":
        # Show all channels with action options
        channels = temp["channels"]
        await query.edit_message_text(
            f"{e()} <b>Select Action for All Channels:</b>\n"
            f"{e()} You selected ALL {len(channels)} channels\n"
            f"Choose what to do:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{pending_emoji()} DM Pending Requests", callback_data="action_pending_all")],
                [InlineKeyboardButton(f"{joined_emoji()} DM Joined Members", callback_data="action_joined_all")],
                [InlineKeyboardButton(f"{back_emoji()} Back", callback_data="dm_pending")],
            ])
        )
        return

    ch_id = int(selection)
    channel = next((c for c in temp["channels"] if c["id"] == ch_id), None)

    if not channel:
        await query.edit_message_text(f"{e()} Channel not found.", parse_mode=ParseMode.HTML)
        return

    await query.edit_message_text(
        f"{e()} <b>Channel Selected:</b> {channel['title']}\n"
        f"{channel_emoji()} Members: {channel.get('participants_count', 'N/A')}\n"
        f"{admin_emoji()} Admin Status: {'Owner' if channel.get('is_owner') else 'Admin'}\n"
        f"Choose action:",
        parse_mode=ParseMode.HTML,
        reply_markup=channel_action_keyboard(ch_id)
    )

async def process_channel_action(query, context, data, action_type):
    user_id = query.from_user.id
    temp = user_temp.get(user_id, {})

    if not temp:
        await query.edit_message_text(f"{e()} Session expired.", parse_mode=ParseMode.HTML)
        return

    user = db.get_user(user_id)

    if "_all" in data:
        # Handle all channels
        channels = temp.get("channels", [])
        all_targets = []

        for ch in channels:
            if action_type == "pending":
                targets = await manager.get_pending_requests(user["session_string"], ch["id"])
            else:
                targets = await manager.get_joined_members(user["session_string"], ch["id"])
            all_targets.extend(targets)
            await asyncio.sleep(0.5)

        if not all_targets:
            await query.edit_message_text(
                f"{e()} <b>No {'pending requests' if action_type == 'pending' else 'joined members'} found!</b>",
                parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
            )
            return

        user_temp[user_id]["pending" if action_type == "pending" else "joined"] = all_targets
        user_temp[user_id]["action_type"] = action_type

        dm_limit = db.get_dm_limit(user_id)
        await query.edit_message_text(
            f"{e()} <b>{'Pending Requests' if action_type == 'pending' else 'Joined Members'}: {len(all_targets)}</b>\n"
            f"{e()} DM Limit: {'Unlimited' if dm_limit == float('inf') else dm_limit}\n"
            f"Do you want to start sending?",
            parse_mode=ParseMode.HTML,
            reply_markup=confirm_keyboard(
                f"confirm_dm_{'pending' if action_type == 'pending' else 'joined'}",
                "open_dashboard"
            )
        )
    else:
        # Handle single channel
        ch_id = int(data.split("_")[-1])

        await query.edit_message_text(
            f"{e()} <b>Fetching {'pending requests' if action_type == 'pending' else 'joined members'}...</b>\nPlease wait.",
            parse_mode=ParseMode.HTML
        )

        if action_type == "pending":
            targets = await manager.get_pending_requests(user["session_string"], ch_id)
        else:
            targets = await manager.get_joined_members(user["session_string"], ch_id)

        if not targets:
            await query.edit_message_text(
                f"{e()} <b>No {'pending requests' if action_type == 'pending' else 'joined members'} found!</b>",
                parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
            )
            return

        user_temp[user_id]["pending" if action_type == "pending" else "joined"] = targets
        user_temp[user_id]["action_type"] = action_type
        dm_limit = db.get_dm_limit(user_id)

        await query.edit_message_text(
            f"{e()} <b>{'Pending Requests' if action_type == 'pending' else 'Joined Members'}: {len(targets)}</b>\n"
            f"{e()} DM Limit: {'Unlimited' if dm_limit == float('inf') else dm_limit}\n"
            f"Do you want to start sending?",
            parse_mode=ParseMode.HTML,
            reply_markup=confirm_keyboard(
                f"confirm_dm_{'pending' if action_type == 'pending' else 'joined'}",
                "open_dashboard"
            )
        )

async def execute_dm_pending(query, context):
    user_id = query.from_user.id
    temp = user_temp.get(user_id, {})

    if not temp or temp.get("action_type") != "pending":
        await query.edit_message_text(f"{e()} Session expired.", parse_mode=ParseMode.HTML)
        return

    user = db.get_user(user_id)
    pending = temp.get("pending", [])
    dm_limit = db.get_dm_limit(user_id)

    if dm_limit != float('inf'):
        pending = pending[:dm_limit]

    await query.edit_message_text(
        f"{e()} <b>Starting pending DM campaign...</b>\n"
        f"Targets: {len(pending)}\n"
        f"Please wait...",
        parse_mode=ParseMode.HTML
    )

    media_path = None
    if user.get("message_media"):
        try:
            file = await context.bot.get_file(user["message_media"])
            media_path = f"/tmp/dm_media_{user_id}.jpg"
            await file.download_to_drive(media_path)
        except:
            pass

    results = await manager.send_bulk_messages(
        user["session_string"], pending, user["message_text"], media_path, delay=2
    )

    if dm_limit != float('inf'):
        db.use_dm(user_id, results["success"])

    for p in pending[:results["success"]]:
        db.log_sent(user_id, "pending", p["id"], True)

    await query.edit_message_text(
        f"{e()} <b>Pending DM Campaign Completed!</b>\n"
        f"Success: {results['success']}\n"
        f"Failed: {results['failed']}\n"
        f"{e()} All pending requests have been DMed!",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )

    if media_path and os.path.exists(media_path):
        os.remove(media_path)
    if user_id in user_temp:
        del user_temp[user_id]


# ============ DM TO JOINED MEMBERS (NEW) ============
async def start_dm_joined(query, context):
    user_id = query.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get("is_logged_in"):
        await query.edit_message_text(
            f"{e()} <b>Please login first!</b>",
            parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
        )
        return

    if not user.get("message_text"):
        await query.edit_message_text(
            f"{e()} <b>Set a message first!</b>",
            parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
        )
        return

    await query.edit_message_text(
        f"{e()} <b>Fetching your channels...</b>\n"
        f"{e()} Loading joined members data...",
        parse_mode=ParseMode.HTML
    )

    # Get all channels (not just admin ones)
    channels = await manager.get_all_channels(user["session_string"])

    if not channels:
        await query.edit_message_text(
            f"{e()} <b>No channels found!</b>\n"
            f"You must be in at least one channel.",
            parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
        )
        return

    user_temp[user_id] = {"channels": channels, "type": "joined"}

    await query.edit_message_text(
        f"{e()} <b>Select Channel for Joined Members:</b>\n"
        f"{e()} <b>Found {len(channels)} channels</b>\n"
        f"Choose a channel to DM joined members:",
        parse_mode=ParseMode.HTML,
        reply_markup=channel_select_keyboard(channels, "select_channel")
    )

async def execute_dm_joined(query, context):
    user_id = query.from_user.id
    temp = user_temp.get(user_id, {})

    if not temp or temp.get("action_type") != "joined":
        await query.edit_message_text(f"{e()} Session expired.", parse_mode=ParseMode.HTML)
        return

    user = db.get_user(user_id)
    joined = temp.get("joined", [])
    dm_limit = db.get_dm_limit(user_id)

    if dm_limit != float('inf'):
        joined = joined[:dm_limit]

    await query.edit_message_text(
        f"{e()} <b>Starting joined members DM campaign...</b>\n"
        f"Targets: {len(joined)}\n"
        f"Please wait...",
        parse_mode=ParseMode.HTML
    )

    media_path = None
    if user.get("message_media"):
        try:
            file = await context.bot.get_file(user["message_media"])
            media_path = f"/tmp/dm_media_{user_id}.jpg"
            await file.download_to_drive(media_path)
        except:
            pass

    results = await manager.send_bulk_messages(
        user["session_string"], joined, user["message_text"], media_path, delay=2
    )

    if dm_limit != float('inf'):
        db.use_dm(user_id, results["success"])

    for j in joined[:results["success"]]:
        db.log_sent(user_id, "joined", j["id"], True)

    await query.edit_message_text(
        f"{e()} <b>Joined Members DM Campaign Completed!</b>\n"
        f"Success: {results['success']}\n"
        f"Failed: {results['failed']}\n"
        f"{e()} All joined members have been DMed!",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )

    if media_path and os.path.exists(media_path):
        os.remove(media_path)
    if user_id in user_temp:
        del user_temp[user_id]


# ============ ADVANCED CHANNEL FEATURES ============
async def refresh_channels(query, context):
    user_id = query.from_user.id
    user = db.get_user(user_id)

    if not user or not user.get("is_logged_in"):
        await query.edit_message_text(
            f"{e()} <b>Please login first!</b>",
            parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
        )
        return

    await query.edit_message_text(
        f"{refresh_emoji()} <b>Refreshing channels...</b>\nPlease wait.",
        parse_mode=ParseMode.HTML
    )

    channels = await manager.get_admin_channels(user["session_string"], refresh=True)

    if not channels:
        await query.edit_message_text(
            f"{e()} <b>No channels found!</b>",
            parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
        )
        return

    await query.edit_message_text(
        f"{success_emoji()} <b>Channels Refreshed!</b>\n"
        f"Found {len(channels)} admin channels.",
        parse_mode=ParseMode.HTML,
        reply_markup=channel_select_keyboard(channels, "select_channel")
    )

async def filter_channels(query, context, filter_type):
    user_id = query.from_user.id
    temp = user_temp.get(user_id, {})
    channels = temp.get("channels", [])

    if filter_type == "all":
        filtered = channels
    elif filter_type == "admin_only":
        filtered = [c for c in channels if c.get("is_admin")]
    elif filter_type == "owner_only":
        filtered = [c for c in channels if c.get("is_owner")]
    else:
        filtered = channels

    await query.edit_message_text(
        f"{filter_emoji()} <b>Filtered Channels:</b> {len(filtered)}\n"
        f"Select a channel:",
        parse_mode=ParseMode.HTML,
        reply_markup=channel_select_keyboard(filtered, "select_channel")
    )

async def sort_channels(query, context, sort_type):
    user_id = query.from_user.id
    temp = user_temp.get(user_id, {})
    channels = temp.get("channels", [])

    if sort_type == "recent":
        channels.sort(key=lambda x: x.get("date", ""), reverse=True)
    elif sort_type == "members":
        channels.sort(key=lambda x: x.get("participants_count", 0), reverse=True)
    elif sort_type == "name":
        channels.sort(key=lambda x: x.get("title", ""))

    await query.edit_message_text(
        f"{sort_emoji()} <b>Sorted by {sort_type.title()}</b>\n"
        f"Select a channel:",
        parse_mode=ParseMode.HTML,
        reply_markup=channel_select_keyboard(channels, "select_channel")
    )


# ============ PREMIUM PLANS ============
async def show_premium_plans(query, context):
    user_id = query.from_user.id
    status = get_premium_text(user_id)

    text = f"""{e()} <b>VIP Premium</b>
----------------------
{status}

Choose a plan to unlock unlimited sends! {e()}

Prices shown in INR."""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=premium_plans_keyboard())

async def process_plan_selection(query, context, data):
    user_id = query.from_user.id
    parts = data.split("_")
    days = int(parts[1])
    amount = int(parts[2])

    user_temp[user_id] = {"plan_days": days, "amount": amount}

    upi = db.get_setting("payment_upi") or "your-upi@bank"

    text = f"""{e()} <b>Payment</b>\nDear <b>{query.from_user.first_name}</b>,\nPlease pay <b>Rs.{amount}</b> to:\n\n<code>{upi}</code>\n\n{e()} <b>Plan:</b> {days} Days Premium\n{e()} <b>Amount:</b> Rs.{amount}\n\nAfter payment, send:\n1. UTR Number\n2. Screenshot of payment\n\n{e()} Type your UTR number now:"""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return STATE_PAYMENT_UTR

async def receive_utr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    utr = update.message.text.strip()
    temp = user_temp.get(user_id, {})

    if not temp:
        await update.message.reply_text(f"{e()} Session expired.", parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    user_temp[user_id]["utr"] = utr

    await update.message.reply_text(
        f"{e()} <b>UTR Received!</b>\n"
        f"Now send the screenshot of your payment:",
        parse_mode=ParseMode.HTML
    )
    return STATE_PAYMENT_SCREENSHOT

async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    temp = user_temp.get(user_id, {})

    if not temp:
        await update.message.reply_text(f"{e()} Session expired.", parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    if not update.message.photo:
        await update.message.reply_text(
            f"{e()} <b>Please send a screenshot!</b>",
            parse_mode=ParseMode.HTML
        )
        return STATE_PAYMENT_SCREENSHOT

    screenshot_id = update.message.photo[-1].file_id

    payment_id = db.add_payment(
        user_id, temp["plan_days"], temp["amount"],
        temp["utr"], screenshot_id
    )

    # Notify admin
    admin_text = f"""{e()} <b>New Payment!</b>\n<b>User:</b> <a href="tg://user?id={user_id}">{update.effective_user.first_name}</a>\n<b>User ID:</b> <code>{user_id}</code>\n<b>Plan:</b> {temp['plan_days']} Days\n<b>Amount:</b> Rs.{temp['amount']}\n<b>UTR:</b> <code>{temp['utr']}</code>\n<b>Payment ID:</b> <code>{payment_id}</code>"""

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=screenshot_id,
                caption=admin_text,
                parse_mode=ParseMode.HTML,
                reply_markup=admin_payment_keyboard(payment_id)
            )
        except Exception as ex:
            logger.error(f"Failed to notify admin {admin_id}: {ex}")

    await update.message.reply_text(
        f"{e()} <b>Payment Submitted!</b>\n"
        f"Your payment is under review.\n"
        f"You will be notified when approved.",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )

    del user_temp[user_id]
    return ConversationHandler.END

async def approve_payment(query, context, data):
    if not is_admin(query.from_user.id):
        await query.answer("Access Denied!")
        return

    payment_id = int(data.replace("approve_pay_", ""))
    payment = db.get_payment(payment_id)

    if not payment:
        await query.answer("Payment not found!")
        return

    if payment["status"] != "pending":
        await query.answer("Already processed!")
        return

    db.update_payment(payment_id, status="approved", approved_by=query.from_user.id, approved_at=datetime.now().isoformat())
    db.add_premium(payment["user_id"], payment["plan_days"])

    # Notify user
    try:
        await context.bot.send_message(
            chat_id=payment["user_id"],
            text=f"{e()} <b>Payment Approved!</b> {e()}\n"
                 f"Your {payment['plan_days']} days premium has been activated.\n"
                 f"Enjoy unlimited sends!",
            parse_mode=ParseMode.HTML
        )
    except:
        pass

    await query.edit_message_caption(
        caption=f"{query.message.caption}\n<b>Approved by:</b> {query.from_user.first_name}",
        parse_mode=ParseMode.HTML
    )
    await query.answer("Approved!")

async def disapprove_payment(query, context, data):
    if not is_admin(query.from_user.id):
        await query.answer("Access Denied!")
        return

    payment_id = int(data.replace("disapprove_pay_", ""))
    payment = db.get_payment(payment_id)

    if not payment:
        await query.answer("Payment not found!")
        return

    db.update_payment(payment_id, status="disapproved", approved_by=query.from_user.id, approved_at=datetime.now().isoformat())

    try:
        await context.bot.send_message(
            chat_id=payment["user_id"],
            text=f"{e()} <b>Payment Disapproved</b>\n"
                 f"Your payment was not approved.\n"
                 f"If you believe this is an error, please contact support.",
            parse_mode=ParseMode.HTML
        )
    except:
        pass

    await query.edit_message_caption(
        caption=f"{query.message.caption}\n<b>Disapproved by:</b> {query.from_user.first_name}",
        parse_mode=ParseMode.HTML
    )
    await query.answer("Disapproved!")


# ============ REDEEM CODE ============
async def start_redeem(query, context):
    await query.edit_message_text(
        f"{e()} <b>Redeem Code</b>\n"
        f"Enter your redeem code:",
        parse_mode=ParseMode.HTML
    )
    return STATE_REDEEM

async def receive_redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip().upper()

    redeem = db.get_redeem_code(code)

    if not redeem:
        await update.message.reply_text(
            f"{e()} <b>Invalid Code!</b>\nThis code does not exist.",
            parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
        )
        return ConversationHandler.END

    if redeem["uses_remaining"] <= 0:
        await update.message.reply_text(
            f"{e()} <b>Code Expired!</b>\nThis code has been used up.",
            parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
        )
        return ConversationHandler.END

    db.use_redeem_code(code)
    db.add_premium(user_id, redeem["days"])

    await update.message.reply_text(
        f"{e()} <b>Code Redeemed!</b> {e()}\n"
        f"You got <b>{redeem['days']} Days</b> Premium!",
        parse_mode=ParseMode.HTML, reply_markup=back_keyboard()
    )
    return ConversationHandler.END

# ============ REFER & EARN ============
async def show_refer(query, context):
    user_id = query.from_user.id
    user = db.get_user(user_id)
    refer_count = user.get("refer_count", 0) if user else 0
    bot_username = (await context.bot.get_me()).username
    refer_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    text = f"""{e()} <b>Refer & Earn</b>
----------------------

{e()} <b>Your Referrals:</b> {refer_count}
{e()} <b>Reward:</b> {refer_count} Days Premium

{e()} <b>How it works:</b>
- Share your link with friends
- When they buy any premium plan
- You get <b>1 Day Premium</b> per verified user!

{e()} <b>Your Link:</b>
<code>{refer_link}</code>"""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_keyboard())

# ============ CANCEL CONVERSATION ============
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_temp:
        del user_temp[user_id]
    await update.message.reply_text(
        f"{e()} Cancelled.",
        parse_mode=ParseMode.HTML,
        reply_markup=back_keyboard()
    )
    return ConversationHandler.END

# ============ ADMIN COMMANDS ============
async def admin_create_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Access Denied!")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /createcode <code> <days> [uses]
"
            "Example: /createcode VIP2024 7 10"
        )
        return

    code = args[0].upper()
    days = int(args[1])
    uses = int(args[2]) if len(args) > 2 else 1

    db.create_redeem_code(code, days, uses, update.effective_user.id)

    await update.message.reply_text(
        f"{e()} <b>Redeem Code Created!</b>\n"
        f"Code: <code>{code}</code>\n"
        f"Days: {days}\n"
        f"Uses: {uses}",
        parse_mode=ParseMode.HTML
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Access Denied!")
        return

    import sqlite3
    conn = sqlite3.connect(db.conn.database)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE is_logged_in = 1")
    logged_in = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'approved'")
    total_payments = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(plan_days) FROM payments WHERE status = 'approved'")
    total_days = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
    pending = cursor.fetchone()[0]

    conn.close()

    text = f"""{e()} <b>Bot Statistics</b>
----------------------
{e()} Total Users: {total_users}
{e()} Logged In: {logged_in}
{e()} Total Payments: {total_payments}
{e()} Premium Days Sold: {total_days}
{e()} Pending Payments: {pending}"""

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Access Denied!")
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    message = " ".join(context.args)

    import sqlite3
    conn = sqlite3.connect(db.conn.database)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    sent = 0
    failed = 0
    for (uid,) in users:
        try:
            await context.bot.send_message(uid, message, parse_mode=ParseMode.HTML)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1

    await update.message.reply_text(f"Sent: {sent}
Failed: {failed}")

async def admin_set_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Access Denied!")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setchannel <force|update> @channel")
        return

    key = context.args[0]
    channel = context.args[1]

    if key == "force":
        db.set_setting("force_join_channel", channel)
        await update.message.reply_text(f"Force join channel set to {channel}")
    elif key == "update":
        db.set_setting("update_channel", channel)
        await update.message.reply_text(f"Update channel set to {channel}")
    else:
        await update.message.reply_text("Use 'force' or 'update'")

async def admin_set_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Access Denied!")
        return

    if not context.args:
        await update.message.reply_text("Usage: /setupi <upi_id>")
        return

    upi = context.args[0]
    db.set_setting("payment_upi", upi)
    await update.message.reply_text(f"UPI ID set to: {upi}")

# ============ MAIN ============
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Account login conversation
    account_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_account, pattern="^add_account$")],
        states={
            STATE_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
            STATE_OTP: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_otp)],
            STATE_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_2fa)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Set message conversation
    message_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_set_message, pattern="^set_message$")],
        states={
            STATE_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Payment conversation
    payment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(process_plan_selection, pattern="^plan_")],
        states={
            STATE_PAYMENT_UTR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_utr)],
            STATE_PAYMENT_SCREENSHOT: [MessageHandler(filters.PHOTO, receive_screenshot)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Redeem conversation
    redeem_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_redeem, pattern="^redeem_code$")],
        states={
            STATE_REDEEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_redeem_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Handlers - IMPORTANT: Order matters! Conversation handlers must be added BEFORE generic callback handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(account_conv)
    application.add_handler(message_conv)
    application.add_handler(payment_conv)
    application.add_handler(redeem_conv)

    # Generic callback handler - must be AFTER conversation handlers
    application.add_handler(CallbackQueryHandler(button_callback))

    # Admin commands
    application.add_handler(CommandHandler("createcode", admin_create_code))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_handler(CommandHandler("setchannel", admin_set_channel))
    application.add_handler(CommandHandler("setupi", admin_set_upi))

    logger.info("Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
