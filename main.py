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
    {
        'text': "Выберите тип строения:",
        'options': ['Дом', 'Баня', 'Навес', 'Сарай']
    },
    {
        'text': "Укажите площадь в кв.м:",
        'options': ['50', '100', '150', '200', 'Другое']
    },
    {
        'text': "Сколько этажей?",
        'options': ['1', '2', '3']
    },
    {
        'text': "Выберите тип фундамента:",
        'options': ['Ленточный', 'Свайный']
    },
    {
        'text': "Выберите тип отделки:",
        'options': ['Эконом', 'Стандарт', 'Премиум']
    },
    {
        'text': "Нужны ли дополнительные услуги?",
        'options': ['Нет', 'Септик', 'Гараж', 'Оба']
    }
]

STEP = {
    'building_type': 0,
    'area': 1,
    'floors': 2,
    'foundation': 3,
    'finish': 4,
    'extras': 5
}

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    user_data[user_id] = {'step': 0}
    ask_next_question(user_id)

def ask_next_question(user_id):
    current_step = user_data[user_id]['step']
    if current_step < len(QUESTIONS):
        question = QUESTIONS[current_step]
        text = question['text']
        options = question['options']
        
        # Создаем клавиатуру
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add(*options)
        
        bot.send_message(user_id, text, reply_markup=markup)
    else:
        calculate_and_send_result(user_id)

@bot.message_handler(func=lambda message: True)
def answer(message):
    user_id = message.chat.id
    current_step = user_data[user_id]['step']
    
    if current_step < len(QUESTIONS):
        question = QUESTIONS[current_step]
        options = question['options']
        user_answer = message.text
        
        # Проверяем, что ответ в списке вариантов
        if user_answer not in options:
            bot.send_message(user_id, "Пожалуйста, выберите вариант из списка.")
            return
        
        # Сохраняем ответ
        key = list(STEP.keys())[current_step]
        user_data[user_id][key] = user_answer
        
        # Переходим к следующему шагу
        user_data[user_id]['step'] += 1
        ask_next_question(user_id)
    else:
        bot.send_message(user_id, "Спасибо, ваш запрос обрабатывается...")

def calculate_and_send_result(user_id):
    data = user_data[user_id]
    try:
        area = float(data['area']) if data['area'] != 'Другое' else float(input("Укажите площадь: "))
        floors = int(data['floors'])
        foundation = data['foundation']
        finish = data['finish']
        extras = data['extras']
        building_type = data['building_type']

        # Базовая стоимость зависит от типа строения
        base_cost = {
            'Дом': 1000000,
            'Баня': 800000,
            'Навес': 200000,
            'Сарай': 300000
        }[building_type]

        cost = base_cost

        # Расчет площади
        cost += area * 15000  # 15000 руб за 1 м²

        # Этажи
        cost += floors * 200000

        # Фундамент
        if foundation == 'Ленточный':
            cost *= 1.10  # +10%
        elif foundation == 'Свайный':
            cost *= 1.20  # +20%

        # Отделка
        if finish == 'Эконом':
            cost *= 1.05  # +5%
        elif finish == 'Стандарт':
            cost *= 1.10  # +10%
        elif finish == 'Премиум':
            cost *= 1.15  # +15%

        # Дополнительные услуги
        extra_cost = 0
        if extras == 'Септик':
            extra_cost = 10000
        elif extras == 'Гараж':
            extra_cost = 20000
        elif extras == 'Оба':
            extra_cost = 30000
        cost += extra_cost

        result = f"Общая стоимость: {cost:.2f} руб."
        bot.send_message(user_id, result, reply_markup=types.ReplyKeyboardRemove())
    except Exception as e:
        bot.send_message(user_id, "Ошибка: проверьте корректность данных.")
        logging.error(f"Ошибка: {str(e)}")
    finally:
        del user_data[user_id]  # Сброс состояния

# Используем Flask для порта
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

def start_bot():
    # Удаляем предыдущий вебхук и обновления
    bot.remove_webhook()
    bot.delete_webhook()
    
    # Запускаем polling с очисткой
    bot.infinity_polling(skip_pending=True)

if __name__ == '__main__':
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)