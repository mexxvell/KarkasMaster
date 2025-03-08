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

EMOJI = {
    'foundation': '🏛️',
    'roof': '🏛️',
    'insulation': '❄️',
    'exterior': '🎨',
    'interior': '🛋️',
    'utilities': '⚡',
    'windows': '🪟',
    'doors': '🚪',
    'terrace': '🌳'
}

COSTS = {
    'materials': {
        'foundation': 15000,
        'roof': {
            'Металлочерепица': 1200,
            'Мягкая кровля': 800,
            'Фальцевая кровля': 1800,
            'Пропустить': 0
        },
        'insulation': {
            'Минеральная вата': 500,
            'Эковата': 400,
            'Пенополистирол': 600,
            'Пропустить': 0
        },
        'exterior': {
            'Сайдинг': 300,
            'Вагонка': 400,
            'Штукатурка': 250,
            'Пропустить': 0
        },
        'interior': {
            'Вагонка': 350,
            'Гипсокартон': 300,
            'Другое': 0,
            'Пропустить': 0
        },
        'windows': 5000,
        'doors': {
            'входная': 15000,
            'межкомнатная': 8000
        }
    },
    'work': {
        'base': 8000,
        'terrace': 3000,
        'basement': 1500
    }
}

QUESTIONS = [
    {
        'text': '🏡 Площадь дома (кв.м):',
        'options': ['100 м²', '120 м²', '150 м²', 'Пропустить'],
        'key': 'area'
    },
    {
        'text': 'Этажность 🏠:',
        'options': ['Одноэтажный', 'Двухэтажный', 'С мансардой', 'Пропустить'],
        'key': 'floors'
    },
    {
        'text': 'Фундамент 🏗️:',
        'key': 'foundation',
        'auto_value': 'свайно-винтовой'
    },
    {
        'text': 'Кровля:',
        'options': ['Металлочерепица', 'Мягкая кровля', 'Фальцевая кровля', 'Пропустить'],
        'key': 'roof'
    },
    {
        'text': 'Утеплитель ❄️:',
        'options': ['Минеральная вата', 'Эковата', 'Пенополистирол', 'Пропустить'],
        'key': 'insulation'
    },
    {
        'text': 'Толщина утеплителя (мм) 📏:',
        'type': 'number',
        'key': 'insulation_thickness'
    },
    {
        'text': 'Внешняя отделка 🎨:',
        'options': ['Сайдинг', 'Вагонка', 'Штукатурка', 'Пропустить'],
        'key': 'exterior'
    },
    {
        'text': 'Внутренняя отделка 🛋️:',
        'options': ['Вагонка', 'Гипсокартон', 'Другое', 'Пропустить'],
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
        'options': ['Электрика', 'Водоснабжение', 'Канализация', 'Отопление', 'Пропустить'],
        'multiple': True,
        'key': 'utilities'
    }
]

TOTAL_STEPS = len(QUESTIONS)

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if user_id in user_data:
        del user_data[user_id]
    user_data[user_id] = {'step': 0}
    ask_next_question(user_id)

def ask_next_question(user_id):
    current_step = user_data[user_id].get('step', 0)
    if current_step >= TOTAL_STEPS:
        calculate_and_send_result(user_id)
        return
    
    question = QUESTIONS[current_step]
    text = question['text']
    progress = f"Шаг {current_step + 1} из {TOTAL_STEPS}\n\n{text}"
    
    if 'options' in question:
        emoji_char = EMOJI.get(question['key'], '')
        options = [opt for opt in question['options'] if opt != 'Пропустить']
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        
        for opt in options:
            markup.add(f"{emoji_char} {opt}")
        markup.add("Пропустить")
    else:
        markup = types.ReplyKeyboardRemove()
    
    bot.send_message(user_id, progress, reply_markup=markup)
    
    if 'auto_value' in question:
        user_data[user_id][question['key']] = question['auto_value']
        user_data[user_id]['step'] = current_step + 1
        ask_next_question(user_id)
    else:
        bot.register_next_step_handler_by_chat_id(user_id, process_answer, current_step=current_step)

