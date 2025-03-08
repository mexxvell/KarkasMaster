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
    'foundation': '🏗️',
    'roof': '🏛️',
    'insulation': '❄️',
    'exterior': '🎨',
    'interior': '🛋️',
    'utilities': '⚡',
    'windows': '🪟',
    'doors': '🚪',
    'terrace': '🌳',
    'region': '📍'
}

COSTS = {
    'materials': {
        'foundation': {
            'Свайно-винтовой': 15000,
            'Ленточный': 20000,
            'Плитный': 25000
        },
        'roof': {
            'Металлочерепица': 1200,
            'Мягкая кровля': 800,
            'Фальцевая кровля': 1800,
            'Пропустить': 0
        },
        'insulation': {
            'Минеральная вата': {'price': 500, 'min_thickness': 150},
            'Эковата': {'price': 400, 'min_thickness': 200},
            'Пенополистирол': {'price': 600, 'min_thickness': 100},
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
        'base': {
            'price': 8000,
            'floor_multiplier': {
                'Одноэтажный': 1.0,
                'Двухэтажный': 0.9,
                'С мансардой': 1.2
            }
        },
        'terrace': 3000,
        'basement': 1500
    }
}

REGIONAL_COEFFICIENTS = {
    'Москва': 1.5,
    'СПб': 1.3,
    'Другой': 1.0
}

QUESTIONS = [
    {
        'text': '📍 Регион строительства:',
        'options': ['Москва', 'СПб', 'Другой'],
        'key': 'region'
    },
    {
        'text': '🏡 Площадь дома (кв.м):',
        'options': ['100 м²', '120 м²', '150 м²', 'Пропустить'],
        'key': 'area',
        'max': 1000
    },
    {
        'text': 'Этажность 🏠:',
        'options': ['Одноэтажный', 'Двухэтажный', 'С мансардой', 'Пропустить'],
        'key': 'floors'
    },
    {
        'text': 'Фундамент 🏗️:',
        'options': ['Свайно-винтовой', 'Ленточный', 'Плитный', 'Пропустить'],
        'key': 'foundation'
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
        'key': 'insulation_thickness',
        'min': 50,
        'max': 500
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
        'key': 'windows_count',
        'max': 50
    },
    {
        'text': 'Входные двери 🚪:',
        'type': 'number',
        'key': 'entrance_doors',
        'max': 10
    },
    {
        'text': 'Межкомнатные двери 🚪:',
        'type': 'number',
        'key': 'inner_doors',
        'max': 30
    },
    {
        'text': 'Терраса/балкон (кв.м) 🌳:',
        'type': 'number',
        'key': 'terrace_area',
        'max': 200
    },
    {
        'text': 'Инженерные сети ⚡ (выберите все):',
        'options': ['Электрика', 'Водоснабжение', 'Канализация', 'Отопление', 'Пропустить'],
        'multiple': True,
        'key': 'utilities'
    }
]

TOTAL_STEPS = len(QUESTIONS)

def calculate_roof_area(data):
    area = data.get('area', 100)
    floors = data.get('floors', 'Одноэтажный')
    
    if floors == 'Двухэтажный':
        return area * 0.6
    elif floors == 'С мансардой':
        return area * 1.1
    return area * 0.8

def apply_discounts(total, data):
    selected_items = sum(1 for k in data if data.get(k) and k not in ['area', 'floors', 'region'])
    if selected_items > 5:
        total *= 0.9
    if data.get('area', 0) > 200:
        total *= 0.95
    return total

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    user_data[user_id] = {'step': 0}
    ask_next_question(user_id)

def ask_next_question(user_id):
    current_step = user_data[user_id].get('step', 0)
    if current_step >= TOTAL_STEPS:
        calculate_and_send_result(user_id)
        return
    
    question = QUESTIONS[current_step]
    text = question['text']
    progress = f"Шаг {current_step + 1} из {TOTAL_STEPS}\n{text}"
    
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
    bot.register_next_step_handler_by_chat_id(user_id, process_answer, current_step=current_step)

def process_answer(message, current_step):
    user_id = message.chat.id
    question = QUESTIONS[current_step]
    answer = message.text.strip()
    
    try:
        if 'options' in question:
            emoji_char = EMOJI.get(question['key'], '')
            clean_answer = answer.replace(f"{emoji_char} ", "").strip()
            
            if clean_answer not in question['options'] and clean_answer != 'Пропустить':
                raise ValueError("Неверный вариант")
            
            user_data[user_id][question['key']] = clean_answer if clean_answer != 'Пропустить' else None
            
        elif question.get('type') == 'number':
            value = float(answer)
            
            if 'min' in question and value < question['min']:
                raise ValueError(f"Минимальное значение: {question['min']}")
                
            if 'max' in question and value > question['max']:
                raise ValueError(f"Максимальное значение: {question['max']}")
                
            user_data[user_id][question['key']] = value
            
        elif question.get('multiple'):
            user_data[user_id][question['key']] = answer.split(', ')
            
    except Exception as e:
        error_msg = f"Ошибка: {str(e)}\nПожалуйста, введите корректные данные."
        bot.send_message(user_id, error_msg)
        return ask_next_question(user_id)
    
    user_data[user_id]['step'] += 1
    ask_next_question(user_id)

def calculate_cost(data):
    total = 0
    details = []
    
    # Основные работы
    floor_type = data.get('floors', 'Одноэтажный')
    base_price = COSTS['work']['base']['price']
    multiplier = COSTS['work']['base']['floor_multiplier'].get(floor_type, 1.0)
    area = data.get('area', 100)
    base_cost = area * base_price * multiplier
    total += base_cost
    details.append(f"Основные работы ({floor_type}): {base_cost:,.0f} руб.")
    
    # Фундамент
    foundation_type = data.get('foundation')
    if foundation_type and foundation_type != 'Пропустить':
        foundation_cost = COSTS['materials']['foundation'].get(foundation_type, 0)
        total += foundation_cost
        details.append(f"Фундамент ({foundation_type}): {foundation_cost:,.0f} руб.")
    
    # Кровля
    roof_type = data.get('roof')
    if roof_type and roof_type != 'Пропустить':
        roof_area = calculate_roof_area(data)
        roof_cost = roof_area * COSTS['materials']['roof'].get(roof_type, 0)
        total += roof_cost
        details.append(f"Кровля ({roof_type}): {roof_cost:,.0f} руб.")
    
    # Утеплитель
    insulation_type = data.get('insulation')
    if insulation_type and insulation_type != 'Пропустить':
        min_thickness = COSTS['materials']['insulation'][insulation_type]['min_thickness']
        actual_thickness = max(data.get('insulation_thickness', 0), min_thickness)
        insulation_cost = (actual_thickness / 100) * area * COSTS['materials']['insulation'][insulation_type]['price']
        total += insulation_cost
        details.append(f"Утеплитель ({insulation_type}): {insulation_cost:,.0f} руб.")
    
    # Внешняя отделка
    exterior_type = data.get('exterior')
    if exterior_type and exterior_type != 'Пропустить':
        exterior_cost = area * COSTS['materials']['exterior'].get(exterior_type, 0)
        total += exterior_cost
        details.append(f"Внешняя отделка ({exterior_type}): {exterior_cost:,.0f} руб.")
    
    # Внутренняя отделка
    interior_type = data.get('interior')
    if interior_type and interior_type != 'Пропустить':
        interior_cost = area * COSTS['materials']['interior'].get(interior_type, 0)
        total += interior_cost
        details.append(f"Внутренняя отделка ({interior_type}): {interior_cost:,.0f} руб.")
    
    # Окна и двери
    windows_cost = data.get('windows_count', 0) * COSTS['materials']['windows']
    entrance_doors_cost = data.get('entrance_doors', 0) * 15000
    inner_doors_cost = data.get('inner_doors', 0) * 8000
    doors_windows_total = windows_cost + entrance_doors_cost + inner_doors_cost
    total += doors_windows_total
    details.append(f"Окна/двери: {doors_windows_total:,.0f} руб.")
    
    # Терраса
    terrace_area = data.get('terrace_area', 0)
    terrace_cost = terrace_area * COSTS['work']['terrace']
    total += terrace_cost
    if terrace_area > 0:
        details.append(f"Терраса: {terrace_cost:,.0f} руб.")
    
    # Инженерные сети
    utility_cost = sum(
        50000 if 'Электрика' in data.get('utilities', []) else 0,
        30000 if 'Водоснабжение' in data.get('utilities', []) else 0,
        25000 if 'Канализация' in data.get('utilities', []) else 0,
        40000 if 'Отопление' in data.get('utilities', []) else 0
    )
    total += utility_cost
    if utility_cost > 0:
        details.append(f"Инженерные сети: {utility_cost:,.0f} руб.")
    
    # Региональный коэффициент
    region = data.get('region', 'Другой')
    regional_coeff = REGIONAL_COEFFICIENTS.get(region, 1.0)
    total *= regional_coeff
    details.append(f"Региональный коэффициент ({region}): x{regional_coeff}")
    
    # Применение скидок
    total_before_discount = total
    total = apply_discounts(total, data)
    if total < total_before_discount:
        details.append(f"Скидка: {total_before_discount - total:,.0f} руб.")
    
    return round(total, 2), details

def calculate_and_send_result(user_id):
    try:
        data = user_data[user_id]
        total, details = calculate_cost(data)
        
        result = [
            "📊 Детализированный расчет стоимости:",
            *details,
            "────────────────────────",
            f"💰 Итоговая стоимость: {total:,.0f} руб."
        ]
        
        bot.send_message(user_id, "\n".join(result), parse_mode='Markdown')
        
    except Exception as e:
        bot.send_message(user_id, f"⚠️ Ошибка расчета: {str(e)}")
    finally:
        if user_id in user_data:
            del user_data[user_id]

app = Flask(__name__)

@app.route('/')
def home():
    return "Construction Bot работает!"

def start_bot():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))