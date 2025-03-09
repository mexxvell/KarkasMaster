import os
import logging
import threading
from datetime import datetime
from flask import Flask
import telebot
from telebot import types
import requests

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv('API_TOKEN')
bot = telebot.TeleBot(API_TOKEN)

user_data = {}
analytics_data = {
    'started_calculations': 0,
    'completed_calculations': 0,
    'abandoned_steps': {}
}

EMOJI = {
    'foundation': '🏗️',
    'roof': '🏛️',
    'insulation': '❄️',
    'exterior': '🎨',
    'interior': '🛋️',
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
        'key': 'region',
        'row_width': 2
    },
    {
        'text': '🏡 Площадь дома (кв.м):',
        'options': ['100', '120', '150', 'Пропустить'],
        'key': 'area',
        'max': 1000,
        'row_width': 2
    },
    {
        'text': 'Этажность 🏠:',
        'options': ['Одноэтажный', 'Двухэтажный', 'С мансардой', 'Пропустить'],
        'key': 'floors',
        'row_width': 2
    },
    {
        'text': 'Фундамент 🏗️:',
        'options': ['Свайно-винтовой', 'Ленточный', 'Плитный', 'Пропустить'],
        'key': 'foundation',
        'row_width': 2
    },
    {
        'text': 'Кровля:',
        'options': ['Металлочерепица', 'Мягкая кровля', 'Фальцевая кровля', 'Пропустить'],
        'key': 'roof',
        'row_width': 2
    },
    {
        'text': 'Утеплитель ❄️:',
        'options': ['Минеральная вата', 'Эковата', 'Пенополистирол', 'Пропустить'],
        'key': 'insulation',
        'row_width': 2
    },
    {
        'text': 'Толщина утеплителя (мм) 📏:',
        'options': ['100', '150', '200'],
        'key': 'insulation_thickness',
        'row_width': 3
    },
    {
        'text': 'Внешняя отделка 🎨:',
        'options': ['Сайдинг', 'Вагонка', 'Штукатурка', 'Пропустить'],
        'key': 'exterior',
        'row_width': 2
    },
    {
        'text': 'Внутренняя отделка 🛋️:',
        'options': ['Вагонка', 'Гипсокартон', 'Другое', 'Пропустить'],
        'key': 'interior',
        'row_width': 2
    },
    {
        'text': 'Количество окон 🪟:',
        'options': ['1', '2', '3', '4', '5', '6'],
        'key': 'windows_count',
        'row_width': 3
    },
    {
        'text': 'Входные двери 🚪:',
        'options': ['1', '2', '3', '4', '5', '6'],
        'key': 'entrance_doors',
        'row_width': 3
    },
    {
        'text': 'Межкомнатные двери 🚪:',
        'options': ['1', '2', '3', '4', '5', '6'],
        'key': 'inner_doors',
        'row_width': 3
    },
    {
        'text': 'Терраса/балкон (кв.м) 🌳:',
        'options': ['0', '10', '20', '30', 'Пропустить'],
        'key': 'terrace_area',
        'row_width': 2
    }
]

TOTAL_STEPS = len(QUESTIONS)

def get_user_data(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            'projects': {},
            'current_project': None,
            'last_active': datetime.now(),
            'guide_progress': 0,
            'reminders': []
        }
    return user_data[user_id]

GUIDES = {
    'foundation': {
        'title': '🏗️ Фундамент',
        'content': '''🔨 <b>Типы фундаментов:</b>
1. Свайно-винтовой - идеален для неровного рельефа
2. Ленточный - для тяжелых конструкций
3. Плитный - максимальная устойчивость

💡 <b>Советы:</b>
✅ Экономить: на декоративной отделке
❌ Не экономить: на гидроизоляции
🕒 Срок службы: 50-100 лет''',
        'image': 'https://example.com/foundation.jpg'
    },
    'walls': {
        'title': '🧱 Каркас и стены',
        'content': '''🏠 <b>Технологии строительства:</b>
1. Каркасная - быстрая сборка
2. Двойной каркас - повышенная прочность
3. Перекрестное утепление - для холодных регионов

💡 <b>Рекомендации:</b>
✅ Экономить: на внутренней обшивке
❌ Не экономить: на качестве OSB-плит
🌡️ Теплоизоляция: минимум 200 мм утеплителя''',
        'image': 'https://example.com/walls.jpg'
    },
    'roof': {
        'title': '🏛️ Кровельная система',
        'content': '''🌧️ <b>Конструктивные элементы:</b>
1. Стропильная система - основа кровли
2. Обрешетка - тип зависит от покрытия
3. Утепление - обязательно для жилых помещений

💡 <b>Важно:</b>
✅ Экономить: на декоративных коньках
❌ Не экономить: на ветрозащитной мембране
📐 Уклон: от 28° для металлочерепицы''',
        'image': 'https://example.com/roof.jpg'
    },
    'insulation': {
        'title': '❄️ Теплоизоляция',
        'content': '''🧊 <b>Схемы утепления:</b>
1. Базальтовые плиты - негорючий материал
2. Эковата - бесшовное покрытие
3. ППУ-напыление - высокая стоимость

💡 <b>Правила монтажа:</b>
✅ Экономить: на толщине в гараже
❌ Не экономить: на пароизоляционной пленке
📏 Толщина: 150-200 мм для жилых помещений''',
        'image': 'https://example.com/insulation.jpg'
    }
}

