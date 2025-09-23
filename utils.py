import random
from threading import BoundedSemaphore
import base64
import configparser
import importlib
import logging
import os
import re
import sys
import time
import traceback
import unicodedata
from importlib import reload
from io import BytesIO
from typing import Optional, Union

from PIL import Image

from aiogram import types, exceptions


class ConfigData:
    path = ""
    my_id = ""
    my_username = ""
    api_queue: BoundedSemaphore

    def __init__(self):

        try:
            self.path = sys.argv[1] + "/"
            if not os.path.isdir(sys.argv[1]):
                print("WARNING: working path IS NOT EXIST. Remake.")
                os.mkdir(sys.argv[1])
        except IndexError:
            pass
        except IOError:
            traceback.print_exc()
            print("ERROR: Failed to create working directory! Bot will be closed!")
            sys.exit(1)

        reload(logging)
        logging.basicConfig(
            handlers=[
                logging.FileHandler(self.path + "logging.log", 'w', 'utf-8'),
                logging.StreamHandler(sys.stdout)
            ],
            force=True,
            level=logging.INFO,
            format='%(asctime)s %(levelname)s: %(message)s',
            datefmt="%d-%m-%Y %H:%M:%S")

        prompts_path = f"{self.path[:-1]}.prompts" if self.path else "prompts"
        if not os.path.isfile(f"{self.path}prompts.py") and self.path:
            logging.warning(f"The prompts file was not found in the {self.path}, a generic prompt will be used!")
            prompts_path = "prompts"
        try:
            self.prompts = importlib.import_module(prompts_path)
        except Exception as e:
            logging.error(f'Module prompts.py is invalid! {e}')
            logging.error(traceback.format_exc())
            sys.exit(1)

        if not os.path.isfile(self.path + "config.ini"):
            print("Config file isn't found! Trying to remake!")
            self.remake_conf()

        config = configparser.ConfigParser()
        while True:
            try:
                config.read(self.path + "config.ini")
                self.token = config["Telegram"]["token"]
                self.unified_context = self.bool_init(config["Telegram"]["unified-context"])
                self.service_messages = self.bool_init(config["Telegram"]["service-messages"])
                self.markdown_enable = self.bool_init(config["Telegram"]["markdown-enable"])
                self.markdown_filter = self.bool_init(config["Telegram"]["markdown-filter"])
                self.unicode_filter = self.bool_init(config["Telegram"]["unicode-filter"])
                self.split_paragraphs = self.bool_init(config["Telegram"]["split-paragraphs"])
                self.reply_to_quotes = self.bool_init(config["Telegram"]["reply-to-quotes"])
                self.max_answer_len = int(config["Telegram"]["max-answer-len"])
                self.random_response_probability = float(config["Telegram"]["random-response-probability"]
                                                         .replace(',', "."))
                self.whitelist = config["Telegram"]["whitelist-chats"]
                self.api_key = config["Personality"]["api-key"]
                self.model = config["Personality"]["model"]
                self.model_vendor = config["Personality"]["model-vendor"].lower()
                self.timezone = int(config["Personality"]["timezone"])
                self.summarizer_limit = int(config["Personality"]["summarizer-limit"])
                self.tokens_per_answer = int(config["Personality"]["tokens-per-answer"])
                self.memory_dump_size = int(config["Personality"]["memory-dump-size"])
                self.vision = config["Personality"]["vision"]
                self.stream_mode = self.bool_init(config["Personality"]["stream-mode"])
                self.attempts = int(config["Personality"]["gen-attempts"])
                self.full_debug = self.bool_init(config["Personality"]["full-debug"])
                queue_size = int(config["Personality"]["queue-size"])
                self.summarizer_engine = config["Personality"]["summarizer-engine"].lower()
                self.summarizer_iterations = int(config["Personality"]["summarizer-iterations"])
                self.summarizer_minimal_ratio = float(config["Personality"]["summarizer-minimal-ratio"]
                                                      .replace(',', "."))
                self.prefill_mode = config["Personality"]["prefill-mode"].lower()
                self.memory_api_key = config["Memory"]["api-key"]
                self.memory_model = config["Memory"]["model"]
                self.memory_model_vendor = config["Memory"]["model-vendor"].lower()
                self.memory_tokens_per_answer = int(config["Memory"]["tokens-per-answer"])
                self.memory_stream_mode = self.bool_init(config["Memory"]["stream-mode"])
                self.memory_attempts = int(config["Memory"]["gen-attempts"])
                memory_queue_size = int(config["Memory"]["queue-size"])
                if self.model_vendor not in ("openai", "anthropic"):
                    raise KeyError('The model vendor must be "openai" or "anthropic"')
                if self.summarizer_engine not in ('personality', 'memory'):
                    raise KeyError('The "summarizer-engine" parameter value can only be "personality" or "memory"')
                if self.memory_model_vendor not in ("openai", "anthropic"):
                    raise KeyError('The "memory" model vendor must be "openai" or "anthropic"')
                if self.prefill_mode not in ('assistant', 'pre-user', 'post-user', 'disabled'):
                    raise KeyError('The "prefill-mode" parameter value can only be '
                                   '"assistant", "pre-user", "post-user" or "disabled"')
                if self.vision not in ("enabled", "memory-mode", "disabled"):
                    raise KeyError('The "vision" parameter value can only be '
                                   '"enabled", "memory-mode" or "disabled"')
                break
            except Exception as e:
                logging.error(str(e))
                logging.error(traceback.format_exc())
                time.sleep(1)
                print("\nInvalid config file! Trying to remake!")
                agreement = "-1"
                while agreement != "y" and agreement != "n" and agreement != "":
                    agreement = input("Do you want to reset your broken config file on defaults? (Y/n): ")
                    agreement = agreement.lower()
                if agreement == "" or agreement == "y":
                    self.remake_conf()
                else:
                    sys.exit(0)
        try:
            self.base_url = config["Personality"]["base-url"]
            if self.base_url == "":
                raise KeyError
        except (KeyError, TypeError):
            self.base_url = None

        try:
            self.temperature = float(config["Personality"]["temperature"])
            if self.temperature == "":
                raise KeyError
        except (KeyError, TypeError, ValueError):
            self.temperature = None

        try:
            self.memory_base_url = config["Memory"]["base-url"]
            if self.memory_base_url == "":
                raise KeyError
        except (KeyError, TypeError):
            self.memory_base_url = None

        try:
            self.memory_temperature = float(config["Memory"]["temperature"])
            if self.memory_temperature == "":
                raise KeyError
        except (KeyError, TypeError, ValueError):
            self.memory_temperature = None

        if self.attempts <= 0:
            logging.warning('''Value "gen-attempts" can't be less than or equal to 0, set to default (3)''')
            self.attempts = 3

        if queue_size <= 0:
            logging.warning('''Value "queue-size" can't be less than or equal to 0, set to default (3)''')
            queue_size = 3

        if self.memory_attempts <= 0:
            logging.warning('''Value "gen-attempts" can't be less than or equal to 0, set to default (3)''')
            self.attempts = 3

        if memory_queue_size <= 0:
            logging.warning('''Value "queue-size" can't be less than or equal to 0, set to default (3)''')
            queue_size = 3

        if not 1 <= self.summarizer_iterations <= 10:
            logging.warning('''Value "summarizer-iterations" can only have a value from 1 to 10, set to default (3)''')
            self.summarizer_iterations = 3

        if self.summarizer_minimal_ratio < 0:
            logging.warning('''Value "summarizer-minimal-ratio" can only be greater than or equal to 0, 
            set to default (0.7)''')
            self.summarizer_minimal_ratio = 0.7

        self.api_queue = BoundedSemaphore(queue_size)
        self.memory_api_queue = BoundedSemaphore(memory_queue_size)

    def remake_conf(self):
        token, api_key, model = "", "", ""
        while token == "":
            token = input("Please, write your bot token: ")
        while api_key == "":
            api_key = input("Please, write your API key: ")
        while model == "":
            model = input("Please, write your model name: ")
        model_vendor = "anthropic" if "claude" in model else "openai"

        memory_api_key = input('Please, write your API key for memory model '
                               'or leave blank to use values from the main model: ') or api_key
        memory_model = input('Please, write your memory model name '
                             'or leave blank to use values from the main model: ') or model
        memory_model_vendor = "anthropic" if "claude" in memory_model else "openai"

        config = configparser.ConfigParser()
        config.add_section("Telegram")
        config.set("Telegram", "token", token)
        config.set("Telegram", "whitelist-chats", "")
        config.set("Telegram", "unified-context", "false")
        config.set("Telegram", "service-messages", "true")
        config.set("Telegram", "markdown-enable", "true")
        config.set("Telegram", "markdown-filter", "true")
        config.set("Telegram", "unicode-filter", "true")
        config.set("Telegram", "split-paragraphs", "true")
        config.set("Telegram", "reply-to-quotes", "true")
        config.set("Telegram", "max-answer-len", "2000")
        config.set("Telegram", "random-response-probability", "0.01")
        config.add_section("Personality")
        config.set("Personality", "api-key", api_key)
        config.set("Personality", "base-url", "")
        config.set("Personality", "model", model)
        config.set("Personality", "model-vendor", model_vendor)
        config.set("Personality", "temperature", "0.5")
        config.set("Personality", "timezone", "0")
        config.set("Personality", "stream-mode", "false")
        config.set("Personality", "gen-attempts", "3")
        config.set("Personality", "queue-size", "3")
        config.set("Personality", "full-debug", "false")
        config.set("Personality", "summarizer-limit", "12000")
        config.set("Personality", "tokens-per-answer", "6000")
        config.set("Personality", "memory-dump-size", "2000")
        config.set("Personality", "summarizer-engine", "personality")
        config.set("Personality", "summarizer-iterations", "3")
        config.set("Personality", "summarizer-minimal-ratio", "0.8")
        config.set("Personality", "prefill-mode", "pre-user")
        if "vision" in model:
            config.set("Personality", "vision", "enabled")
        else:
            config.set("Personality", "vision", "disabled")
        config.add_section("Memory")
        config.set("Memory", "api-key", memory_api_key)
        config.set("Memory", "base-url", "")
        config.set("Memory", "model", memory_model)
        config.set("Memory", "model-vendor", memory_model_vendor)
        config.set("Memory", "temperature", "0.5")
        config.set("Memory", "stream-mode", "false")
        config.set("Memory", "gen-attempts", "3")
        config.set("Memory", "queue-size", "3")
        config.set("Memory", "tokens-per-answer", "6000")
        try:
            config.write(open(self.path + "config.ini", "w"))
            print("New config file was created successful")
        except IOError:
            print("ERR: Bot cannot write new config file and will close")
            logging.error(traceback.format_exc())
            sys.exit(1)

    @staticmethod
    def bool_init(var):
        if var.lower() in ("false", "0"):
            return False
        elif var.lower() in ("true", "1"):
            return True
        else:
            raise TypeError


