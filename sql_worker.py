import sqlite3
import time


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
        cursor.execute(f"""CREATE TABLE if not exists chats (
                                    context TEXT NOT NULL PRIMARY KEY,
                                    dialog_text TEXT NOT NULL,
                                    first_use INTEGER NOT NULL DEFAULT {int(time.time())});""")
        # Backward compatibility
        try:
            cursor.execute(f"ALTER TABLE chats ADD COLUMN first_use INTEGER NOT NULL DEFAULT {int(time.time())}")
        except sqlite3.OperationalError:
            pass
        sqlite_connection.commit()
        cursor.close()
        sqlite_connection.close()

    @open_close_db
    def dialog_update(self, cursor, context, dialog_text):
        cursor.execute("""SELECT * FROM chats WHERE context = ?""", (context,))
        record = cursor.fetchall()
        if not record:
            cursor.execute("""INSERT INTO chats VALUES (?,?,?);""",
                           (context, dialog_text, int(time.time())))
        else:
            cursor.execute("""UPDATE chats SET dialog_text = ? WHERE context = ?""", (dialog_text, context))

    @open_close_db
    def dialog_get(self, cursor, context):
        cursor.execute("""SELECT * FROM chats WHERE context = ?""", (context,))
        dialog = cursor.fetchall()
        return dialog