def create_keyboard(items, row_width, skip_button=False):
    markup = types.ReplyKeyboardMarkup(row_width=row_width, resize_keyboard=True)
    filtered = [item for item in items if item != 'Пропустить']
    
    # Добавляем кнопки порциями
    for i in range(0, len(filtered), row_width):
        markup.add(*filtered[i:i+row_width])
    
    # Добавляем кнопки управления
    if skip_button:
        markup.add('Пропустить')
    markup.add('❌ Отменить расчет')
    return markup

def schedule_reminder(user_id, project_name):
    def send_reminder():
        bot.send_message(user_id, f"🔔 Напоминание о проекте '{project_name}'. Продолжить расчет? Используйте /menu")
    
    timer = threading.Timer(3600, send_reminder)
    user = get_user_data(user_id)
    user['reminders'].append(timer)
    timer.start()

def track_event(event_type, step=None):
    if event_type == 'start':
        analytics_data['started_calculations'] += 1
    elif event_type == 'complete':
        analytics_data['completed_calculations'] += 1
    elif event_type == 'abandon':
        analytics_data['abandoned_steps'][step] = analytics_data['abandoned_steps'].get(step, 0) + 1

def create_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["🏠 Новый проект", "📚 Строительный гайд", 
              "📊 История расчетов", "⚙ Настройки"]
    markup.add(*buttons)
    return markup

@bot.message_handler(commands=['start', 'menu'])
def show_main_menu(message):
    user_id = message.chat.id
    user = get_user_data(user_id)
    user['last_active'] = datetime.now()
    bot.send_message(user_id, "🏠 Главное меню:", reply_markup=create_main_menu())

@bot.message_handler(func=lambda m: m.text == "🏠 Новый проект")
def start_new_project(message):
    user_id = message.chat.id
    user = get_user_data(user_id)
    project_id = f"project_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    user['projects'][project_id] = {
        'name': f"Проект от {datetime.now().strftime('%d.%m.%Y')}",
        'data': {},
        'created_at': datetime.now(),
        'completed': False
    }
    user['current_project'] = project_id
    track_event('start')
    ask_next_question(user_id)

def ask_next_question(user_id):
    user = get_user_data(user_id)
    project = user['projects'][user['current_project']]
    current_step = project['data'].get('step', 0)
    
    if current_step >= TOTAL_STEPS:
        calculate_and_send_result(user_id)
        return
    
    question = QUESTIONS[current_step]
    text = question['text']
    row_width = question.get('row_width', 2)
    skip_button = 'Пропустить' in question['options']
    
    progress = f"Шаг {current_step + 1} из {TOTAL_STEPS}\n{text}"
    markup = create_keyboard(question['options'], row_width, skip_button)
    
    bot.send_message(user_id, progress, reply_markup=markup)
    bot.register_next_step_handler_by_chat_id(user_id, process_answer, current_step=current_step)

