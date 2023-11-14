# from dotenv import load_dotenv
import logging
import random
import time
import traceback

import openai

import prompts
import utils


class Dialog:

    def __init__(self, config):
        self.config = config
        self.dialog_history = [{"role": "system",
                                "content": f"{prompts.start}\n{prompts.hard}\n{utils.current_time_info(config)}"}]
        self.client = openai.OpenAI(api_key=config.api_key,
                                    base_url=config.base_url)
        self.flood_wait = 0

    def get_answer(self, message, config):
        chat_name = utils.username_parser(message) if message.chat.title is None else message.chat.title
        prompt = ""
        if random.randint(1, 50) == 1:
            prompt += f"{prompts.prefill}"
            logging.info(f"Prompt reminded for dialogue in chat {chat_name}")
        if random.randint(1, 30) == 1:
            prompt += f"{utils.current_time_info(config)}"
            logging.info(f"Time updated for dialogue in chat {chat_name}")
        prompt += f"{utils.username_parser(message)}: {message.text}"
        dialog_buffer = self.dialog_history.copy()
        dialog_buffer.append({"role": "user", "content": prompt})
        try:
            completion = self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=dialog_buffer,
                temperature=self.config.temperature,
                max_tokens=4096,
                stream=False)
        except Exception as e:
            logging.error(f"{e}\n{traceback.format_exc()}")
            return random.choice(prompts.errors)

        answer = completion.choices[0].message.content
        self.dialog_history.extend([{"role": "user", "content": f"{utils.username_parser(message)}: {message.text}"},
                                    {"role": "assistant", "content": str(answer)}])
        return answer

    def is_flooded(self, message):
        if int(time.time()) - self.flood_wait <= 5:
            chat_name = utils.username_parser(message) if message.chat.title is None else message.chat.title
            logging.info(f"Rejected request from chat {chat_name} by floodwait. Retry after 5 seconds.")
            return True
        self.flood_wait = int(time.time())
        return False