def check_names(message, config) -> Union[None, str]:
    """
    The bot will only respond if called by name (if it's public chat)
    :param message:
    :param config:
    :return:
    """

    if not any([message.text, message.caption, message.photo, message.sticker, message.poll]):
        return None
    msg_txt = message.text or message.caption
    if message.chat.id == message.from_user.id:
        if msg_txt is not None:
            if re.fullmatch(r"/[a-zA-Z0-9]+", msg_txt.split(" ", 1)[0]):
                return None
        return 'default'
    if message.reply_to_message:
        if message.reply_to_message.from_user.id == config.my_id:
            return 'default'
    if msg_txt is None:
        return None
    if config.my_username in msg_txt:
        return 'default'
    msg_txt = re.sub(r'[^\w\s]', '', msg_txt.lower()).split()
    for name in config.prompts.names:
        if name.lower() in msg_txt:
            return 'default'
    if random.random() < config.random_response_probability:
        return 'auto'
    return None


def username_parser(message, html=False):
    if message.from_user.first_name == "":
        return "DELETED USER"

    if message.from_user.username == "GroupAnonymousBot":
        return "ANONYMOUS ADMIN"

    if message.from_user.last_name is None:
        username = str(message.from_user.first_name)
    else:
        username = str(message.from_user.first_name) + " " + str(message.from_user.last_name)

    if not html:
        return username

    return html_fix(username)