def process_answer(message, current_step):
    user_id = message.chat.id
    user = get_user_data(user_id)
    project = user['projects'][user['current_project']]
    question = QUESTIONS[current_step]
    
    try:
        answer = message.text.strip()
        
        if answer == "❌ Отменить расчет":
            del user['projects'][user['current_project']]
            user['current_project'] = None
            show_main_menu(message)
            return

        # Обработка числовых значений
        if answer == 'Пропустить':
            project['data'][question['key']] = None
        elif question['key'] in ['windows_count', 'entrance_doors', 'inner_doors']:
            project['data'][question['key']] = int(answer)
        elif question['key'] in ['area', 'terrace_area', 'insulation_thickness']:
            project['data'][question['key']] = float(answer)
        else:
            project['data'][question['key']] = answer
        
        project['data']['step'] = current_step + 1
        user['last_active'] = datetime.now()
        
    except Exception as e:
        bot.send_message(user_id, f"❌ Ошибка: {str(e)}")
        track_event('abandon', current_step)
        return ask_next_question(user_id)
    
    ask_next_question(user_id)

def calculate_roof_area(data):
    area = float(data.get('area', 100))
    floors = data.get('floors', 'Одноэтажный')
    
    if floors == 'Двухэтажный':
        return area * 0.6
    elif floors == 'С мансардой':
        return area * 1.1
    return area * 0.8

def calculate_cost(data):
    total = 0
    details = []
    
    try:
        # Основные работы
        floor_type = data.get('floors', 'Одноэтажный')
        base_price = COSTS['work']['base']['price']
        multiplier = COSTS['work']['base']['floor_multiplier'][floor_type]
        area = float(data.get('area', 100))
        base_cost = area * base_price * multiplier
        total += base_cost
        details.append(f"Основные работы ({floor_type}): {base_cost:,.0f}₽")

        # Фундамент
        foundation_type = data.get('foundation')
        if foundation_type and foundation_type != 'Пропустить':
            foundation_cost = COSTS['materials']['foundation'].get(foundation_type, 0)
            total += foundation_cost
            details.append(f"Фундамент ({foundation_type}): {foundation_cost:,.0f}₽")

        # Кровля
        roof_type = data.get('roof')
        if roof_type and roof_type != 'Пропустить':
            roof_area = calculate_roof_area(data)
            roof_cost = roof_area * COSTS['materials']['roof'].get(roof_type, 0)
            total += roof_cost
            details.append(f"Кровля ({roof_type}): {roof_cost:,.0f}₽")

        # Утеплитель
        insulation_type = data.get('insulation')
        if insulation_type and insulation_type != 'Пропустить':
            thickness = float(data.get('insulation_thickness', 150))
            material = COSTS['materials']['insulation'][insulation_type]
            insulation_cost = (thickness / 100) * area * material['price']
            total += insulation_cost
            details.append(f"Утеплитель ({insulation_type} {thickness}мм): {insulation_cost:,.0f}₽")

        # Внешняя отделка
        exterior_type = data.get('exterior')
        if exterior_type and exterior_type != 'Пропустить':
            exterior_cost = area * COSTS['materials']['exterior'].get(exterior_type, 0)
            total += exterior_cost
            details.append(f"Внешняя отделка ({exterior_type}): {exterior_cost:,.0f}₽")

        # Внутренняя отделка
        interior_type = data.get('interior')
        if interior_type and interior_type != 'Пропустить':
            interior_cost = area * COSTS['materials']['interior'].get(interior_type, 0)
            total += interior_cost
            details.append(f"Внутренняя отделка ({interior_type}): {interior_cost:,.0f}₽")

        # Окна и двери
        windows_count = int(data.get('windows_count', 0))
        entrance_doors = int(data.get('entrance_doors', 0))
        inner_doors = int(data.get('inner_doors', 0))
        
        windows_cost = windows_count * COSTS['materials']['windows']
        entrance_doors_cost = entrance_doors * COSTS['materials']['doors']['входная']
        inner_doors_cost = inner_doors * COSTS['materials']['doors']['межкомнатная']
        doors_windows_total = windows_cost + entrance_doors_cost + inner_doors_cost
        total += doors_windows_total
        details.append(f"Окна/двери: {doors_windows_total:,.0f}₽")

        # Терраса
        terrace_area = float(data.get('terrace_area', 0))
        terrace_cost = terrace_area * COSTS['work']['terrace']
        total += terrace_cost
        if terrace_area > 0:
            details.append(f"Терраса: {terrace_cost:,.0f}₽")

        # Региональный коэффициент
        region = data.get('region', 'Другой')
        regional_coeff = REGIONAL_COEFFICIENTS.get(region, 1.0)
        total *= regional_coeff
        details.append(f"Региональный коэффициент ({region}): x{regional_coeff}")

        # Скидки
        selected_items = sum(1 for k in data if data.get(k) and k not in ['area', 'floors', 'region'])
        if selected_items > 5:
            total *= 0.9
            details.append("Скидка за комплексный заказ: 10%")
        
        if area > 200:
            total *= 0.95
            details.append("Скидка за большую площадь: 5%")

    except Exception as e:
        raise ValueError(f"Ошибка расчета: {str(e)}")
    
    return round(total, 2), details

