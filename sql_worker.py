import json
import sqlite3


def open_close_db(function):
    def wrapper(self, *args, **kwargs):
        sqlite_connection = sqlite3.connect(self.dbname)
        cursor = sqlite_connection.cursor()
        data = function(self, cursor, *args, **kwargs)
        sqlite_connection.commit()
        cursor.close()
        sqlite_connection.close()
        return data
    return wrapper


class SqlWorker:
    dbname = ""

    def __init__(self, dbname):
        self.dbname = dbname

        sqlite_connection = sqlite3.connect(dbname)
        cursor = sqlite_connection.cursor()
        cursor.execute("""CREATE TABLE if not exists chats (
                                    context TEXT NOT NULL PRIMARY KEY,
                                    dialog_text TEXT NOT NULL);""")
        sqlite_connection.commit()
        cursor.close()
        sqlite_connection.close()

    @open_close_db
    def dialog_update(self, cursor, context, dialog_text):
        cursor.execute("""SELECT * FROM chats WHERE context = ?""", (context,))
        record = cursor.fetchall()
        if not record:
            cursor.execute("""INSERT INTO chats VALUES (?,?);""", (context, json.dumps(dialog_text)))
        else:
            cursor.execute("""UPDATE chats SET dialog_text = ? WHERE context = ?""", (json.dumps(dialog_text), context))

    @open_close_db
    def dialog_get(self, cursor, context):
        cursor.execute("""SELECT * FROM chats WHERE meow = ?""", (context,))
        dialog = cursor.fetchall()
        if dialog:
            dialog = json.loads(dialog[0][1])
        return dialog