def html_fix(text):
    """
    Fixes some characters that could cause problems with parse_mode=html
    :param text:
    :return:
    """
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def current_time_info(config, int_time: int = None):
    if not int_time:
        int_time = int(time.time())
    current_time = time.strftime("%d.%m.%Y, %a, %H:%M", time.gmtime(int_time + config.timezone * 3600))
    return f"Current time: {current_time}"


async def check_whitelist(message: types.Message, config):
    if str(message.chat.id) in config.whitelist or not config.whitelist:
        return "True"
    private = "с тобой" if message.chat is None else "здесь"
    # noinspection PyUnresolvedReferences
    chat_name = username_parser(message) if message.chat.title is None else message.chat.title
    logging.info(f"Rejected request from chat {chat_name}")
    if config.service_messages:
        await message.reply(f"Извини, но мне нельзя говорить {private}. "
                            f"Это не моя вина, просто на всех не разорваться.")
    return False


def get_image_width(photo_base64):
    width, _ = Image.open(BytesIO(base64.b64decode(photo_base64.split("base64,")[-1]))).size
    return width


def message_len_parser(text, config, fn_list):
    max_len = config.max_answer_len

    while len(text) > max_len:

        parsed = False

        for parse_fn in fn_list:
            for index in range(max_len, 1, -1):
                if parse_fn(text, index):
                    yield text[:index]
                    text = text[index + 1:]
                    parsed = True
                    break
            if parsed:
                break
        if parsed:
            continue
        yield text[:max_len]
        text = text[max_len:]

    yield text


