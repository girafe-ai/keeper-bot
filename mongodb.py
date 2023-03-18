import pymongo
import logging

# logging.config.fileConfig('logging.conf', disable_existing_loggers=False)
logger = logging.getLogger(__name__)


def get_groups_collection():
    client = pymongo.MongoClient()
    mipt_db = client["mipt"]
    collection = mipt_db["groups"]
    return collection

def get_users_collection():
    client = pymongo.MongoClient()
    mipt_db = client["mipt"]
    collection = mipt_db["users"]
    return collection

def get_chats_collection():
    client = pymongo.MongoClient()
    mipt_db = client["mipt"]
    collection = mipt_db["chats"]
    return collection


def get_user_chats(user) -> list:
    logger.info("User ID is: %s, User nickname is: %s", user.id, user.username)

    users_col = get_users_collection()
    groups_col = get_groups_collection()
    chats_col = get_chats_collection()

    try:
        user_query = {"_id": user.username}
        dbuser = users_col.find_one(user_query)
        logger.info(f"... successfully found user in collection! {dbuser}")

        groups_query = {"user_ids": user.username}
        dbgroups = [group for group in groups_col.find(groups_query)]
        logger.info(f"... successfully found groups in collection! {dbgroups}")
        dbgroup_names = [group["_id"] for group in dbgroups]

        chats_query = {"$or": [{"allowed_users": user.username},{"allowed_groups": {'$in': dbgroup_names}}]}
        dbchats = [chat for chat in chats_col.find(chats_query)]
        logger.info(f"... successfully found groups in collection! {dbchats}")

        return dbchats

    except Exception as e:
        logger.exception(str(e))
        return []

def get_current_chat_members(chat_id) -> set:
    chats_col = get_chats_collection()
    chat = chats_col.find_one({'tgid': chat_id})
    current_members = set()
    for member in chat.get('current_members'):
        current_members.add(member)
    logger.info(f"current chat members are {current_members}")
    return current_members

def get_allowed_chat_members(chat_id) -> set:
    chats_col = get_chats_collection()
    chat = chats_col.find_one({'tgid': chat_id})
    allowed_groups = chat['allowed_groups']
    allowed_members_tgids = set()
    for group in allowed_groups:
        for tgid in get_group_members_tgids(group):
            allowed_members_tgids.add(tgid)
        for tgid in chat['allowed_users_tgids']:
            allowed_members_tgids.add(tgid)
    logger.info(f"allowed chat members are {allowed_members_tgids}")
    return allowed_members_tgids

def get_group_members_tgids(group_id) -> list:
    groups_col = get_groups_collection()
    group = groups_col.find_one({'_id': group_id})
    return(group.get('members_tgids'))

def get_managed_chats():
    chats_col = get_chats_collection()
    try:
        managed_chats = list()
        cursor = chats_col.find({})
        for document in cursor:
            if document.get("tg_id") and document.get("managed"):
                managed_chats.append(document)
    except Exception as e:
        logger.error(str(e))

    return managed_chats

def get_user(user_id):
    users_col = get_users_collection()
    user = users_col.find_one({'tgid': user_id})
    logger.info(f"I found user {user}")
    return user
