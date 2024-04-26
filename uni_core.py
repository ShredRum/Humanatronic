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

        def get_client(vendor, api_key, base_url):
            if vendor == 'anthropic':
                return anthropic.Anthropic(api_key=api_key, base_url=base_url)
            return openai.OpenAI(api_key=api_key, base_url=base_url)

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
            if dialog_data[0][2]:
                self.memory_dump = json.loads(dialog_data[0][2])
            start_time = (f"{utils.current_time_info(config, dialog_data[0][3]).split(maxsplit=2)[2]} - "
                          f"it's time to start our conversation")
            self.dialog_history = json.loads(dialog_data[0][1])
            # Pictures saved in the database may cause problems when working without Vision
            if not config.vision:
                self.dialog_history = self.cleaning_images(self.dialog_history)
        self.system = f"{config.prompts.start}\n{config.prompts.hard}\n{start_time}"
        self.client = get_client(config.model_vendor, config.api_key, config.base_url)
        self.memory_client = get_client(config.memory_model_vendor, config.memory_api_key, config.memory_base_url)

    @staticmethod
    def send_api_request_openai(client, queue, model, messages,
                                max_tokens=1000,
                                system=None,
                                temperature=None,
                                stream=False,
                                attempts=3):

        if system:
            system = [{"role": "system", "content": system}]
            system.extend(messages)
            messages = system

        queue.acquire()
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
                queue.release()
                return answer, total_tokens
            except Exception as e:
                logging.error(f"{e}\n{traceback.format_exc()}")

        queue.release()
        raise ApiRequestException

    @staticmethod
    def send_api_request_claude(client, queue, model, messages,
                                max_tokens=1000,
                                system=None,
                                temperature=None,
                                stream=False,
                                attempts=3,
                                prefill=None):

        if prefill:
            messages.append({"role": "assistant", "content": prefill})

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if system:
            kwargs.update({'system': system})

        queue.acquire()
        for _ in range(attempts):
            if not stream:
                try:
                    completion = client.messages.create(**kwargs)  # ДА НЕ БОМБИТ У МЕНЯ!!!!
                    if "error" in completion.id:
                        logging.error(completion.content[0].text)
                        raise ApiRequestException
                    text = completion.content[0].text
                    while text[0] in (" ", "\n"):  # Sometimes Anthropic spits out spaces and line breaks
                        text = text[1::]  # at the beginning of text
                    queue.release()
                    return text, completion.usage.input_tokens + completion.usage.output_tokens
                except Exception as e:
                    logging.error(f"{e}\n{traceback.format_exc()}")
                    continue

            try:
                tokens_count = 0
                text = ""
                with client.messages.stream(**kwargs) as stream:
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
                queue.release()
                return text, tokens_count
            except Exception as e:
                logging.error(f"{e}\n{traceback.format_exc()}")
                continue

        queue.release()
        raise ApiRequestException

    def send_api_request(self, mode, *args):
        if mode not in ('personality', 'memory'):
            logging.error('The mode of use should be "personality" or "memory"')
            raise ApiRequestException
        vendor = self.config.memory_model_vendor if mode == 'memory' else self.config.model_vendor
        if mode == 'memory':
            client = self.memory_client
            queue = self.config.memory_api_queue
        else:
            client = self.client
            queue = self.config.api_queue
        if vendor == 'anthropic':
            return self.send_api_request_claude(client, queue, *args)
        return self.send_api_request_openai(client, queue, *args)

    def get_image_context(self, photo_base64, prompt):
        if self.config.model_vendor == 'anthropic':
            return [
                {"type": "image", "source":
                    {"type": "base64", "media_type": photo_base64['mime'], "data": photo_base64['data']}},
                {"type": "text", "text": prompt}]
        else:
            return [
                {"type": "image_url", "image_url":
                    {"url": f"data:{photo_base64['mime']};base64,{photo_base64['data']}"}},
                {"type": "text", "text": prompt}]

    async def get_answer(self, message, reply_msg, photo_base64):
        username = utils.username_parser(message)
        chat_name = f"{username}'s private messages" if message.chat.title is None else f'chat {message.chat.title}'
        if reply_msg:
            if self.dialog_history[-1]['content'] == reply_msg:
                reply_msg = ""
            else:
                reply_msg = f'In response to the message "{reply_msg}"\n'

        msg_txt = message.text or message.caption
        if msg_txt is None:
            msg_txt = "I sent a photo"

        main_text = f"Message from person {username} from {chat_name}: {msg_txt}"

        dialog_buffer = self.dialog_history.copy()
        summarizer_used = False
        if self.dialogue_locker.locked():
            logging.info(f"Adding messages is blocked for {chat_name} due to the work of the summarizer.")
            summarizer_used = True
            await self.dialogue_locker.acquire()
            self.dialogue_locker.release()

        memory_result = ""
        if self.memory_dump:
            request_to_memory = f'{username}: {msg_txt}'
            if reply_msg:
                request_to_memory = f'{reply_msg}{request_to_memory}'
            try:
                args = ['memory',
                        self.config.memory_model,
                        [{"role": "user",
                          "content": f'Answer everything you remember from the request "{request_to_memory}"'}],
                        self.config.memory_tokens_per_answer,
                        f'{self.config.prompts.memory_read}{self.memory_dump}',
                        self.config.memory_temperature,
                        self.config.memory_stream_mode,
                        self.config.memory_attempts]
                answer, total_tokens = await asyncio.get_running_loop().run_in_executor(
                    None, self.send_api_request, *args)
                memory_result = f"Memory: {answer}\n"
                logging.info(f"Memory usage spent {total_tokens} tokens")
            except ApiRequestException:
                logging.error("The character's memory could not process the request")

        current_time = ""
        if any([random.randint(1, 30) == 1,  # Time is reminded of Humanotronic with a probability of 1/30
                int(time.time()) - self.last_time >= 3600,
                "врем" in msg_txt.lower(),
                "час" in msg_txt.lower()
                ]):
            current_time = f"{utils.current_time_info(self.config)}\n"
            logging.info(f"Time updated for dialogue in {chat_name}")
        prompt = f'{current_time}{memory_result}{reply_msg}{main_text}'
        if photo_base64:
            dialog_buffer.append({"role": "user", "content": self.get_image_context(photo_base64, prompt)})
        else:
            dialog_buffer.append({"role": "user", "content": prompt})
        if self.dialogue_locker.locked():
            logging.info(f"Adding messages is blocked for {chat_name} due to the work of the summarizer.")
            summarizer_used = True
            await self.dialogue_locker.acquire()
            self.dialogue_locker.release()
        try:
            args = ['personality',
                    self.config.model,
                    dialog_buffer,
                    self.config.tokens_per_answer, self.system,
                    self.config.temperature,
                    self.config.stream_mode,
                    self.config.attempts]
            answer, total_tokens = await asyncio.get_running_loop().run_in_executor(
                None, self.send_api_request, *args)
        except ApiRequestException:
            return random.choice(self.config.prompts.errors)

        logging.info(f'{total_tokens} tokens counted by the OpenAI API in {chat_name}.')
        if self.dialogue_locker.locked():
            logging.info(f"Adding messages is blocked for {chat_name} due to the work of the summarizer.")
            summarizer_used = True
            await self.dialogue_locker.acquire()
            self.dialogue_locker.release()
        prompt = f'{current_time}{reply_msg}{main_text}'
        if photo_base64:
            self.dialog_history.extend([{"role": "user", "content": self.get_image_context(photo_base64, prompt)},
                                        {"role": "assistant", "content": answer}])
        else:
            self.dialog_history.extend([{"role": "user", "content": prompt},
                                        {"role": "assistant", "content": answer}])
        if self.config.vision and len(self.dialog_history) > 10:
            self.dialog_history = self.cleaning_images(self.dialog_history, last_only=True)
        if total_tokens >= self.config.summarizer_limit and not summarizer_used:
            logging.info(f"The token limit {self.config.summarizer_limit} for "
                         f"the {chat_name} has been exceeded. Using a lazy summarizer")
            async with self.dialogue_locker:
                await self.summarizer(chat_name)
        try:
            self.sql_helper.dialog_update(self.context, json.dumps(self.dialog_history))
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
        split = self.summarizer_index()

        compressed_dialogue = self.dialog_history[:split:]
        compressed_dialogue.append({"role": "user",
                                    "content": f'{summarizer_text}\n{utils.current_time_info(self.config)}'})

        # When sending pictures to the summarizer, it does not work correctly, so we delete them
        compressed_dialogue = self.cleaning_images(compressed_dialogue)
        try:
            args = ['personality',
                    self.config.model,
                    compressed_dialogue,
                    self.config.tokens_per_answer, None,
                    self.config.temperature,
                    self.config.stream_mode,
                    self.config.attempts]
            answer, total_tokens = await asyncio.get_running_loop().run_in_executor(
                None, self.send_api_request, *args)
            logging.info(f"{total_tokens} tokens were used to compress the dialogue")

            if self.memory_dump:
                args = ['memory',
                        self.config.memory_model,
                        [{"role": "user",
                          "content": f'Update information on the following memory block:\n{answer}'}],
                        self.config.memory_tokens_per_answer,
                        f'{self.config.prompts.memory_write}{self.memory_dump}',
                        self.config.memory_temperature,
                        self.config.memory_stream_mode,
                        self.config.memory_attempts]
                self.memory_dump, total_tokens = await asyncio.get_running_loop().run_in_executor(
                    None, self.send_api_request, *args)
                logging.info(f"{total_tokens} tokens used to update the memory dump")
            else:
                self.memory_dump = answer
        except ApiRequestException:
            logging.error(f"Summarizing failed for {chat_name}!")
            return

        logging.info(f"Summarizing completed for {chat_name}, "
                     f"{total_tokens} tokens were used")
        self.dialog_history = self.dialog_history[split::]
        try:
            self.sql_helper.memory_update(self.context, json.dumps(self.memory_dump))
        except Exception as e:
            logging.error("Humanotronic was unable to save conversation information! Please check your database!")
            logging.error(f"{e}\n{traceback.format_exc()}")
