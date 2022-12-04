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

        chats_query = {"$or": [{"allowed_users": user.username},{"allowed_groups": dbgroup_names}]}
        dbchats = [chat for chat in chats_col.find(chats_query)]
        logger.info(f"... successfully found groups in collection! {dbchats}")

        return dbchats

    except Exception as e:
        logger.exception(str(e))
        return []

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