def answer_parser(text, config) -> list:
    def lines_parser(txt, index):
        return txt[index] == "\n"

    def sentences_parser(txt, index):
        return txt[index] == " " and txt[index - 1] in ".!?"

    def space_parser(txt, index):
        return txt[index] == " "

    fn_list = (lines_parser, sentences_parser, space_parser)

    answer = text.split("\n\n") if config.split_paragraphs else [text]
    split_answer = []
    for answer_part in answer:
        split_answer.extend([parsed_txt for parsed_txt in message_len_parser(answer_part, config, fn_list)])
    return split_answer


async def get_image_from_message(message, bot) -> Optional[dict]:
    if not message:
        return None
    elif message.photo:
        byte_file = await bot.download(message.photo[-1].file_id)
        mime = "image/jpeg"
    elif message.sticker:
        byte_file = await bot.download(message.sticker.thumbnail.file_id)
        mime = "image/webp"
    else:
        return None
    # noinspection PyUnresolvedReferences
    return {"data": base64.b64encode(byte_file.getvalue()).decode('utf-8'), "mime": mime}


def get_poll_text(message):
    if not message.poll:
        return None
    poll_text = message.poll.question + "\n\n"
    for option in message.poll.options:
        poll_text += "☑️ " + option.text + "\n"
    return poll_text


async def send_message(message, bot, text: str, markdown_filter=None, parse_mode=None, reply=False):
    thread_id = message.message_thread_id if message.is_topic_message else None
    if markdown_filter and not parse_mode:
        text = text.replace('*', '').replace('`', '')
    try:
        if reply:
            await message.reply(text, allow_sending_without_reply=True, parse_mode=parse_mode)
        else:
            await bot.send_message(message.chat.id, text, thread_id, parse_mode=parse_mode)
    except exceptions.TelegramBadRequest as e:
        if "can't parse entities" in str(e):
            logging.warning("Telegram could not parse markdown in message, it will be sent without formatting")
            await send_message(message, bot, text, markdown_filter, None, reply)
        elif "text must be non-empty" in str(e) or 'message text is empty' in str(e):
            logging.warning(f"Failed to send empty message in chat! Message content: {text}")
        else:
            logging.error(traceback.format_exc())


def unicode_filter(str_):
    return "".join(ch for ch in str_ if unicodedata.category(ch)[0] != 'C' or ch in {'\n', '\r', '\t'})
