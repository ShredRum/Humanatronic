import asyncio
import logging

from aiogram import types, Bot, Dispatcher
from aiogram.filters.command import Command


import openai_core

import utils

config = utils.ConfigData()
bot = Bot(token=config.token)
dp = Dispatcher()

dialogs = {}


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.reply("Я не бот, я живой человек! Не забывай об этом во время разговора со мной!")


@dp.message(lambda message: utils.check_names(message, config.my_id))
async def chatgpt(message: types.Message):
    logging.info(f"User {utils.username_parser(message)} send a request to ChatGPT")
    if dialogs.get(message.chat.id) is None:
        dialogs.update({message.chat.id: openai_core.Dialog(config)})
    await bot.send_chat_action(chat_id=message.chat.id, action='typing')
    await message.reply(dialogs.get(message.chat.id).get_answer(message))


async def main() -> None:
    config.my_id = (await bot.get_me()).id
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.info("###HUMANOTRONIC v0.0.2 LAUNCHED SUCCESSFULLY###")
    asyncio.run(main())
