import configparser
import logging
import os
import sys
import time
import traceback
from importlib import reload

import prompts


class ConfigData:

    path = ""
    my_id = ""

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
            level=logging.INFO,
            format='%(asctime)s %(levelname)s: %(message)s',
            datefmt="%d-%m-%Y %H:%M:%S")

        if not os.path.isfile(self.path + "config.ini"):
            print("Config file isn't found! Trying to remake!")
            self.remake_conf()

        config = configparser.ConfigParser()
        while True:
            try:
                config.read(self.path + "config.ini")
                self.token = config["ChatGPT"]["token"]
                self.api_key = config["ChatGPT"]["api-key"]
                break
            except Exception as e:
                logging.error((str(e)))
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
            self.base_url = config["ChatGPT"]["base-url"]
            if self.base_url == "":
                raise KeyError
        except (KeyError, TypeError):
            self.base_url = None

        try:
            self.temperature = float(config["ChatGPT"]["temperature"])
            if self.base_url == "":
                raise KeyError
        except (KeyError, TypeError, ValueError):
            self.temperature = None

    def remake_conf(self):
        token, api_key = "", ""
        while token == "":
            token = input("Please, write your bot token: ")
        while api_key == "":
            api_key = input("Please, write your OpenAI developer key: ")
        config = configparser.ConfigParser()
        config.add_section("ChatGPT")
        config.set("ChatGPT", "token", token)
        config.set("ChatGPT", "api-key", api_key)
        config.set("ChatGPT", "base-url", "")
        config.set("ChatGPT", "temperature", "0.5")
        try:
            config.write(open(self.path + "config.ini", "w"))
            print("New config file was created successful")
        except IOError:
            print("ERR: Bot cannot write new config file and will close")
            logging.error(traceback.format_exc())
            sys.exit(1)


def check_names(message, bot_id):
    """
    The bot will only respond if called by name (if it's public chat)
    :param message:
    :param bot_id:
    :return:
    """
    if message.text is None:
        return False
    if message.chat.id == message.from_user.id:
        return True
    if message.reply_to_message:
        if message.reply_to_message.from_user.id == bot_id:
            return True
    msg_txt = message.text.lower()
    for name in prompts.names:
        if name.lower() in msg_txt:
            return True
    return False


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


def current_time_info():
    current_time = time.strftime("%Hч., %Mм. и %Sс.", time.gmtime(int(time.time())))
    return f"Current time is: {current_time}"
