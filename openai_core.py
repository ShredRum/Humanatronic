# from dotenv import load_dotenv
import logging
import random
import traceback

import openai

import prompts
import utils


class Dialog:

    def __init__(self, config):
        self.config = config
        self.dialog_history = [{"role": "system",
                                "content": f"{prompts.start}\n{prompts.hard}\n{utils.current_time_info()}"}]
        self.client = openai.OpenAI(api_key=config.api_key,
                                    base_url=config.base_url)

    def get_answer(self, message):
        chat_name = utils.username_parser(message) if message.chat is None else message.chat
        prompt = ""
        if random.randint(1, 50) == 1:
            prompt += f"{prompts.prefill}"
            logging.info(f"Promt reminded for dialogue in chat {chat_name}")
        if random.randint(1, 30) == 1:
            prompt += f"{utils.current_time_info()}"
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
