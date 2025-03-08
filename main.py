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

# Добавлены эмодзи для категорий
EMOJI = {
    'foundation': '🏛️',
    'roof': '葺',
    'insulation': '❄️',
    'exterior': 'Facade 🖌️',
    'interior': 'Interior 🛋️',
    'utilities': 'Utilities ⚡',
    'windows': 'Window 🪟',
    'doors': 'Door 🚪',
    'terrace': 'Terrace 🌳'
}

# Параметры для расчета с эмодзи
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
        'options': ['Свайно-винтовой', 'Ленточный', 'Плита'],
        'key': 'foundation'
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
        # Создаем клавиатуру с эмодзи
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add(*[f"{emoji} {opt}" for opt in question['options']])
        
        bot.send_message(user_id, text, reply_markup=markup)
    else:
        bot.send_message(user_id, text)
    
    bot.register_next_step_handler_by_chat_id(user_id, process_answer, step=step)

def process_answer(message, step):
    user_id = message.chat.id
    question = QUESTIONS[step]
    answer = message.text.strip()
    
    if 'options' in question:
        if 'multiple' in question and question['multiple']:
            # Обработка множественного выбора
            selected = []
            for option in question['options']:
                if option in answer:
                    selected.append(option)
            user_data[user_id][question['key']] = selected
        else:
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
    
    # Основные работы
    total += data['area'] * COSTS['work']['base']
    
    # Фундамент
    foundation_cost = COSTS['materials']['foundation'].get(data['foundation'], 0)
    total += foundation_cost
    
    # Кровля
    roof_area = data['area'] * 0.8  # примерная площадь кровли
    total += roof_area * COSTS['materials']['roof'].get(data['roof'], 0)
    
    # Утеплитель
    insulation_cost = (data['insulation_thickness'] / 100) * data['area'] * \
        COSTS['materials']['insulation'].get(data['insulation'], 0)
    total += insulation_cost
    
    # Внешняя отделка
    total += data['area'] * COSTS['materials']['exterior'].get(data['exterior'], 0)
    
    # Внутренняя отделка
    total += data['area'] * COSTS['materials']['interior'].get(data['interior'], 0)
    
    # Окна и двери
    windows = data.get('windows_count', 0) * COSTS['materials']['windows']
    doors = (data.get('entrance_doors', 0) * COSTS['materials']['doors']['входная']) + \
            (data.get('inner_doors', 0) * COSTS['materials']['doors']['межкомнатная'])
    total += windows + doors
    
    # Терраса
    terrace_area = data.get('terrace_area', 0)
    total += terrace_area * COSTS['work']['terrace']
    
    # Инженерные сети
    utility_cost = 0
    for utility in data.get('utilities', []):
        if utility == 'Электрика':
            utility_cost += 50000
        elif utility == 'Водоснабжение':
            utility_cost += 30000
        elif utility == 'Канализация':
            utility_cost += 25000
        elif utility == 'Отопление':
            utility_cost += 40000
    total += utility_cost
    
    return round(total, 2)

def calculate_and_send_result(user_id):
    data = user_data[user_id]
    try:
        total = calculate_cost(data)
        result = f"💰 Общая стоимость: {total} руб.\n\n" \
                 f"Расчет включает:\n" \
                 f"• Основные работы: {data['area'] * COSTS['work']['base']} руб.\n" \
                 f"• Фундамент: {COSTS['materials']['foundation'].get(data['foundation'], 0)} руб.\n" \
                 f"• Инженерные сети: {calculate_utility_cost(data)} руб.\n" \
                 f"• Дополнительные элементы: {calculate_additions(data)} руб."
        bot.send_message(user_id, result, reply_markup=types.ReplyKeyboardRemove())
    except Exception as e:
        bot.send_message(user_id, "Ошибка: проверьте корректность данных.")
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
    bot.infinity_polling(skip_pending=True)

if __name__ == '__main__':
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)