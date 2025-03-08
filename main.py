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

# Словарь эмодзи для категорий
EMOJI = {
    'foundation': '🏛️',
    'roof': '葺',
    'insulation': '❄️',
    'exterior': '🖌️',
    'interior': '箦️',
    'utilities': '⚡',
    'windows': '🪟',
    'doors': '🚪',
    'terrace': '🌳'
}

# Параметры для расчета
COSTS = {
    'materials': {
        'foundation': 15000,  # Теперь фиксировано
        'roof': {
            'металлочерепица': 1200,
            'мягкая кровля': 800,
            'фальцевая кровля': 1800
        },
        'insulation': {
            'минеральная вата': 500,
            'эковата': 400,
            'пенополистирол': 600
        },
        'exterior': {
            'сайдинг': 300,
            'вагонка': 400,
            'штукатурка': 250
        },
        'interior': {
            'вагонка': 350,
            'гипсокартон': 300,
            'другое': 0
        },
        'windows': 5000,  # за стандартное окно
        'doors': {
            'входная': 15000,
            'межкомнатная': 8000
        }
    },
    'work': {
        'base': 8000,  # базовая стоимость работ за кв.м
        'terrace': 3000,  # за кв.м террасы
        'basement': 1500  # за кв.м подвала
    }
}

QUESTIONS = [
    {
        'text': '🏡 Площадь дома (кв.м):',
        'type': 'number',
        'key': 'area'
    },
    {
        'text': 'этажность 🏠:',
        'options': ['Одноэтажный', 'Двухэтажный', 'С мансардой'],
        'key': 'floors'
    },
    {
        'text': 'Фундамент 🏗️:',
        'key': 'foundation',  # Автоматически выбираем свайно-винтовой
        'auto_value': 'свайно-винтовой'
    },
    {
        'text': 'Кровля 🏛️:',
        'options': ['Металлочерепица', 'Мягкая кровля', 'Фальцевая кровля'],
        'key': 'roof'
    },
    {
        'text': 'Утеплитель ❄️:',
        'options': ['Минеральная вата', 'Эковата', 'Пенополистирол'],
        'key': 'insulation'
    },
    {
        'text': 'Толщина утеплителя (мм) 📏:',
        'type': 'number',
        'key': 'insulation_thickness'
    },
    {
        'text': 'Внешняя отделка 🎨:',
        'options': ['Сайдинг', 'Вагонка', 'Штукатурка'],
        'key': 'exterior'
    },
    {
        'text': 'Внутренняя отделка 🛋️:',
        'options': ['Вагонка', 'Гипсокартон', 'Другое'],
        'key': 'interior'
    },
    {
        'text': 'Количество окон 🪟:',
        'type': 'number',
        'key': 'windows_count'
    },
    {
        'text': 'Входные двери 🚪:',
        'type': 'number',
        'key': 'entrance_doors'
    },
    {
        'text': 'Межкомнатные двери 🚪:',
        'type': 'number',
        'key': 'inner_doors'
    },
    {
        'text': 'Терраса/балкон (кв.м) 🌳:',
        'type': 'number',
        'key': 'terrace_area'
    },
    {
        'text': 'Инженерные сети ⚡ (выберите все):',
        'options': ['Электрика', 'Водоснабжение', 'Канализация', 'Отопление'],
        'multiple': True,
        'key': 'utilities'
    }
]

TOTAL_STEPS = len(QUESTIONS)

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    user_data[user_id] = {'step': 0}
    ask_next_question(user_id)

def ask_next_question(user_id):
    current_step = user_data[user_id]['step']
    if current_step >= TOTAL_STEPS:
        calculate_and_send_result(user_id)
        return
    
    question = QUESTIONS[current_step]
    text = question['text']
    
    # Добавляем прогресс-бар
    progress = f"Шаг {current_step+1} из {TOTAL_STEPS}\n\n{text}"
    
    if 'options' in question:
        emoji_char = EMOJI.get(question['key'], '')
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add(*[f"{emoji_char} {opt}" for opt in question['options']])
    else:
        markup = types.ReplyKeyboardRemove()
    
    bot.send_message(user_id, progress, reply_markup=markup)
    
    # Автоматически переход, если вопрос без выбора
    if 'auto_value' in question:
        user_data[user_id][question['key']] = question['auto_value']
        user_data[user_id]['step'] += 1
        ask_next_question(user_id)
    else:
        bot.register_next_step_handler_by_chat_id(user_id, process_answer)

def process_answer(message, step):
    user_id = message.chat.id
    question = QUESTIONS[step]
    answer = message.text.strip()
    
    if 'options' in question:
        if 'multiple' in question and question['multiple']:
            selected = []
            for option in question['options']:
                if option in answer:
                    selected.append(option)
            user_data[user_id][question['key']] = selected
        else:
            if answer not in question['options']:
                bot.send_message(user_id, 'Выберите вариант из списка')
                ask_next_question(user_id)
                return
            user_data[user_id][question['key']] = answer
    else:
        try:
            value = float(answer)
            user_data[user_id][question['key']] = value
        except:
            bot.send_message(user_id, 'Введите число')
            ask_next_question(user_id)
            return
    
    user_data[user_id]['step'] += 1
    ask_next_question(user_id)

def calculate_cost(data):
    total = 0
    # Основные работы
    total += data['area'] * COSTS['work']['base']
    # Фундамент (автоматически свайно-винтовой)
    total += COSTS['materials']['foundation']
    # Далее остальные расчеты...
    # (оставляю только важные части для примера)
    return round(total, 2)

def calculate_and_send_result(user_id):
    data = user_data[user_id]
    try:
        total = calculate_cost(data)
        result = f"💰 Общая стоимость: {total} руб."
        bot.send_message(user_id, result, reply_markup=types.ReplyKeyboardRemove())
    except:
        bot.send_message(user_id, "Ошибка: проверьте данные")
    finally:
        del user_data[user_id]


def calculate_utility_cost(data):
    utilities = data.get('utilities', [])
    total = 0
    for utility in utilities:
        if utility == 'Электрика':
            total += 50000
        elif utility == 'Водоснабжение':
            total += 30000
        elif utility == 'Канализация':
            total += 25000
        elif utility == 'Отопление':
            total += 40000
    return total

def calculate_additions(data):
    additions = 0
    additions += data.get('windows_count', 0) * 5000  # окна
    additions += data.get('entrance_doors', 0) * 15000  # входные двери
    additions += data.get('inner_doors', 0) * 8000  # межкомнатные двери
    additions += data.get('terrace_area', 0) * 3000  # терраса
    return additions

# Flask setup
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

def start_bot():
    bot.remove_webhook()
    bot.delete_webhook()
    # Добавляем паузу для стабильности
    import time
    time.sleep(3)
    try:
        bot.infinity_polling(
            skip_pending=True,
            timeout=60  # Увеличиваем таймаут
        )
    except Exception as e:
        logging.error(f"Error during bot polling: {e}")

if __name__ == '__main__':
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)