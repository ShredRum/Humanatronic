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
                model=self.config.model,
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
        # print(f"{self.num_tokens_from_messages()} prompt tokens counted by num_tokens_from_messages().")
        # print(f'{completion["usage"]["prompt_tokens"]} prompt tokens counted by the OpenAI API.')
        total_tokens = completion.usage.total_tokens
        logging.info(f'{total_tokens} tokens counted by the OpenAI API in chat {chat_name}.')
        if total_tokens >= self.config.summarizer_limit:
            self.summarizer()
        try:
            self.sql_helper.dialog_update(self.context, self.dialog_history)
        except Exception as e:
            logging.error("Humanotronic was unable to save conversation information! Please check your database!")
            logging.error(f"{e}\n{traceback.print_exc()}")
        return answer

    def summarizer(self):
        pass

    # def num_tokens_from_messages(self, model=None):
    #     """Official example from the OpenAI website.
    #     Return the number of tokens used by a list of messages."""
    #
    #     model = model or self.config.model
    #     print(model)
    #     try:
    #         encoding = tiktoken.encoding_for_model(model)
    #     except KeyError:
    #         print("Warning: model not found. Using cl100k_base encoding.")
    #         encoding = tiktoken.get_encoding("cl100k_base")
    #     if model in {
    #         "gpt-3.5-turbo-0613",
    #         "gpt-3.5-turbo-16k-0613",
    #         "gpt-4-0314",
    #         "gpt-4-32k-0314",
    #         "gpt-4-0613",
    #         "gpt-4-32k-0613",
    #     }:
    #         tokens_per_message = 3
    #         tokens_per_name = 1
    #     elif model == "gpt-3.5-turbo-0301":
    #         tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
    #         tokens_per_name = -1  # if there's a name, the role is omitted
    #     elif "gpt-3.5-turbo" in model:
    #         print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
    #         return self.num_tokens_from_messages("gpt-3.5-turbo-0613")
    #     elif "gpt-4" in model:
    #         print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
    #         return self.num_tokens_from_messages("gpt-4-0613")
    #     else:
    #         raise NotImplementedError(
    #             f"""num_tokens_from_messages() is not implemented for model {model}.
    #             See https://github.com/openai/openai-python/blob/main/chatml.md
    #             for information on how messages are converted to tokens."""
    #         )
    #     num_tokens = 0
    #     for message in self.dialog_history:
    #         num_tokens += tokens_per_message
    #         for key, value in message.items():
    #             num_tokens += len(encoding.encode(value))
    #             if key == "name":
    #                 num_tokens += tokens_per_name
    #     num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    #     return num_tokens
