"""Telethon Session Manager - Advanced Channel Fetching"""
import asyncio
import os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.channels import (
    GetAdminedPublicChannelsRequest,
    GetParticipantsRequest,
    GetFullChannelRequest
)
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import (
    InputPeerEmpty, InputPeerUser, InputPeerChannel,
    ChannelParticipantsRecent, ChannelParticipantsAdmins,
    ChannelParticipantsKicked, ChannelParticipantsBanned,
    ChannelParticipantsSearch, ChannelParticipant,
    ChannelParticipantAdmin, ChannelParticipantCreator,
    UserStatusRecently, UserStatusOnline, UserStatusOffline
)
from telethon.sessions import StringSession

class TelethonManager:
    def __init__(self):
        self.sessions = {}
        self.api_id = int(os.getenv("TELETHON_API_ID", "2040"))
        self.api_hash = os.getenv("TELETHON_API_HASH", "b18441a1ff607e10a989891a5462e627")

    async def create_client(self, phone, session_string=None):
        if session_string:
            client = TelegramClient(
                StringSession(session_string),
                self.api_id, self.api_hash
            )
        else:
            client = TelegramClient(
                StringSession(),
                self.api_id, self.api_hash
            )
        await client.connect()
        return client

    async def send_code(self, phone):
        client = await self.create_client(phone)
        try:
            result = await client.send_code_request(phone)
            session_string = client.session.save()
            await client.disconnect()
            return {"success": True, "phone_code_hash": result.phone_code_hash, "session_string": session_string}
        except Exception as e:
            await client.disconnect()
            return {"success": False, "error": str(e)}

    async def verify_code(self, phone, code, phone_code_hash, session_string):
        client = await self.create_client(phone, session_string)
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            me = await client.get_me()
            new_session = client.session.save()
            await client.disconnect()
            return {"success": True, "session_string": new_session, "user_id": me.id}
        except SessionPasswordNeededError:
            await client.disconnect()
            return {"success": False, "need_2fa": True, "session_string": client.session.save()}
        except Exception as e:
            await client.disconnect()
            return {"success": False, "error": str(e)}

    async def verify_2fa(self, phone, password, session_string):
        client = await self.create_client(phone, session_string)
        try:
            await client.sign_in(password=password)
            me = await client.get_me()
            new_session = client.session.save()
            await client.disconnect()
            return {"success": True, "session_string": new_session, "user_id": me.id}
        except Exception as e:
            await client.disconnect()
            return {"success": False, "error": str(e)}

    # ============ ADVANCED DM FETCHING - ALL PERSONAL DMs ============
    async def get_all_personal_dms(self, session_string):
        """Fetch ALL personal DMs (not just contacts) - includes groups, channels, and private chats"""
        client = await self.create_client("", session_string)
        try:
            # Get all dialogs (conversations)
            dialogs = await client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=500,
                hash=0
            ))

            all_dms = []
            for dialog in dialogs.dialogs:
                peer = dialog.peer
                try:
                    entity = await client.get_entity(peer)

                    # Skip bots
                    if hasattr(entity, 'bot') and entity.bot:
                        continue

                    # Get user info
                    user_id = None
                    name = ""
                    username = ""
                    chat_type = "unknown"

                    if hasattr(peer, 'user_id'):
                        # Private chat
                        user_id = peer.user_id
                        name = entity.first_name or ""
                        if entity.last_name:
                            name += " " + entity.last_name
                        username = entity.username or ""
                        chat_type = "private"
                    elif hasattr(peer, 'chat_id'):
                        # Basic group
                        user_id = peer.chat_id
                        name = entity.title or ""
                        username = ""
                        chat_type = "group"
                    elif hasattr(peer, 'channel_id'):
                        # Channel/Supergroup
                        user_id = peer.channel_id
                        name = entity.title or ""
                        username = entity.username or ""
                        chat_type = "channel" if entity.broadcast else "supergroup"

                    if user_id and name:
                        all_dms.append({
                            "id": user_id,
                            "name": name.strip(),
                            "username": username,
                            "type": chat_type,
                            "unread_count": dialog.unread_count or 0,
                            "last_message_date": dialog.date.isoformat() if dialog.date else None
                        })
                except Exception:
                    continue

            await client.disconnect()
            return all_dms
        except Exception as e:
            await client.disconnect()
            return []

    # ============ GET ONLY PRIVATE CONTACTS (legacy) ============
    async def get_contacts(self, session_string):
        """Fetch only private 1-on-1 contacts"""
        client = await self.create_client("", session_string)
        try:
            dialogs = await client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=500,
                hash=0
            ))
            contacts = []
            for dialog in dialogs.dialogs:
                peer = dialog.peer
                if hasattr(peer, 'user_id'):
                    try:
                        user = await client.get_entity(peer)
                        if user and not user.bot:
                            contacts.append({
                                "id": user.id,
                                "name": (user.first_name or "") + (" " + user.last_name if user.last_name else ""),
                                "username": user.username or "",
                                "type": "private"
                            })
                    except:
                        pass
            await client.disconnect()
            return contacts
        except Exception as e:
            await client.disconnect()
            return []

    # ============ ADVANCED CHANNEL FETCHING ============
    async def get_admin_channels(self, session_string, refresh=False):
        """Fetch all channels where user is admin with advanced info"""
        client = await self.create_client("", session_string)
        try:
            # Get admined channels
            channels = await client(GetAdminedPublicChannelsRequest())

            result = []
            for ch in channels.chats:
                try:
                    # Get full channel info
                    full_channel = await client(GetFullChannelRequest(ch))

                    # Get participant count
                    participants_count = 0
                    if hasattr(full_channel.full_chat, 'participants_count'):
                        participants_count = full_channel.full_chat.participants_count

                    # Get admin rights
                    is_owner = False
                    is_admin = False
                    try:
                        participant = await client.get_permissions(ch, await client.get_me())
                        is_admin = participant.is_admin
                        is_owner = ch.creator if hasattr(ch, 'creator') else False
                    except:
                        pass

                    result.append({
                        "id": ch.id,
                        "title": ch.title,
                        "username": ch.username or "",
                        "participants_count": participants_count,
                        "is_owner": is_owner,
                        "is_admin": is_admin,
                        "has_link": bool(ch.username),
                        "date": ch.date.isoformat() if hasattr(ch, 'date') else None
                    })
                except Exception:
                    # Fallback to basic info
                    result.append({
                        "id": ch.id,
                        "title": ch.title,
                        "username": ch.username or "",
                        "participants_count": 0,
                        "is_owner": False,
                        "is_admin": True,
                        "has_link": bool(ch.username),
                        "date": None
                    })

            await client.disconnect()
            return result
        except Exception as e:
            await client.disconnect()
            return []

    # ============ GET PENDING JOIN REQUESTS ============
    async def get_pending_requests(self, session_string, channel_id):
        """Fetch REAL pending join requests for a channel"""
        client = await self.create_client("", session_string)
        try:
            from telethon.tl.functions.channels import GetParticipantRequestsRequest

            channel = await client.get_entity(channel_id)

            pending = []
            try:
                # Try to get actual pending requests
                requests = await client(GetParticipantRequestsRequest(
                    channel=channel,
                    limit=500
                ))

                for req in requests.requests:
                    user = req.user
                    pending.append({
                        "id": user.id,
                        "name": (user.first_name or "") + (" " + user.last_name if user.last_name else ""),
                        "username": user.username or "",
                        "request_date": req.date.isoformat() if hasattr(req, 'date') else None,
                        "type": "pending_request"
                    })
            except Exception:
                # Fallback: Get recent participants who might be pending
                participants = await client(GetParticipantsRequest(
                    channel, ChannelParticipantsRecent(), 0, 500, hash=0
                ))

                for user in participants.users:
                    if not user.bot:
                        pending.append({
                            "id": user.id,
                            "name": (user.first_name or "") + (" " + user.last_name if user.last_name else ""),
                            "username": user.username or "",
                            "type": "recent_participant"
                        })

            await client.disconnect()
            return pending
        except Exception as e:
            await client.disconnect()
            return []

    # ============ GET JOINED MEMBERS ============
    async def get_joined_members(self, session_string, channel_id, limit=500):
        """Fetch all joined members of a channel"""
        client = await self.create_client("", session_string)
        try:
            channel = await client.get_entity(channel_id)

            members = []
            offset = 0
            chunk_size = 200

            while True:
                participants = await client(GetParticipantsRequest(
                    channel, ChannelParticipantsSearch(''), offset, chunk_size, hash=0
                ))

                if not participants.users:
                    break

                for user in participants.users:
                    if not user.bot:
                        members.append({
                            "id": user.id,
                            "name": (user.first_name or "") + (" " + user.last_name if user.last_name else ""),
                            "username": user.username or "",
                            "status": str(user.status) if user.status else "unknown",
                            "type": "joined_member"
                        })

                offset += len(participants.users)
                if len(participants.users) < chunk_size or len(members) >= limit:
                    break

                await asyncio.sleep(0.5)

            await client.disconnect()
            return members
        except Exception as e:
            await client.disconnect()
            return []

    # ============ GET ALL CHANNELS (not just admin) ============
    async def get_all_channels(self, session_string):
        """Fetch ALL channels the user is in (member or admin)"""
        client = await self.create_client("", session_string)
        try:
            dialogs = await client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=500,
                hash=0
            ))

            channels = []
            for dialog in dialogs.dialogs:
                peer = dialog.peer
                if hasattr(peer, 'channel_id'):
                    try:
                        entity = await client.get_entity(peer)
                        if entity.broadcast or entity.megagroup:
                            channels.append({
                                "id": entity.id,
                                "title": entity.title,
                                "username": entity.username or "",
                                "is_broadcast": entity.broadcast,
                                "is_megagroup": entity.megagroup,
                                "participants_count": entity.participants_count if hasattr(entity, 'participants_count') else 0
                            })
                    except:
                        pass

            await client.disconnect()
            return channels
        except Exception as e:
            await client.disconnect()
            return []

    # ============ GET RECENT ACTIVE MEMBERS ============
    async def get_recent_active_members(self, session_string, channel_id, days=7):
        """Get members who were active recently"""
        client = await self.create_client("", session_string)
        try:
            from datetime import datetime, timedelta
            channel = await client.get_entity(channel_id)

            members = []
            participants = await client(GetParticipantsRequest(
                channel, ChannelParticipantsRecent(), 0, 500, hash=0
            ))

            cutoff = datetime.now() - timedelta(days=days)

            for user in participants.users:
                if not user.bot:
                    is_recent = False
                    if hasattr(user.status, 'was_online'):
                        is_recent = user.status.was_online > cutoff
                    elif isinstance(user.status, UserStatusRecently):
                        is_recent = True
                    elif isinstance(user.status, UserStatusOnline):
                        is_recent = True

                    members.append({
                        "id": user.id,
                        "name": (user.first_name or "") + (" " + user.last_name if user.last_name else ""),
                        "username": user.username or "",
                        "status": str(user.status) if user.status else "unknown",
                        "is_recent": is_recent,
                        "type": "active_member"
                    })

            await client.disconnect()
            return members
        except Exception as e:
            await client.disconnect()
            return []

    # ============ MESSAGE SENDING ============
    async def send_message(self, session_string, target_id, text, media_path=None):
        client = await self.create_client("", session_string)
        try:
            entity = await client.get_entity(target_id)
            if media_path and os.path.exists(media_path):
                await client.send_file(entity, media_path, caption=text)
            else:
                await client.send_message(entity, text)
            await client.disconnect()
            return {"success": True}
        except FloodWaitError as e:
            await client.disconnect()
            return {"success": False, "error": f"FloodWait: {e.seconds}s", "flood": True, "seconds": e.seconds}
        except Exception as e:
            await client.disconnect()
            return {"success": False, "error": str(e)}

    async def send_bulk_messages(self, session_string, targets, text, media_path=None, delay=2):
        results = {"success": 0, "failed": 0, "errors": []}
        for target in targets:
            result = await self.send_message(session_string, target["id"], text, media_path)
            if result["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({"target": target, "error": result.get("error", "Unknown")})
                if result.get("flood"):
                    await asyncio.sleep(result.get("seconds", 30))
            await asyncio.sleep(delay)
        return results

manager = TelethonManager()
