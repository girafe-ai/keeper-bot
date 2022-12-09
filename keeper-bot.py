#!/usr/bin/env python
# pylint: disable=unused-argument, wrong-import-position
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to handle '(my_)chat_member' updates.
Greets new users & keeps track of which chats the bot is in.

Usage:
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
import configparser
from typing import Optional, Tuple
import jinja2

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
import telegram

from telegram import Chat, ChatMember, ChatMemberUpdated, Update
from telegram.constants import ParseMode
from telegram.ext import Application, ChatMemberHandler, CommandHandler, ContextTypes, PicklePersistence

import mongodb

# Enable logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info("User ID is: %s, User nickname is: %s", user.id, user.username)

    dbchats = mongodb.get_user_chats(user)

    invite_links = []
    for dbchat in dbchats:
        if not dbchat.get("tg_id"):
            continue
        invite_link = await context.bot.create_chat_invite_link(chat_id=dbchat["tg_id"])
        invite_links.append((dbchat["_id"], invite_link.invite_link))
        logger.info(f"I GOT INVITE LINK {invite_link}")

    template_string = """
Greetings @{{ username }}! I am keeper bot for all of Girafe-ai telegram chats.
And as far as I know you can join some of them!

Your invite links:

{% for chat_name, chat_link in user_chats -%}

{{ chat_name }}:  {{ chat_link }}
{% endfor %}
    """

    environment = jinja2.Environment()
    template = environment.from_string(template_string)
    text = template.render(username=user.username, user_chats=invite_links)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


def extract_status_change(chat_member_update: ChatMemberUpdated) -> Optional[Tuple[bool, bool]]:
    """Takes a ChatMemberUpdated instance and extracts whether the 'old_chat_member' was a member
    of the chat and whether the 'new_chat_member' is a member of the chat. Returns None, if
    the status didn't change.
    """
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

def update_chat_status(chat):
    chats_col = get_chats_collection()
    chats_query = {"_id": chat}
    chats_col.update_one(
        {'_id': chat.title},
        {"$set": {
                "tg_id": chat.id,
                "managed": True
                }})

    logger.info(f"... successfully updated chats in collection!")

async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tracks the chats the bot is in."""
    result = extract_status_change(update.my_chat_member)
    if result is None:
        return
    was_member, is_member = result

    # Let's check who is responsible for the change
    cause_name = update.effective_user.full_name

    chat = update.effective_chat
    if chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        if not was_member and is_member:
            logger.info("%s added the bot to the group %s", cause_name, chat)
            update_chat_status(chat)
            context.bot_data.setdefault("group_ids", set()).add(chat.id)
        elif was_member and not is_member:
            logger.info("%s removed the bot from the group %s", cause_name, chat.title)
            context.bot_data.setdefault("group_ids", set()).discard(chat.id)

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

def check_user(user, chat):
    logger.info("CHecking User with ID: %s and nickname: %s", user.id, user.username)
    try:
        dbchats = mongodb.get_user_chats(user)
        dbchat_ids = [chat.get("tg_id") for chat in dbchats]

        if chat.id in dbchat_ids:
            return True
        else:
            return False

    except Exception as e:
        logger.exception(str(e))
        raise(e)


async def greet_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greets new users in chats and announces when someone leaves"""
    result = extract_status_change(update.chat_member)
    if result is None:
        return

    user = update.chat_member.new_chat_member.user
    chat = update.effective_chat

    is_allowed = check_user(user, chat)
    logger.info(str(is_allowed))
    was_member, is_member = result
    cause_name = update.chat_member.from_user.mention_html()
    member_name = update.chat_member.new_chat_member.user.mention_html()

    if not was_member and is_member:
        if is_allowed:
            await update.effective_chat.send_message(
                f"{member_name} was added by {cause_name}. YOU ARE ALLOWED! Welcome!",
                parse_mode=ParseMode.HTML,
            )
        else:
            admins = await chat.get_administrators()
            for admin in admins:
                try:
                    await admin.user.send_message(
                        f"{member_name} was added by {cause_name} to chat named {chat.title} and HE IS NOT ALLOWED THERE!",
                        parse_mode=ParseMode.HTML,
                    )
                except Exception as e:
                    logger.error(str(e))
                    continue

    elif was_member and not is_member:
        await update.effective_chat.send_message(
            f"{member_name} is no longer with us. Thanks a lot, {cause_name} ...",
            parse_mode=ParseMode.HTML,
        )


async def doctor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    managed_chats = mongodb.get_managed_chats()
    if len(managed_chats) == 0:
        await update.effective_chat.send_message(
            f"sorry there are no any chats I have to keep eye on"
        )
    else:
        logger.info(f"starting to heal context storage")
        try:
            for chat in managed_chats:
                tg_id = chat["tg_id"]
                logger.info(f"adding {tg_id} to storage")
                context.bot_data.setdefault(
                    "group_ids",
                    set()
                ).add(chat["tg_id"])
        except Exception as e:
            logger.error(str(e))

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.

    config = configparser.ConfigParser()
    config.read('config.ini')

    token = config['DEFAULT']['TOKEN']

    persistence = PicklePersistence(
        filepath="keeper-bot",
        update_interval=5
    )

    application = Application.builder()\
        .token(token)\
        .persistence(persistence=persistence)\
        .build()

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    doctor_handler = CommandHandler('doctor', doctor)
    application.add_handler(doctor_handler)

    # Keep track of which chats the bot is in
    application.add_handler(
        ChatMemberHandler(
            track_chats,
            ChatMemberHandler.MY_CHAT_MEMBER
        )
    )
    application.add_handler(
        CommandHandler(
            "show_chats",
            show_chats
        )
    )

    # Handle members joining/leaving chats.
    application.add_handler(
        ChatMemberHandler(
            greet_chat_members,
            ChatMemberHandler.CHAT_MEMBER
        )
    )

    # Run the bot until the user presses Ctrl-C
    # We pass 'allowed_updates' handle *all* updates including `chat_member` updates
    # To reset this, simply pass `allowed_updates=[]`
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
