# from dotenv import load_dotenv
import logging
import random
import traceback

import openai

import prompts
import utils


class Dialog:

    def __init__(self, config, sql_helper, context):
        self.config = config
        self.sql_helper = sql_helper
        self.context = context
        try:
            dialog_history = sql_helper.dialog_get(context)
        except Exception as e:
            dialog_history = []
            logging.error("Humanotronic was unable to read conversation information! Please check your database!")
            logging.error(f"{e}\n{traceback.format_exc()}")
        if not dialog_history:
            self.dialog_history = [{"role": "system",
                                    "content": f"{prompts.start}\n{prompts.hard}\n{utils.current_time_info(config)}"}]
        else:
            self.dialog_history = dialog_history
        self.client = openai.OpenAI(api_key=config.api_key, base_url=config.base_url)

    def get_answer(self, message):
        chat_name = utils.username_parser(message) if message.chat.title is None else message.chat.title
        prompt = ""
        if random.randint(1, 50) == 1:
            prompt += f"{prompts.prefill} "
            logging.info(f"Prompt reminded for dialogue in chat {chat_name}")
        if random.randint(1, 30) == 1:
            prompt += f"{utils.current_time_info(self.config)} "
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
        self.dialog_history.extend([{"role": "user", "content": prompt},
                                    {"role": "assistant", "content": str(answer)}])
        try:
            self.sql_helper.dialog_update(self.context, self.dialog_history)
        except Exception as e:
            logging.error("Humanotronic was unable to save conversation information! Please check your database!")
            logging.error(f"{e}\n{traceback.print_exc()}")
        return answer
