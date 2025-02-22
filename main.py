import asyncio
import base64
import logging
import random
import time
import traceback

from aiogram import types, Bot, Dispatcher, exceptions
from aiogram.filters.command import Command

import uni_core
import sql_worker
import utils

config = utils.ConfigData()
bot = Bot(token=config.token)
dp = Dispatcher()
sql_helper = sql_worker.SqlWorker(config.path + "database.db")

dialogs = {}
flood_wait = {}


def is_flooded(message):
    last_msg_time = flood_wait.get(message.from_user.id)
    if last_msg_time is None:
        flood_wait.update({message.from_user.id: int(time.time())})
        return False
    if int(time.time()) - last_msg_time <= 5:
        logging.info(f"Rejected request from user {utils.username_parser(message)} "
                     f"by floodwait. Retry after 5 seconds.")
        return True
    flood_wait.update({message.from_user.id: int(time.time())})
    return False


@dp.message(Command("start"))
async def start(message: types.Message):
    if not await utils.check_whitelist(message, config):
        return
    if config.service_messages:
        await message.reply("Я не бот, я живой человек! Не забывай об этом во время разговора со мной!")


@dp.message(lambda message: utils.check_names(message, config.my_id, config.prompts))
async def chatgpt(message: types.Message):

    async def send_message(text, parse=None, reply=False):
        try:
            if reply:
                await message.reply(text, allow_sending_without_reply=True, parse_mode=parse)
            else:
                await bot.send_message(message.chat.id, text, thread_id, parse_mode=parse)
        except exceptions.TelegramBadRequest as exc:
            if "can't parse entities" in str(exc):
                logging.warning("Telegram could not parse markdown in message, it will be sent without formatting")
                await send_message(text, reply=reply)
            elif "text must be non-empty" in str(exc) and len(answer) == 1:
                await send_message("ᅠ ", reply=reply)
            else:
                logging.error(traceback.format_exc())

    if not await utils.check_whitelist(message, config):
        return

    if message.text is None and message.caption is None and not config.vision:
        return

    if message.quote and not config.reply_to_quotes:
        return

    photo_base64 = None
    if (message.photo is not None or message.sticker is not None) and config.vision:
        try:
            if message.photo:
                byte_file = await bot.download(message.photo[-1].file_id)
                mime = "image/jpeg"
            else:
                byte_file = await bot.download(message.sticker.thumbnail.file_id)
                mime = "image/webp"
            # noinspection PyUnresolvedReferences
            photo_base64 = {"data": base64.b64encode(byte_file.getvalue()).decode('utf-8'), "mime": mime}
        except Exception as e:
            logging.error(f"{e}\n{traceback.format_exc()}")
            await message.reply(random.choice(config.prompts.errors))
            return

    context = message.chat.id if not config.unified_context else 0
    if dialogs.get(context) is None:
        dialogs.update({context: uni_core.Dialog(config, sql_helper, context)})
    if is_flooded(message):
        return

    reply_msg = ""
    if message.reply_to_message:
        if message.quote:
            reply_msg = message.quote.text
        elif message.reply_to_message.text or message.reply_to_message.caption:
            reply_msg = message.reply_to_message.text or message.reply_to_message.caption

    logging.info(f"User {utils.username_parser(message)} send a request to ChatGPT")
    parse_mode = 'markdown' if config.markdown_enable else None
    await bot.send_chat_action(chat_id=message.chat.id, action='typing')
    answer = utils.answer_parser(await dialogs.get(context).get_answer(message, reply_msg, photo_base64), config)
    await send_message(answer[0], parse=parse_mode, reply=True)
    thread_id = message.message_thread_id if message.is_topic_message else None
    for paragraph in answer[1::]:
        await asyncio.sleep(5)
        await bot.send_chat_action(chat_id=message.chat.id, action='typing')
        await asyncio.sleep(5)
        await send_message(paragraph, parse=parse_mode)


async def main() -> None:
    config.my_id = (await bot.get_me()).id
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.info("###HUMANOTRONIC v4.5.1 (Dualcore) LAUNCHED SUCCESSFULLY###")
    asyncio.run(main())
