
import html
import sys

from aiogram.types import Update
from redis.exceptions import RedisError

from hitsuki import OWNER_ID, bot, dp
from hitsuki.services.redis import redis
from hitsuki.utils.logger import log

SENT = []


def catch_redis_error(**dec_kwargs):
    def wrapped(func):
        async def wrapped_1(*args, **kwargs):
            global SENT
            # We can't use redis here
            # So we save data - 'message sent to' in a list variable
            update: Update = args[0]

            if update.message is not None:
                message = update.message
            elif update.callback_query is not None:
                message = update.callback_query.message
            elif update.edited_message is not None:
                message = update.edited_message
            else:
                return True

            chat_id = -1001605464716 if "chat" in message else None
            try:
                return await func(*args, **kwargs)
            except RedisError:
                if chat_id not in SENT:
                    text = (
                        "Sorry for inconvenience! I encountered error in my redis DB, which is necessary for  "
                        "running bot \n\nPlease report this to my support group immediately when you see this error!"
                    )
                    if await bot.send_message(chat_id, text):
                        SENT.append(chat_id)
                # Alert bot owner
                if OWNER_ID not in SENT:
                    text = "Raichu panic: Got redis error"
                    if await bot.send_message(OWNER_ID, text):
                        SENT.append(OWNER_ID)
                log.error(RedisError, exc_info=True)
                return True

        return wrapped_1

    return wrapped


@dp.errors_handler()
@catch_redis_error()
async def all_errors_handler(update: Update, error):
    if update.message is not None:
        message = update.message
    elif update.callback_query is not None:
        message = update.callback_query.message
    elif update.edited_message is not None:
        message = update.edited_message
    else:
        return True  # we don't want other guys in playground

    chat_id = -1001605464716
    err_tlt = sys.exc_info()[0].__name__
    err_msg = str(sys.exc_info()[1])

    log.warn(
        "Error caused update is: \n"
        + html.escape(str(parse_update(message)), quote=False)
    )

    if redis.get(chat_id) == str(error):
        # by err_tlt we assume that it is same error
        return True

    if err_tlt == "BadRequest" and err_msg == "Have no rights to send a message":
        return True

    ignored_errors = (
        "FloodWaitError",
        "RetryAfter",
        "SlowModeWaitError",
        "InvalidQueryID",
    )
    if err_tlt in ignored_errors:
        return True

    if err_tlt in ("NetworkError", "TelegramAPIError", "RestartingTelegram"):
        log.error("Conn/API error detected", exc_info=error)
        return True

    text = "<u><b>Raichu Client Error...!</b></u>\n\n"
    text += "<b>Forward this to @XRaichu_Official</b>\n\n"
    text += "<i>--------------------Starting Crash Log--------------------</i>\n"
    text += f"<code>{html.escape(err_tlt, quote=False)}: {html.escape(err_msg, quote=False)}</code>\n"
    text += "<i>--------------------Finishing Crash Log-------------------</i>\n\n"
    text += "<b>© 2020-2021 @XRaichu_Official</b>"
    redis.set(chat_id, str(error), ex=600)
    await bot.send_message(chat_id, text)


def parse_update(update):
    # The parser to hide sensitive informations in the update (for logging)

    if isinstance(update, Update):  # Hacc
        if update.message is not None:
            update = update.message
        elif update.callback_query is not None:
            update = update.callback_query.message
        elif update.edited_message is not None:
            update = update.edited_message
        else:
            return

    if "chat" in update:
        chat = update["chat"]
        chat["id"] = chat["title"] = chat["username"] = chat["first_name"] = chat[
            "last_name"
        ] = []
    if user := update["from"]:
        user["id"] = user["first_name"] = user["last_name"] = user["username"] = []
    if "reply_to_message" in update:
        reply_msg = update["reply_to_message"]
        reply_msg["chat"]["id"] = reply_msg["chat"]["title"] = reply_msg["chat"][
            "first_name"
        ] = reply_msg["chat"]["last_name"] = reply_msg["chat"]["username"] = []
        reply_msg["from"]["id"] = reply_msg["from"]["first_name"] = reply_msg["from"][
            "last_name"
        ] = reply_msg["from"]["username"] = []
        reply_msg["message_id"] = []
        reply_msg["new_chat_members"] = reply_msg["left_chat_member"] = []
    if ("new_chat_members", "left_chat_member") in update:
        update["new_chat_members"] = update["left_chat_member"] = []
    if "message_id" in update:
        update["message_id"] = []
    return update
