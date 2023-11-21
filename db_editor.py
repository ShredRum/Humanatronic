import json
import os.path
import sqlite3
import subprocess
import sys
import time
import traceback


# This is NOT PART of the main code. This is a separate utility!


class SQLWrapper:

    def __init__(self, dbname):
        self.dbname = dbname

    def __enter__(self):
        self.sqlite_connection = sqlite3.connect(self.dbname)
        self.cursor = self.sqlite_connection.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            self.sqlite_connection.commit()
        self.cursor.close()
        self.sqlite_connection.close()


class Editor:
    path = ""

    def __init__(self):
        while True:
            self.path = input("Please enter path to your database.db folder "
                              "(leave blank to search the current directory): ")
            if self.path:
                self.path = f"{self.path}/"
            self.dbname = f"{self.path}database.db"
            if os.path.isfile(self.dbname):
                break
            print("Incorrect DB path!")
        print("DB found!")
        self.worker_process()
        choice = ""
        while choice not in ("y", "n"):
            choice = input("Do you want to restart script? (y/n): ").lower()
            if choice == "n":
                sys.exit(0)

    def worker_process(self):
        incorrect = False
        while True:
            try:
                list_conversations = [x[0] for x in self.list_all_conversations()]
            except Exception as e:
                print(f"{e}/{traceback.format_exc()}")
                return
            if not incorrect:
                print("List of current conversations:")
                for con_num in range(len(list_conversations)):
                    print(f"{con_num + 1} - {list_conversations[con_num]}")
            incorrect = False

            conversation = input('Please enter number of your conversation or "exit" for return: ')
            if conversation == "exit":
                return
            try:
                conversation = int(conversation)
            except ValueError:
                print("Incorrect conversation")
                incorrect = True
                continue
            if not (0 < conversation <= len(list_conversations)):
                print("Incorrect conversation")
                incorrect = True
            else:
                self.conversation_worker(list_conversations[conversation - 1])

    def conversation_worker(self, conversation):
        incorrect = False
        commands = ['read', 'edit', 'copy', 'update', 'clear']
        while True:
            if not incorrect:
                print(f"\nConversation {conversation} selected")
                print("Available commands: " + ", ".join(commands))
            incorrect = False
            choice = input('Please enter your command or "exit" for return: ').lower()
            if choice == "exit":
                return
            if choice not in commands:
                print("Incorrect command")
                incorrect = True
            elif choice == 'read':
                self.conversation_read(conversation)
            elif choice == 'edit':
                self.conversation_edit(conversation)
            elif choice == 'copy':
                self.conversation_copy(conversation)
            elif choice == 'update':
                self.conversation_update(conversation)
            elif choice == 'clear':
                if self.conversation_clear(conversation):
                    return

    def conversation_read(self, conversation):
        print("*" * 10)
        try:
            conversation_text = json.loads(self.read_conversation(conversation)[0][0])
            for conversation_piece in conversation_text:
                print(f"{tuple(conversation_piece.values())[0]}: {tuple(conversation_piece.values())[1]}")
        except Exception as e:
            print(f"{e}/{traceback.format_exc()}")
            return
        finally:
            print("*" * 10)

    def conversation_copy(self, conversation):
        file_buffer = ""
        try:
            conversation_text = json.loads(self.read_conversation(conversation)[0][0])
            for conversation_piece in conversation_text:
                file_buffer += f"[{tuple(conversation_piece.values())[0]}: {tuple(conversation_piece.values())[1]}]\n"
        except Exception as e:
            print(f"{e}/{traceback.format_exc()}")
            return False
        file_path = f"{self.path}{conversation}.txt"
        if os.path.isfile(file_path):
            while True:
                choice = input("The file already exists! Do you want to overwrite it, "
                               "losing the data stored there? (Y/n): ").lower()
                if choice == "n":
                    return False
                elif choice in ("", "y"):
                    break
        try:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(file_buffer)
                print(f"\nSuccessfully written {file_path}")
                return True
        except Exception as e:
            print("Error writing information to txt file!")
            print(f"{e}/{traceback.format_exc()}")
            return False

    def conversation_edit(self, conversation):

        if not self.conversation_copy(conversation):
            return

        file_path = f"{self.path}{conversation}.txt"

        try:
            if sys.platform.startswith('darwin'):
                # для macOS
                subprocess.run(['open', file_path])
            elif sys.platform.startswith('win32'):
                # для Windows
                os.startfile(file_path)
            elif sys.platform.startswith('linux'):
                # для Linux
                subprocess.run(['xdg-open', file_path])
            else:
                raise OSError(f'Failed to open file: unknown operating system {sys.platform}')
        except Exception as e:
            print(f"Error opening file {file_path}. You can open it in a text editor yourself.")
            print(f"{e}/{traceback.format_exc()}")

    def conversation_update(self, conversation):
        file_path = f"{self.path}{conversation}.txt"
        if not os.path.isfile(file_path):
            print(f"File {file_path} not found! There is nothing to write to the database!")
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                file_buffer = file.read()
        except Exception as e:
            print(f"Error reading information from file {file_path}.")
            print(f"{e}/{traceback.format_exc()}")
            return

        nesting = 0
        text_buffer = []
        sym_buffer = ""
        for sym in file_buffer:
            if sym not in "[ \n" and nesting == 0:
                print("Error parsing text file! Invalid nesting!")
                return
            elif sym == "[":
                if nesting != 0:
                    sym_buffer += sym
                nesting += 1
            elif sym == "]":
                if nesting == 1:
                    text_buffer.append(sym_buffer)
                    sym_buffer = ""
                else:
                    sym_buffer += sym
                nesting -= 1
            elif sym in " \n" and nesting == 0:
                continue
            else:
                sym_buffer += sym

        if nesting != 0:
            print("Error parsing text file! Invalid nesting!")
            return
        result = []
        for str_buffer in text_buffer:
            split_str = str_buffer.split(sep=": ", maxsplit=1)
            if split_str[0] not in ('system', 'user', 'assistant'):
                print("Error parsing text file! Invalid role info!")
                print(f"String {str_buffer}")
                return
            result.append({'role': split_str[0], 'content': split_str[1]})

        print("File parsing completed successfully!")
        while True:
            choice = input("Do you want to overwrite context in the database? (Y/n): ").lower()
            if choice == "n":
                return
            elif choice in ("", "y"):
                break

        try:
            self.update_conversation(conversation, result)
        except Exception as e:
            print(f"{e}/{traceback.format_exc()}")
            return

        print("\nThe data in the database was overwritten successfully!")

    def conversation_clear(self, conversation):
        while True:
            choice = input("Do you want to clear context from this database? (Y/n): ").lower()
            if choice == "n":
                return False
            elif choice in ("", "y"):
                break

        try:
            self.clear_conversation(conversation)
        except Exception as e:
            print(f"{e}/{traceback.format_exc()}")
            return True

        print("\nThe data in the database was cleared successfully!")
        return True

    def list_all_conversations(self):
        with SQLWrapper(self.dbname) as sql_wrapper:
            sql_wrapper.cursor.execute("""SELECT context FROM chats""")
            records = sql_wrapper.cursor.fetchall()
            return records

    def read_conversation(self, context):
        with SQLWrapper(self.dbname) as sql_wrapper:
            sql_wrapper.cursor.execute("""SELECT dialog_text FROM chats WHERE context = ?""",
                                       (context,))
            records = sql_wrapper.cursor.fetchall()
            return records

    def clear_conversation(self, context):
        with SQLWrapper(self.dbname) as sql_wrapper:
            sql_wrapper.cursor.execute("""DELETE from chats where context = ?""", (context,))

    def update_conversation(self, context, dialog_text):
        with SQLWrapper(self.dbname) as sql_wrapper:
            sql_wrapper.cursor.execute("""SELECT * FROM chats WHERE context = ?""", (context,))
            record = sql_wrapper.cursor.fetchall()
            if not record:
                sql_wrapper.cursor.execute("""INSERT INTO chats VALUES (?,?,?);""",
                                           (context, json.dumps(dialog_text), int(time.time())))
            else:
                sql_wrapper.cursor.execute("""UPDATE chats SET dialog_text = ? WHERE context = ?""",
                                           (json.dumps(dialog_text), context))


if __name__ == "__main__":
    print("###HUMANOTRONIC DB EDITOR v0.3 LAUNCHED SUCCESSFULLY###")
    while True:
        Editor()