def process_answer(message, current_step):
    user_id = message.chat.id
    question = QUESTIONS[current_step]
    answer = message.text.strip()
    
    if 'options' in question:
        emoji_char = EMOJI.get(question['key'], '')
        clean_answer = answer.replace(f"{emoji_char} ", "").strip()
        options = question['options']
        
        if clean_answer not in options and clean_answer != 'Пропустить':
            bot.send_message(user_id, 'Выберите вариант из списка')
            ask_next_question(user_id)
            return
        
        if clean_answer == 'Пропустить':
            user_data[user_id][question['key']] = None
        else:
            if question['key'] == 'area':
                try:
                    user_data[user_id][question['key']] = int(clean_answer.split()[0])
                except:
                    bot.send_message(user_id, 'Некорректный формат. Введите число.')
                    ask_next_question(user_id)
                    return
            else:
                user_data[user_id][question['key']] = clean_answer
    else:
        try:
            value = float(answer)
            user_data[user_id][question['key']] = value
        except:
            bot.send_message(user_id, 'Введите число')
            ask_next_question(user_id)
            return
    
    user_data[user_id]['step'] = current_step + 1
    ask_next_question(user_id)

def calculate_cost(data):
    total = 0
    total += data.get('area', 100) * COSTS['work']['base']
    total += COSTS['materials']['foundation']
    
    # Кровля
    roof_type = data.get('roof')
    if roof_type and roof_type != 'Пропустить':
        roof_area = data.get('area', 100) * 0.8
        total += roof_area * COSTS['materials']['roof'].get(roof_type, 0)
    
    # Утеплитель
    insulation_type = data.get('insulation')
    if insulation_type and insulation_type != 'Пропустить':
        insulation_cost = (data.get('insulation_thickness', 150) / 100) * data.get('area', 100) * \
            COSTS['materials']['insulation'].get(insulation_type, 0)
        total += insulation_cost
    
    # Внешняя отделка
    exterior_type = data.get('exterior')
    if exterior_type and exterior_type != 'Пропустить':
        total += data.get('area', 100) * COSTS['materials']['exterior'].get(exterior_type, 0)
    
    # Внутренняя отделка
    interior_type = data.get('interior')
    if interior_type and interior_type != 'Пропустить':
        total += data.get('area', 100) * COSTS['materials']['interior'].get(interior_type, 0)
    
    # Окна и двери
    windows = data.get('windows_count', 0) * COSTS['materials']['windows']
    doors = (data.get('entrance_doors', 0) * 15000) + (data.get('inner_doors', 0) * 8000)
    total += windows + doors
    
    # Терраса
    terrace_area = data.get('terrace_area', 0)
    total += terrace_area * COSTS['work']['terrace']
    
    # Инженерные сети
    utility_cost = calculate_utility_cost(data)
    total += utility_cost
    
    return round(total, 2)

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

def calculate_and_send_result(user_id):
    data = user_data[user_id]
    try:
        total = calculate_cost(data)
        result = f"💰 Общая стоимость: {total} руб.\n\n" \
                 f"Расчет включает:\n" \
                 f"• Основные работы: {data.get('area', 100) * COSTS['work']['base']} руб.\n" \
                 f"• Фундамент: {COSTS['materials']['foundation']} руб.\n" \
                 f"• Кровля: {data.get('roof', 'Не выбрано')} - {COSTS['materials']['roof'].get(data.get('roof'), 0) * data.get('area', 100) * 0.8} руб.\n" \
                 f"• Инженерные сети: {calculate_utility_cost(data)} руб."
        bot.send_message(user_id, result, reply_markup=types.ReplyKeyboardRemove())
    except Exception as e:
        bot.send_message(user_id, f"Ошибка: {str(e)}")
    finally:
        if user_id in user_data:
            del user_data[user_id]

app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!"

def start_bot():
    bot.remove_webhook()
    bot.polling(none_stop=True)

if __name__ == '__main__':
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)