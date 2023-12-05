import time

import telebot
from telebot import types
import psycopg2
from psycopg2 import sql
from datetime import datetime, timedelta
import threading

def schedule_task():
    while True:
        time.sleep(10)
        check_reminders()

thread = threading.Thread(target=schedule_task)
thread.start()

TOKEN = '<>'

#vk
DB_CONNECTION_STRING = 'postgresql://user:<>@37.139.43.200:5432/PostgreSQL-9705'
conn = psycopg2.connect(DB_CONNECTION_STRING)

#ya
# conn = psycopg2.connect("""
#     host=rc1d-2e8mkpzj5xklapnw.mdb.yandexcloud.net
#     port=6432
#     sslmode=verify-full
#     dbname=telegramReminder
#     user=kubsu
#     password=<>
#     target_session_attrs=read-write
# """)
cursor = conn.cursor()

bot = telebot.TeleBot(TOKEN)

create_table_query = """
CREATE TABLE IF NOT EXISTS reminders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    text TEXT,
    remind_at TIMESTAMP
);
"""
cursor.execute(create_table_query)
conn.commit()


@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Создать напоминание"))

    bot.send_message(message.chat.id, "Привет! Я бот для напоминаний. Используйте /setreminder, чтобы установить напоминание.")


user_data = {}

@bot.message_handler(commands=['setreminder'])
def handle_set_reminder(message):
    msg = bot.send_message(message.chat.id, "Введите текст напоминания:")
    bot.register_next_step_handler(msg, process_text_input)

def process_text_input(message):
    try:
        user_id = message.from_user.id
        text = message.text

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Через 5 минут", callback_data="5"),
            types.InlineKeyboardButton("Через час", callback_data="60"),
        )
        markup.row(
            types.InlineKeyboardButton("Через день", callback_data="1440"),
            types.InlineKeyboardButton("Выберу вручную", callback_data="manual"),
        )

        msg = bot.send_message(message.chat.id, "Выберите время напоминания:", reply_markup=markup)

        # Сохраняем данные о пользователе и тексте напоминания в глобальной переменной
        user_data[msg.chat.id] = {"user_id": user_id, "text_input": text}

        bot.register_next_step_handler(msg, process_time_input)

    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка: {e}")

@bot.callback_query_handler(func=lambda call: True)
def process_time_input(call):
    try:
        user_id = user_data[call.message.chat.id]["user_id"]  # Используем глобальную переменную для получения параметров
        text = user_data[call.message.chat.id]["text_input"]

        callback_data = call.data

        if callback_data == "manual":
            msg = bot.send_message(call.message.chat.id, "Введите дату и время напоминания в формате 'ГГГГ-ММ-ДД ЧЧ:ММ':")
            bot.register_next_step_handler(msg, lambda msg: process_manual_time_input(msg, user_id, text))
        else:
            selected_time = int(callback_data)
            remind_at = datetime.now() + timedelta(minutes=selected_time)

            insert_query = sql.SQL("INSERT INTO reminders (user_id, text, remind_at) VALUES (%s, %s, %s);")
            cursor.execute(insert_query, (user_id, text, remind_at))
            conn.commit()

            bot.send_message(call.message.chat.id, f"Напоминание установлено: {text} в {remind_at}")

    except Exception as e:
        bot.send_message(call.message.chat.id, f"Произошла ошибка: {e}")

def process_manual_time_input(message, user_id, text):
    try:
        remind_at_str = message.text
        remind_at = datetime.strptime(remind_at_str, '%Y-%m-%d %H:%M')

        insert_query = sql.SQL("INSERT INTO reminders (user_id, text, remind_at) VALUES (%s, %s, %s);")
        cursor.execute(insert_query, (user_id, text, remind_at))
        conn.commit()

        bot.send_message(message.chat.id, f"Напоминание установлено: {text} в {remind_at}")

    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка: {e}")


def set_reminder(message):
    try:
        user_id = message.from_user.id
        text, remind_at_str = message.text.split(maxsplit=1)
        remind_at = datetime.strptime(remind_at_str, '%Y-%m-%d %H:%M')

        insert_query = sql.SQL("INSERT INTO reminders (user_id, text, remind_at) VALUES (%s, %s, %s);")
        cursor.execute(insert_query, (user_id, text, remind_at))
        conn.commit()

        bot.send_message(message.chat.id, f"Напоминание установлено: {text} в {remind_at}")
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка: {e}")


def check_reminders():
    now = datetime.now()

    select_query = sql.SQL("SELECT * FROM reminders WHERE remind_at <= %s;")
    cursor.execute(select_query, (now,))
    reminders = cursor.fetchall()

    for reminder in reminders:
        user_id, text, remind_at = reminder[1], reminder[2], reminder[3]
        bot.send_message(user_id, f"Напоминание: {text}. Время: {remind_at}")

    delete_query = sql.SQL("DELETE FROM reminders WHERE remind_at <= %s;")
    cursor.execute(delete_query, (now,))
    conn.commit()

if __name__ == "__main__":
    while True:
        try:
            check_reminders()
            bot.polling(none_stop=True, interval=1)
        except Exception as e:
            print(f"Произошла ошибка: {e}")
