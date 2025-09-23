import asyncio
import logging
import random
import time
import traceback

from aiogram import types, Bot, Dispatcher, exceptions
from aiogram.filters.command import Command

import ai_core
import sql_worker
import utils

config = utils.ConfigData()
bot = Bot(token=config.token)
dp = Dispatcher()
sql_helper = sql_worker.SqlWorker(config.path + "database.db")

dialogs = {}
flood_wait = {}
chats_queue = {}


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
        await utils.send_message(message, bot,
                                 "Я не бот, я живой человек! Не забывай об этом во время разговора со мной!",
                                 reply=True)


@dp.message()
async def chatgpt(message: types.Message):

    call_type = utils.check_names(message, config)
    if not call_type:
        return

    if not await utils.check_whitelist(message, config):
        return

    if not any([message.text, message.caption, config.vision != "disabled"]):
        return

    if message.quote and not config.reply_to_quotes:
        return

    photo_base64 = None
    try:
        if config.vision != "disabled":
            photo_base64 = (await utils.get_image_from_message(message, bot) or
                            await utils.get_image_from_message(message.reply_to_message, bot))
    except Exception as e:
        logging.error(f"{e}\n{traceback.format_exc()}")
        await message.reply(random.choice(config.prompts.errors))
        return

    context = message.chat.id if not config.unified_context else 0
    if dialogs.get(context) is None:
        dialogs.update({context: ai_core.Dialog(config, sql_helper, context)})
    if is_flooded(message):
        return

    reply_msg_text = None
    if message.reply_to_message:
        if message.quote:
            reply_msg_text = message.quote.text
        elif any([message.reply_to_message.text, message.reply_to_message.caption,
                  utils.get_poll_text(message.reply_to_message)]):
            reply_msg_text = (message.reply_to_message.text
                              or message.reply_to_message.caption
                              or utils.get_poll_text(message.reply_to_message))
    reply_msg = {"name": utils.username_parser(message.reply_to_message),
                 "text": reply_msg_text} if reply_msg_text else None

    logging.info(f"User {utils.username_parser(message)} send a request to ChatGPT")
    parse_mode = 'markdown' if config.markdown_enable else None
    try:
        if call_type == 'default':
            await bot.send_chat_action(chat_id=message.chat.id, action='typing')
    except exceptions.TelegramBadRequest as e:
        logging.error(f'Error sending message to chat {message.chat.id}\n{e}')
        return
    try:
        answer = utils.answer_parser(await dialogs.get(context).get_answer(message, reply_msg, photo_base64), config)
    except ai_core.ApiRequestException:
        if call_type == 'default':
            answer = [random.choice(config.prompts.errors)]
        else:
            return
    chat_queue = chats_queue.get(message.chat.id)
    if not chat_queue:
        chats_queue.update({message.chat.id: asyncio.Lock()})
        chat_queue = chats_queue.get(message.chat.id)

    await chat_queue.acquire()
    await utils.send_message(message, bot, answer[0], config.markdown_filter, parse_mode=parse_mode, reply=True)
    for paragraph in answer[1::]:
        await asyncio.sleep(5)
        try:
            await bot.send_chat_action(chat_id=message.chat.id, action='typing')
        except exceptions.TelegramBadRequest:
            pass
        await asyncio.sleep(5)
        await utils.send_message(message, bot, paragraph, config.markdown_filter, parse_mode=parse_mode)
    chat_queue.release()


async def main():
    get_me = await bot.get_me()
    config.my_id = get_me.id
    config.my_username = f"@{get_me.username}"
    logging.info("###HUMANOTRONIC v4.11 (Memory Reboot) LAUNCHED SUCCESSFULLY###")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
