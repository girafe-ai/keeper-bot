from array import array
import logging
from typing import Optional, Tuple

from telegram import __version__ as TG_VER

try:
    from telegram import __version_info__
except ImportError:
    __version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        f"This example is not compatible with your current PTB version {TG_VER}. To view the "
        f"{TG_VER} version of this example, "
        f"visit https://docs.python-telegram-bot.org/en/v{TG_VER}/examples.html"
    )
from telegram import Chat, ChatMember, ChatMemberUpdated, Update
from telegram.constants import ParseMode
from telegram.ext import Application, ChatMemberHandler, CommandHandler, ContextTypes

# Enable logging

logging.basicConfig(
    format="%(asctime)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


def extract_status_change(chat_member_update: ChatMemberUpdated) -> Optional[Tuple[bool, bool]]:

    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

    if status_change is None:
        return None

    old_status, new_status = status_change
    was_member = old_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (old_status == ChatMember.RESTRICTED and old_is_member is True)
    is_member = new_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (new_status == ChatMember.RESTRICTED and new_is_member is True)

    return was_member, is_member


async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
 
    result = extract_status_change(update.my_chat_member)
    if result is None:
        return
    was_member, is_member = result

    # Let's check who is responsible for the change
    cause_name = update.effective_user.full_name

    # Handle chat types differently:
    chat = update.effective_chat
    if chat.type == Chat.PRIVATE:
        if not was_member and is_member:
            logger.info("%s started the bot", cause_name)
            context.bot_data.setdefault("user_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s blocked the bot", cause_name)
            context.bot_data.setdefault("user_ids", set()).discard(chat.id)
    elif chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        if not was_member and is_member:
            logger.info("%s added the bot to the group %s", cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s removed the bot from the group %s", cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).discard(chat.id)
    else:
        if not was_member and is_member:
            logger.info("%s added the bot to the channel %s", cause_name, chat.title)
            context.bot_data.setdefault("channel_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s removed the bot from the channel %s", cause_name, chat.title)
            context.bot_data.setdefault("channel_ids", set()).discard(chat.id)


async def show_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows which chats the bot is in"""
    user_ids = ", ".join(str(uid) for uid in context.bot_data.setdefault("user_ids", set()))
    group_ids = ", ".join(str(gid) for gid in context.bot_data.setdefault("group_ids", set()))
    channel_ids = ", ".join(str(cid) for cid in context.bot_data.setdefault("channel_ids", set()))
    text = (
        f"@{context.bot.username} is currently in a conversation with the user IDs {user_ids}."
        f" Moreover it is a member of the groups with IDs {group_ids} "
        f"and administrator in the channels with IDs {channel_ids}."
    )
    await update.effective_message.reply_text(text)

def get_whitelist() -> array:
    # Will pull list of allowed users from db in future.
    return [770539667, 155719408, 1378282982]

def validate_chat_member(member_id: int) -> bool:
    
    white_list = get_whitelist()
    
    if member_id in white_list:
        logger.info(f"Member {member_id} is in whitelist.")
        return True
    logger.info(f"Member {member_id} is not in whitelist.")
    return False

async def handle_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    result = extract_status_change(update.chat_member)
    
    if result is None:
        return

    was_member, is_member = result
    chat_id = update.chat_member.chat.id
    cause_name = update.chat_member.from_user.mention_html()
    member_name = update.chat_member.new_chat_member.user.mention_html()
    member_id = update.chat_member.new_chat_member.user.id


    if not was_member and is_member:
        if validate_chat_member(member_id=member_id):
            await update.effective_chat.send_message(
                f"{member_name} was added by {cause_name}. Welcome!",
                parse_mode=ParseMode.HTML,
            )
        else:
            logger.info(f"CHAT_ID ({chat_id}): " \
                 f"User {update.chat_member.new_chat_member.user.id}({update.chat_member.new_chat_member.user.first_name}) " \
                 f"has been baned. " \
                 "User not in whitelist!")
            await update.effective_chat.ban_member(user_id=member_id)
    elif was_member and not is_member :
        await update.effective_chat.send_message(
            f"{member_name} in gulag now. Thanks a lot, {cause_name} ...",
            parse_mode=ParseMode.HTML,
        )


def main() -> None:
    logger.info("Starting bot")
    application = Application.builder().token("5747557099:AAHE7F-69x8H8yJJYKBPd55CtG3DvOGCKnI").build()
    logger.info("Bot is running...")
    application.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    application.add_handler(CommandHandler("show_chats", show_chats))
    application.add_handler(ChatMemberHandler(handle_chat_members, ChatMemberHandler.CHAT_MEMBER))
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    


if __name__ == "__main__":
    main()