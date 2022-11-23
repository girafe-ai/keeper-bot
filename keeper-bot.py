import logging
import configparser
import os
import pymongo

from typing import Optional, Tuple
from array import array
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
from telegram.ext import Application, ChatMemberHandler, ContextTypes


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


def get_users_collection():
    col = db["users"]
    col.create_index("user_id", unique=True)
    return col


def extract_status_change(chat_member_update: ChatMemberUpdated) -> Optional[Tuple[bool, bool]]:

    status_change = chat_member_update.difference().get("status")
    old_is_member, new_is_member = chat_member_update.difference().get("is_member",
                                                                       (None, None))

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
            logger.info(
                f"Bot has been added to {chat.title}. Cause {cause_name}")
            context.bot_data.setdefault("group_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s removed the bot from the group %s",
                        cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).discard(chat.id)
    else:
        if not was_member and is_member:
            logger.info("%s added the bot to the channel %s",
                        cause_name, chat.title)
            context.bot_data.setdefault("channel_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s removed the bot from the channel %s",
                        cause_name, chat.title)
            context.bot_data.setdefault("channel_ids", set()).discard(chat.id)


def list_all_groups_of_chat(chat):
    try:

        collection = db[chat]
        group_list = list(collection.find({}, {"_id": 0}))
        if len(group_list) == 0:
            logger.warning("there are no groups!")

        return group_list

    except Exception as error:
        return str(error)


def list_users_of_group(group_name, include_id={"_id": 0}):
    try:
        logger.info("listing users")
        collection = get_users_collection()
        users_list = list(collection.find(
            {"group": {"$eq": group_name}}, include_id))
        if len(users_list) == 0:
            logger.warning("The users list is empty")
        return users_list
    except Exception as error:
        logger.error(str(error))
        return str(error)


def check_chat_access(chat):
    '''Check if collection exists'''
    if chat not in db.list_collection_names():
        return f'''Chat `{chat}` doesn't exist'''

    groups_of_chat = list_all_groups_of_chat(chat=chat)
    users_of_chat = []
    for group_name in groups_of_chat:
        users_of_chat.append(list_users_of_group(
            group_name=group_name.get("name")))

    return users_of_chat


def validate_chat_member(user_id: int, chat_id: str) -> bool:
    try:

        groups_with_access = check_chat_access(chat=str(chat_id))
        # logger.info(str(users_with_access))
        for users_with_access in groups_with_access:
            for user in users_with_access:
                logger.info(f"{user}")
                if user.get("user_id") == user_id:
                    logger.info(f"Member {user_id} is in whitelist.")
                    return True
        logger.info(f"Member {user_id} is not in whitelist.")
        return False
    except Exception as e:
        logger.critical(f"{str(e)}")
        return False


async def handle_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    result = extract_status_change(update.chat_member)

    if result is None:
        return

    was_member, is_member = result
    chat_id = update.chat_member.chat.id
    cause_name = update.chat_member.from_user.mention_html()
    member_name = update.chat_member.new_chat_member.user.mention_html()
    user_id = update.chat_member.new_chat_member.user.id

    if not was_member and is_member:
        if validate_chat_member(user_id=user_id, chat_id=chat_id):
            await update.effective_chat.send_message(
                f"{member_name} was added by {cause_name}. Welcome!",
                parse_mode=ParseMode.HTML,
            )
        else:
            logger.info(f"CHAT_ID ({chat_id}): "
                        f"User {update.chat_member.new_chat_member.user.id}({update.chat_member.new_chat_member.user.first_name}) "
                        f"has been baned. "
                        "User not in whitelist!")
            await update.effective_chat.ban_member(user_id=user_id)
    elif was_member and not is_member:
        await update.effective_chat.send_message(
            f"{member_name} in gulag now. Thanks a lot, {cause_name} ...",
            parse_mode=ParseMode.HTML,
        )


def main() -> None:
    try:
        logger.info("Starting bot")
        application = Application.builder().token(TG_TOKEN).build()
        logger.info("Bot is running...")
        application.add_handler(ChatMemberHandler(
            track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
        application.add_handler(ChatMemberHandler(
            handle_chat_members, ChatMemberHandler.CHAT_MEMBER))
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as error:
        logger.fatal("Bot failed to start. Error: " + str(error))


if __name__ == "__main__":

    TG_TOKEN = os.environ.get("TG_TOKEN")
    MONGO_URL = os.environ.get("MONGO_URL")
    logger = logging.getLogger(__name__)
    client = pymongo.MongoClient(MONGO_URL)
    db = client["mipt"]

    main()
