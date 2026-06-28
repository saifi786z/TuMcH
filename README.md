# 🤖 Auto DM Forward Bot - Telegram Bot (UPDATED)

A powerful Telegram bot for mass DM campaigns using your own Telegram account.

## 🆕 NEW FEATURES & CHANGES

### 1. OTP Spacing Format
- OTP now displays with spaces between digits
- Example: `74034` → `7 4 0 3 4`
- Added back button to OTP screen

### 2. Back Buttons Added
- **Payment Approved** screen (2nd image) - Added back button to return to dashboard
- **Redeem Code** screen (3rd image) - Added back button to return to dashboard

### 3. DM to Contacts → DM to ALL Personal DMs
- **BEFORE**: Only fetched contacts list
- **AFTER**: Fetches ALL personal DMs including:
  - Private 1-on-1 chats
  - Groups
  - Supergroups
  - Channels
- Shows breakdown: Private Chats | Groups | Channels

### 4. Split "DM to Pending Requests" into TWO buttons:

#### 🔵 DM to Pending Requests
- Sends message to users who have requested to join your channel
- Uses REAL Telegram API for pending join requests
- Falls back to recent participants if API unavailable

#### 🟢 DM to Joined Members (NEW)
- Sends message to already joined members of selected channel(s)
- Can select one channel or ALL channels
- Fetches complete member list with pagination

### 5. Advanced Channel Fetching
- **Refresh Channels**: Real-time refresh of admin channels
- **Filter Options**: All | Admin Only | Owner Only
- **Sort Options**: Recent | Members Count | Name
- Shows real-time member counts
- Shows admin status (Owner/Admin)
- Shows channel link availability

## 📁 Files Updated

| File | Changes |
|------|---------|
| `main.py` | Added new handlers, OTP spacing, back buttons, all DMs fetching, joined members, advanced channel features |
| `keyboards.py` | Added new emoji helpers, channel action keyboard, fetch options keyboard |
| `telethon_manager.py` | Added `get_all_personal_dms()`, `get_joined_members()`, `get_pending_requests()`, `get_admin_channels()` with advanced info, `get_all_channels()`, `get_recent_active_members()` |
| `config.py` | No changes needed |
| `database.py` | No changes needed |

## 🎛️ Updated Dashboard Buttons

```
[➕ Add Account]
[✏️ Set Message] [👁️ Preview Message]
[👥 DM to Contacts]      ← Now fetches ALL DMs
[⏳ DM to Pending Requests]  ← Real pending requests
[✅ DM to Joined Members]    ← NEW: Already joined members
[💎 Buy Premium]
[🎁 Redeem Code] [🤝 Refer & Earn]
[📖 How to Use] [📢 Updates]
```

## 🚀 Deployment

### Step 1: Get Your Bot Token
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot and copy the **Bot Token**

### Step 2: Get Telethon API Credentials
1. Go to [my.telegram.org](https://my.telegram.org)
2. Login with your phone number
3. Go to **API development tools**
4. Create a new app and copy **API ID** and **API Hash**

### Step 3: Set Environment Variables

```bash
export BOT_TOKEN="your_bot_token_here"
export ADMIN_IDS="123456789,987654321"  # Your Telegram user ID(s)
export TELETHON_API_ID="2040"           # Your API ID
export TELETHON_API_HASH="your_api_hash" # Your API Hash
```

### Step 4: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 5: Run the Bot
```bash
python main.py
```

## 🎛️ Admin Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `/createcode` | Create redeem code | `/createcode CODE123 7 10` |
| `/stats` | View bot statistics | `/stats` |
| `/broadcast` | Send message to all users | `/broadcast Hello everyone!` |
| `/setchannel` | Set force/update channel | `/setchannel force @channel` |
| `/setupi` | Set payment UPI ID | `/setupi upi@bank` |

## 🔧 Complete Feature List

- ✅ Force join channel check
- ✅ OTP & 2FA login via Telethon
- ✅ **OTP with spacing** (e.g., "7 4 0 3 4")
- ✅ **Back buttons** on all screens
- ✅ Set DM message (text + image)
- ✅ **DM to ALL personal DMs** (private + groups + channels)
- ✅ **DM to Pending Requests** (real join requests)
- ✅ **DM to Joined Members** (already joined users)
- ✅ **Advanced channel fetching** with refresh/filter/sort
- ✅ Premium plans with payment approval
- ✅ Redeem codes
- ✅ Refer & Earn system
- ✅ Admin panel with stats
- ✅ Dynamic premium emojis
- ✅ SQLite database

## ⚠️ Important Notes

1. **Telegram API Limits**: The bot respects Telegram's rate limits with delays between messages.
2. **Session Security**: User session strings are stored securely in the database.
3. **FloodWait**: If Telegram rate limits are hit, the bot will wait and retry.
4. **Pending Requests**: Uses real Telegram API for join requests, falls back to recent participants.
5. **Joined Members**: Fetches complete member list with pagination (200 per batch).

## 📝 License

For educational purposes only. Use responsibly.
