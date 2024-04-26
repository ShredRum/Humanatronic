# from dotenv import load_dotenv
import json
import logging
import random
import asyncio
import time
import traceback

import anthropic
import openai

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
        self.memory_dump = None

        def get_client(vendor):
            if vendor == 'anthropic':
                return anthropic.Anthropic(api_key=config.api_key, base_url=config.base_url)
            return openai.OpenAI(api_key=config.api_key, base_url=config.base_url)

        try:
            dialog_data = sql_helper.dialog_get(context)
        except Exception as e:
            dialog_data = []
            logging.error("Humanotronic was unable to read conversation information! Please check your database!")
            logging.error(f"{e}\n{traceback.format_exc()}")
        if not dialog_data:
            start_time = f"{utils.current_time_info(config).split(maxsplit=2)[2]} - it's time to start our conversation"
            self.dialog_history = []
        else:
            self.memory_dump = json.loads(dialog_data[0][2])
            start_time = (f"{utils.current_time_info(config, dialog_data[0][2]).split(maxsplit=2)[2]} - "
                          f"it's time to start our conversation")
            dialog_history = json.loads(dialog_data[0][3])
            # Pictures saved in the database may cause problems when working without Vision
            if not config.vision:
                self.dialog_history = self.cleaning_images(dialog_history)
        self.system = f"{config.prompts.start}\n{config.prompts.hard}\n{start_time}"
        self.client = get_client(config.model_vendor)
        self.memory_client = get_client(config.memory_model_vendor)

    @staticmethod
    def send_api_request_openai(client, model, messages,
                                max_tokens=1000,
                                system=None,
                                temperature=None,
                                stream=False,
                                attempts=3):
        if system:
            system = [{"role": "system", "content": system}]
            messages = system.extend(messages)

        for _ in range(attempts):
            try:
                completion = client.chat.completions.create(
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

    def send_api_request_claude(self, client, model, messages,
                                max_tokens=1000,
                                system=None,
                                temperature=None,
                                stream=False,
                                attempts=3):

        msg = []
        if system:
            msg = [{'role': 'user', "content": "Dialogue is started"}, {'role': 'assistant', "content": system}]
        msg.extend(messages)
        messages = msg
        messages.append({"role": "assistant",
                         "content": self.config.prompts.prefill})

        self.config.api_queue.acquire()
        for _ in range(attempts):
            if not stream:
                try:
                    completion = client.messages.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=False,
                    )
                    if "error" in completion.id:
                        logging.error(completion.content[0].text)
                        raise ApiRequestException
                    text = completion.content[0].text
                    while text[0] in (" ", "\n"):  # Sometimes Anthropic spits out spaces and line breaks
                        text = text[1::]  # at the beginning of text
                    self.config.api_queue.release()
                    return text, completion.usage.input_tokens + completion.usage.output_tokens
                except Exception as e:
                    logging.error(f"{e}\n{traceback.format_exc()}")
                    continue

            try:
                tokens_count = 0
                text = ""
                with client.messages.stream(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                ) as stream:
                    empty_stream = True
                    error = False
                    for event in stream:
                        empty_stream = False
                        name = event.__class__.__name__
                        if name == "MessageStartEvent":
                            if event.message.usage:
                                tokens_count += event.message.usage.input_tokens
                            else:
                                error = True
                        elif name == "ContentBlockDeltaEvent":
                            text += event.delta.text
                        elif name == "MessageDeltaEvent":
                            tokens_count += event.usage.output_tokens
                        elif name == "Error":
                            logging.error(event.error.message)
                            raise ApiRequestException
                    if empty_stream:
                        raise ApiRequestException("Empty stream object, please check your proxy connection!")
                    if error:
                        raise ApiRequestException(text)
                    if not text:
                        raise ApiRequestException("Empty text result, please check your prefill!")
                while text[0] in (" ", "\n"):
                    text = text[1::]
                self.config.api_queue.release()
                return text, tokens_count
            except Exception as e:
                logging.error(f"{e}\n{traceback.format_exc()}")
                continue

        self.config.api_queue.release()
        raise ApiRequestException

    def send_api_request(self, mode, args):
        if mode not in ('personality', 'memory'):
            raise ApiRequestException('The mode of use should be "personality" or "memory"')
        vendor = self.config.memory_model_vendor if mode == 'memory' else self.config.model_vendor
        client = self.memory_client if mode == 'memory' else self.client
        if vendor == 'anthropic':
            return self.send_api_request_claude(client, *args)
        return self.send_api_request_openai(client, *args)

    async def get_answer(self, message, reply_msg, photo_base64):
        chat_name = utils.username_parser(message) if message.chat.title is None else message.chat.title
        if reply_msg:
            if self.dialog_history[-1]['content'] == reply_msg:
                reply_msg = None

        msg_txt = message.text or message.caption
        if msg_txt is None:
            msg_txt = "I sent a photo"

        prompt = f"{utils.username_parser(message)}: {msg_txt}"
        dialog_buffer = self.dialog_history.copy()
        if reply_msg:
            content = reply_msg['content']  # python 3.11 and older
            prompt = f'In response to the message "{content}":\n\n{prompt}'
        if any([random.randint(1, 30) == 1,  # Time is reminded of Humanotronic with a probability of 1/30
                int(time.time()) - self.last_time >= 3600,
                "врем" in msg_txt.lower(),
                "час" in msg_txt.lower()
                ]):
            prompt += f"\n\n{utils.current_time_info(self.config)} "
            logging.info(f"Time updated for dialogue in chat {chat_name}")
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
                None, self.send_api_request, args)
        except ApiRequestException:
            return random.choice(self.config.prompts.errors)

        logging.info(f'{total_tokens} tokens counted by the OpenAI API in chat {chat_name}.')
        if self.dialogue_locker.locked():
            logging.info(f"Adding messages is blocked for chat {chat_name} due to the work of the summarizer.")
            summarizer_used = True
            await self.dialogue_locker.acquire()
            self.dialogue_locker.release()
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

    def summarizer_index(self, threshold=None):
        text_len = 0
        for index in range(len(self.dialog_history)):
            if isinstance(self.dialog_history[index]['content'], list):
                for i in self.dialog_history[index]['content']:
                    if i['type'] == 'text':
                        text_len += len(i['text'])
            else:
                text_len += len(self.dialog_history[index]['content'])

            if threshold:
                if text_len >= threshold and self.dialog_history[index]['role'] == "user":
                    return index

        return self.summarizer_index(text_len * 0.7)

    # noinspection PyTypeChecker
    async def summarizer(self, chat_name):

        summarizer_text = self.config.prompts.summarizer.format(self.config.memory_dump_size)
        split = self.summarizer_index(self.dialog_history)

        compressed_dialogue = self.dialog_history[:split:]
        compressed_dialogue.append({"role": "user", "content": f'{summarizer_text}\n{self.system}'
                                                               f'\n{utils.current_time_info(self.config)}'})

        # When sending pictures to the summarizer, it does not work correctly, so we delete them
        compressed_dialogue = self.cleaning_images(compressed_dialogue)
        try:
            args = [self.config.model,
                    compressed_dialogue,
                    self.config.tokens_per_answer, None,
                    self.config.temperature,
                    self.config.stream_mode,
                    self.config.attempts]
            answer, total_tokens = await asyncio.get_running_loop().run_in_executor(
                None, self.send_api_request, *args)
        except ApiRequestException:
            logging.error(f"Summarizing failed for chat {chat_name}!")
            return

        logging.info(f"Summarizing completed for chat {chat_name}, "
                     f"{total_tokens} tokens were used")
        self.dialog_history = self.dialog_history[split::]
        try:
            self.sql_helper.dialog_update(self.context, json.dumps(self.dialog_history))
        except Exception as e:
            logging.error("Humanotronic was unable to save conversation information! Please check your database!")
            logging.error(f"{e}\n{traceback.format_exc()}")
