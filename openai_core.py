# from dotenv import load_dotenv
import json
import logging
import random
import asyncio
import time
import traceback

import openai
import tiktoken

import utils


class ApiRequestException(Exception):
    pass


class Dialog:

    def __init__(self, config, sql_helper, context):
        self.dialogue_locker = asyncio.Lock()
        self.config = config
        self.sql_helper = sql_helper
        self.context = context
        self.last_time = 0
        try:
            dialog_data = sql_helper.dialog_get(context)
        except Exception as e:
            dialog_data = []
            logging.error("Humanotronic was unable to read conversation information! Please check your database!")
            logging.error(f"{e}\n{traceback.format_exc()}")
        if not dialog_data:
            start_time = f"{utils.current_time_info(config).split(maxsplit=2)[2]} - it's time to start our conversation"
            dialog_history = []
        else:
            dialog_history = json.loads(dialog_data[0][1])
            start_time = (f"{utils.current_time_info(config, dialog_data[0][2]).split(maxsplit=2)[2]} - "
                          f"it's time to start our conversation")
            # Pictures saved in the database may cause problems when working without Vision
            if not config.vision:
                dialog_history = self.cleaning_images(dialog_history)
        self.dialog_history = [{"role": "system",
                                "content": f"{config.prompts.start}\n{config.prompts.hard}\n{start_time}"}]
        if dialog_history:
            self.dialog_history.extend(dialog_history)
        self.client = openai.OpenAI(api_key=config.api_key, base_url=config.base_url)

    def send_api_request(self, model, messages,
                         max_tokens=1000,
                         temperature=None,
                         attempts=3):
        for _ in range(attempts):
            try:
                completion = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False)
                answer = completion.choices[0].message.content
                total_tokens = completion.usage.total_tokens
                if total_tokens == 0:
                    raise ApiRequestException(answer)
                return answer, total_tokens
            except Exception as e:
                logging.error(f"{e}\n{traceback.format_exc()}")
        raise ApiRequestException

    async def get_answer(self, message, reply_msg, photo_base64):
        chat_name = utils.username_parser(message) if message.chat.title is None else message.chat.title
        if reply_msg:
            if self.dialog_history[-1]['content'] == reply_msg['content']:
                reply_msg = None

        msg_txt = message.text or message.caption
        if msg_txt is None:
            msg_txt = "I sent a photo"

        prompt = ""
        if any([random.randint(1, 30) == 1,  # Time is reminded of Humanotronic with a probability of 1/30
                int(time.time()) - self.last_time >= 3600,
                "врем" in msg_txt.lower(),
                "час" in msg_txt.lower()
                ]):
            prompt += f"{utils.current_time_info(self.config)} "
            logging.info(f"Time updated for dialogue in chat {chat_name}")
        prompt += f"{utils.username_parser(message)}: {msg_txt}"
        dialog_buffer = self.dialog_history.copy()
        if reply_msg:
            dialog_buffer.append(reply_msg)
        if photo_base64:
            dialog_buffer.append({"role": "user",
                                  "content": [{"type": "text", "text": prompt},
                                              {"type": "image_url", "image_url":
                                                  {"url": f"data:image/jpeg;base64,{photo_base64}"}}]})
        else:
            dialog_buffer.append({"role": "user", "content": prompt})
        summarizer_used = False
        if self.dialogue_locker.locked():
            logging.info(f"Adding messages is blocked for chat {chat_name} due to the work of the summarizer.")
            summarizer_used = True
            await self.dialogue_locker.acquire()
            self.dialogue_locker.release()
        try:
            args = [self.config.model,
                    dialog_buffer,
                    self.config.tokens_per_answer,
                    self.config.temperature]
            answer, total_tokens = await asyncio.get_running_loop().run_in_executor(
                None, self.send_api_request, *args)
        except ApiRequestException:
            return random.choice(self.config.prompts.errors)

        logging.info(f'{total_tokens} tokens counted by the OpenAI API in chat {chat_name}.')
        if self.dialogue_locker.locked():
            logging.info(f"Adding messages is blocked for chat {chat_name} due to the work of the summarizer.")
            summarizer_used = True
            await self.dialogue_locker.acquire()
            self.dialogue_locker.release()
        if reply_msg:
            self.dialog_history.append(reply_msg)
        if photo_base64:
            self.dialog_history.extend([{"role": "user",
                                         "content": [{"type": "text", "text": prompt},
                                                     {"type": "image_url", "image_url":
                                                         {"url": f"data:image/jpeg;base64,{photo_base64}"}}]},
                                        {"role": "assistant", "content": str(answer)}])
        else:
            self.dialog_history.extend([{"role": "user", "content": prompt},
                                        {"role": "assistant", "content": str(answer)}])
        if self.config.vision and len(self.dialog_history) > 10:
            self.dialog_history = self.cleaning_images(self.dialog_history, last_only=True)
        if total_tokens >= self.config.summarizer_limit and not summarizer_used:
            logging.info(f"The token limit {self.config.summarizer_limit} for "
                         f"the {chat_name} chat has been exceeded. Using a lazy summarizer")
            async with self.dialogue_locker:
                await self.summarizer(chat_name)
        try:
            self.sql_helper.dialog_update(self.context, json.dumps(self.dialog_history[1::]))
        except Exception as e:
            logging.error("Humanotronic was unable to save conversation information! Please check your database!")
            logging.error(f"{e}\n{traceback.format_exc()}")
        self.last_time = int(time.time())
        return answer

    # This code clears the context from old images so that they do not cause problems in operation
    # noinspection PyTypeChecker
    @staticmethod
    def cleaning_images(dialog, last_only=False):

        def cleaner():
            if isinstance(dialog[index]['content'], list):
                for i in dialog[index]['content']:
                    if i['type'] == 'text':
                        dialog[index]['content'] = i['text']

        if last_only:
            for index in range(len(dialog) - 11, -1, -1):
                cleaner()
        else:
            for index in range(len(dialog)):
                cleaner()
        return dialog

    # noinspection PyTypeChecker
    async def summarizer(self, chat_name):
        sys_prompt = self.dialog_history[:1:]
        if self.dialog_history[1]['role'] == 'assistant':
            # The dialogue cannot begin with the words of the assistant, which means it was a diary entry
            last_diary = self.dialog_history[1]['content']
            dialogue = self.dialog_history[2::]
        else:
            last_diary = None
            dialogue = self.dialog_history[1::]
        model = self.config.model
        tokens_per_message = 3
        tokens_per_name = 1
        if model == "gpt-3.5-turbo-0301":
            tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
            tokens_per_name = -1  # if there's a name, the role is omitted
        if model in {
            "gpt-3.5-turbo-0613",
            "gpt-3.5-turbo-16k-0613",
            "gpt-4-0314",
            "gpt-4-32k-0314",
            "gpt-4-0613",
            "gpt-4-32k-0613",
            "gpt-3.5-turbo-0301"
        }:
            pass
        elif "gpt-3.5-turbo" in model:
            logging.warning("GPT-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
            model = "gpt-3.5-turbo-0613"
        elif "gpt-4" in model:
            logging.warning("GPT-4 may update over time. Returning num tokens assuming gpt-4-0613.")
            model = "gpt-4-0613"

        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            print("Warning: model not found. Using cl100k_base encoding.")
            encoding = tiktoken.get_encoding("cl100k_base")

        compression_limit = int(self.config.summarizer_limit * 0.7)
        compression_limit_count = 0
        split = 0
        for message in dialogue:
            compression_limit_count += tokens_per_message
            for key, value in message.items():
                try:
                    compression_limit_count += len(encoding.encode(value))
                except TypeError:
                    for image_chk in value:
                        if image_chk['type'] == 'text':
                            compression_limit_count += len(encoding.encode(image_chk['text']))
                        elif image_chk['type'] == 'image_url':
                            compression_limit_count += utils.get_image_width(image_chk['image_url']['url'])
                            # We can't accurately count image tokens, so we'll use an approximate value based on width
                if key == "name":
                    compression_limit_count += tokens_per_name
            split += 1
            if compression_limit_count >= compression_limit:
                break

        summarizer_text = self.config.prompts.summarizer
        if last_diary is not None:
            summarizer_text += f"\n{self.config.prompts.summarizer_last}"
        summarizer_text = summarizer_text.format(self.config.memory_dump_size)
        compressed_dialogue = [{'role': 'system', "content": summarizer_text}]
        if last_diary is None:
            compressed_dialogue.extend(sys_prompt)
            compressed_dialogue[1].update({'role': 'user'})
            compressed_dialogue.extend(dialogue[:split:])
        else:
            compressed_dialogue.extend(dialogue[:split:])
            compressed_dialogue.append({"role": "user", "content": last_diary})

        # When sending pictures to the summarizer, it does not work correctly, so we delete them
        compressed_dialogue = self.cleaning_images(compressed_dialogue)
        compressed_dialogue.append({"role": "user", "content": utils.current_time_info(self.config)})
        original_dialogue = dialogue[split::]
        try:
            args = [self.config.model,
                    compressed_dialogue,
                    self.config.tokens_per_answer,
                    self.config.temperature]
            answer, total_tokens = await asyncio.get_running_loop().run_in_executor(
                None, self.send_api_request, *args)
        except ApiRequestException:
            logging.error(f"Summarizing failed for chat {chat_name}!")
            return

        logging.info(f"Summarizing completed for chat {chat_name}, {total_tokens} tokens were used")
        result = sys_prompt
        result.append({"role": "assistant", "content": answer})
        result.extend(original_dialogue)
        result.append({"role": "user", "content": utils.current_time_info(self.config)})
        self.dialog_history = result
        try:
            self.sql_helper.dialog_update(self.context, json.dumps(self.dialog_history[1::]))
        except Exception as e:
            logging.error("Humanotronic was unable to save conversation information! Please check your database!")
            logging.error(f"{e}\n{traceback.format_exc()}")
