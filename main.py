import os
from flask import Flask
import telebot
from telebot import types
import logging
import threading

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv('API_TOKEN')
bot = telebot.TeleBot(API_TOKEN)

user_data = {}

QUESTIONS = [
    "Укажите площадь дома в квадратных метрах:",
    "Сколько этажей будет в доме?",
    "Выберите тип фундамента:\n1) Ленточный\n2) Свайный",
    "Выберите тип отделки:\n1) Эконом\n2) Стандарт\n3) Премиум",
    "Нужны ли дополнительные услуги? (септик, гараж):\n1) Нет\n2) Да (септик)\n3) Да (гараж)\n4) Да (оба)"
]

STEP = {
    'area': 0,
    'floors': 1,
    'foundation': 2,
    'finish': 3,
    'extras': 4
}

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    user_data[user_id] = {'step': 0}
    ask_next_question(user_id)

def ask_next_question(user_id):
    current_step = user_data[user_id]['step']
    if current_step < len(QUESTIONS):
        bot.send_message(user_id, QUESTIONS[current_step])
    else:
        calculate_and_send_result(user_id)

@bot.message_handler(func=lambda message: True)
def answer(message):
    user_id = message.chat.id
    current_step = user_data[user_id]['step']
    if current_step < len(QUESTIONS):
        key = list(STEP.keys())[current_step]
        user_data[user_id][key] = message.text
        user_data[user_id]['step'] += 1
        ask_next_question(user_id)
    else:
        bot.send_message(user_id, "Спасибо, ваш запрос обрабатывается...")

def calculate_and_send_result(user_id):
    data = user_data[user_id]
    try:
        area = float(data['area'])
        floors = int(data['floors'])
        foundation = data['foundation']
        finish = data['finish']
        extras = data['extras']

        base_cost = 1000000
        cost = base_cost

        # Расчет площади
        cost += area * 15000  # 15000 руб за 1 м²

        # Этажи
        cost += floors * 200000

        # Фундамент
        if foundation == '1':
            cost *= 1.10  # +10%
        elif foundation == '2':
            cost *= 1.20  # +20%

        # Отделка
        if finish == '1':
            cost *= 1.05  # +5%
        elif finish == '2':
            cost *= 1.10  # +10%
        elif finish == '3':
            cost *= 1.15  # +15%

        # Дополнительные услуги
        extra_cost = 0
        if extras == '2':
            extra_cost = 10000  # Септик
        elif extras == '3':
            extra_cost = 20000  # Гараж
        elif extras == '4':
            extra_cost = 30000  # Оба
        cost += extra_cost

        result = f"Общая стоимость: {cost:.2f} руб."
        bot.send_message(user_id, result)
    except Exception as e:
        bot.send_message(user_id, "Ошибка: проверьте корректность данных.")
        logging.error(f"Ошибка: {str(e)}")
    finally:
        del user_data[user_id]  # Сброс состояния

# Используем Flask для запуска на порту
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

def start_bot():
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)

if __name__ == '__main__':
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # Запускаем Flask для порта
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)