def calculate_and_send_result(user_id):
    try:
        user = get_user_data(user_id)
        project = user['projects'][user['current_project']]
        total, details = calculate_cost(project['data'])
        
        project['report'] = {
            'details': details,
            'total': total,
            'timestamp': datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        
        project['completed'] = True
        project['total_cost'] = total
        track_event('complete')
        
        result = [
            "📊 Детализированный расчет стоимости:",
            *details,
            "────────────────────────",
            f"💰 Итоговая стоимость: {total:,.0f} руб."
        ]
        
        bot.send_message(user_id, "\n".join(result))
        show_main_menu(types.Message(chat=types.Chat(id=user_id)))
        schedule_reminder(user_id, project['name'])
        
    except Exception as e:
        bot.send_message(user_id, f"⚠️ Ошибка: {str(e)}")
        track_event('abandon', project['data'].get('step', 0))
    finally:
        if user_id in user_data:
            user['current_project'] = None

@bot.message_handler(func=lambda m: m.text == "📚 Строительный гайд")
def show_guide_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for key in GUIDES:
        markup.add(types.InlineKeyboardButton(GUIDES[key]['title'], callback_data=f"guide_{key}"))
    markup.add(types.InlineKeyboardButton("🔙 Главное меню", callback_data="guide_back"))
    bot.send_message(message.chat.id, "📚 Выберите раздел гайда:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('guide'))
def handle_guides(call):
    user_id = call.message.chat.id
    if call.data == "guide_back":
        bot.delete_message(user_id, call.message.message_id)
        show_main_menu(call.message)
        return
    
    if call.data == "guide_list":
        show_guide_menu(call.message)
        return
    
    section = call.data.split('_')[1]
    guide = GUIDES[section]
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад к списку", callback_data="guide_list"))
    
    try:
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=f"📖 <b>{guide['title']}</b>\n\n{guide['content']}",
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception as e:
        logging.error(f"Error editing message: {str(e)}")

@bot.message_handler(func=lambda m: m.text == "⚙ Настройки")
def handle_settings(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🗑️ Очистить историю", "🔙 Главное меню")
    bot.send_message(message.chat.id, "⚙ Настройки:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🗑️ Очистить историю")
def clear_history(message):
    user_id = message.chat.id
    user = get_user_data(user_id)
    user['projects'] = {}
    bot.send_message(user_id, "✅ История расчетов успешно очищена!")
    show_main_menu(message)

@bot.message_handler(func=lambda m: m.text == "🔙 Главное меню")
def back_to_main(message):
    show_main_menu(message)

@bot.message_handler(func=lambda m: m.text == "📊 История расчетов")
def show_history(message):
    user_id = message.chat.id
    user = get_user_data(user_id)
    
    if not user['projects']:
        bot.send_message(user_id, "📭 У вас пока нет сохраненных проектов")
        return
    
    response = ["📋 Ваши проекты:"]
    for pid, project in user['projects'].items():
        if project.get('report'):
            status = f"✅ {project['report']['timestamp']}"
            response.append(f"{project['name']} - {status}\nСтоимость: {project['report']['total']:,.0f} руб.")
    
    bot.send_message(user_id, "\n".join(response))

def self_ping():
    while True:
        try:
            requests.get("https://karkasmaster.onrender.com")
        except Exception as e:
            logging.error(f"Ping failed: {str(e)}")
        threading.Event().wait(300)

app = Flask(__name__)

@app.route('/')
def home():
    return "🏠 Construction Bot работает!"

@app.route('/analytics')
def show_analytics():
    completion_rate = analytics_data['completed_calculations'] / analytics_data['started_calculations'] * 100 if analytics_data['started_calculations'] > 0 else 0
    return f"""
    📊 Аналитика:
    Начато расчетов: {analytics_data['started_calculations']}
    Завершено: {analytics_data['completed_calculations']} ({completion_rate:.1f}%)
    Проблемные шаги: {analytics_data['abandoned_steps']}
    """

def start_bot():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    threading.Thread(target=self_ping, daemon=True).start()
    
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
