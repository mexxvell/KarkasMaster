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

# Параметры для расчета
COSTS = {
    'materials': {
        'foundation': {
            'свайно-винтовой': 15000,
            'ленточный': 20000,
            'плита': 25000
        },
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
        'text': 'Укажите площадь дома (кв.м):',
        'type': 'number',
        'key': 'area'
    },
    {
        'text': 'Выберите этажность:',
        'options': ['Одноэтажный', 'Двухэтажный', 'С мансардой'],
        'key': 'floors'
    },
    {
        'text': 'Тип фундамента:',
        'options': ['Свайно-винтовой', 'Ленточный', 'Плита'],
        'key': 'foundation'
    },
    {
        'text': 'Тип кровли:',
        'options': ['Металлочерепица', 'Мягкая кровля', 'Фальцевая кровля'],
        'key': 'roof'
    },
    {
        'text': 'Тип утеплителя:',
        'options': ['Минеральная вата', 'Эковата', 'Пенополистирол'],
        'key': 'insulation'
    },
    {
        'text': 'Толщина утеплителя (мм):',
        'type': 'number',
        'key': 'insulation_thickness'
    },
    {
        'text': 'Внешняя отделка:',
        'options': ['Сайдинг', 'Вагонка', 'Штукатурка'],
        'key': 'exterior'
    },
    {
        'text': 'Внутренняя отделка:',
        'options': ['Вагонка', 'Гипсокартон', 'Другое'],
        'key': 'interior'
    },
    {
        'text': 'Количество стандартных окон:',
        'type': 'number',
        'key': 'windows_count'
    },
    {
        'text': 'Количество входных дверей:',
        'type': 'number',
        'key': 'entrance_doors'
    },
    {
        'text': 'Количество межкомнатных дверей:',
        'type': 'number',
        'key': 'inner_doors'
    },
    {
        'text': 'Наличие террасы/балкона (кв.м):',
        'type': 'number',
        'key': 'terrace_area'
    },
    {
        'text': 'Инженерные сети (выберите все что нужно):',
        'options': ['Электрика', 'Водоснабжение', 'Канализация', 'Отопление'],
        'multiple': True,
        'key': 'utilities'
    }
]

STEP = {item['key']: i for i, item in enumerate(QUESTIONS)}

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    user_data[user_id] = {}
    ask_next_question(user_id, 0)

def ask_next_question(user_id, step):
    if step >= len(QUESTIONS):
        calculate_and_send_result(user_id)
        return
    
    question = QUESTIONS[step]
    text = question['text']
    
    if 'options' in question:
        # Создаем клавиатуру
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add(*question['options'])
        bot.send_message(user_id, text, reply_markup=markup)
    else:
        # Числовой ввод
        bot.send_message(user_id, text)
    
    bot.register_next_step_handler_by_chat_id(user_id, process_answer, step=step)

def process_answer(message, step):
    user_id = message.chat.id
    question = QUESTIONS[step]
    answer = message.text.strip()
    
    if 'options' in question:
        if answer not in question['options']:
            bot.send_message(user_id, 'Выберите вариант из списка')
            ask_next_question(user_id, step)
            return
        
        user_data[user_id][question['key']] = answer
    else:
        try:
            value = float(answer)
            user_data[user_id][question['key']] = value
        except:
            bot.send_message(user_id, 'Введите число')
            ask_next_question(user_id, step)
            return
    
    next_step = step + 1
    ask_next_question(user_id, next_step)

def calculate_cost(data):
    total = 0
    
    # Расчет материалов
    materials = [
        data.get('foundation'),
        data.get('roof'),
        data.get('insulation'),
        data.get('exterior'),
        data.get('interior')
    ]
    
    total += data['area'] * COSTS['work']['base']
    
    # Дополнительные материалы
    total += COSTS['materials']['foundation'].get(data['foundation'], 0)
    total += data['roof_area'] * COSTS['materials']['roof'].get(data['roof'], 0)
    total += (data['insulation_thickness'] / 100) * data['area'] * COSTS['materials']['insulation'].get(data['insulation'], 0)
    total += data['area'] * COSTS['materials']['exterior'].get(data['exterior'], 0)
    total += data['area'] * COSTS['materials']['interior'].get(data['interior'], 0)
    
    # Окна и двери
    total += data['windows_count'] * COSTS['materials']['windows']
    total += data['entrance_doors'] * COSTS['materials']['doors']['входная']
    total += data['inner_doors'] * COSTS['materials']['doors']['межкомнатная']
    
    # Терраса
    total += data.get('terrace_area', 0) * COSTS['work']['terrace']
    
    # Инженерные сети
    utility_cost = 0
    if 'Электрика' in data['utilities']:
        utility_cost += 50000
    if 'Водоснабжение' in data['utilities']:
        utility_cost += 30000
    if 'Канализация' in data['utilities']:
        utility_cost += 25000
    if 'Отопление' in data['utilities']:
        utility_cost += 40000
    total += utility_cost
    
    return total

def calculate_and_send_result(user_id):
    data = user_data[user_id]
    try:
        total = calculate_cost(data)
        result = f"Общая стоимость: {total:.2f} руб."
        bot.send_message(user_id, result, reply_markup=types.ReplyKeyboardRemove())
    except Exception as e:
        bot.send_message(user_id, "Ошибка: проверьте корректность данных.")
    finally:
        del user_data[user_id]

# Flask setup
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

def start_bot():
    bot.remove_webhook()
    bot.delete_webhook()
    bot.infinity_polling(skip_pending=True)

if __name__ == '__main__':
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)