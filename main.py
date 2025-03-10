import os
import logging
import threading
import math
from datetime import datetime
from flask import Flask
import telebot
from telebot import types
import requests
from apscheduler.schedulers.background import BackgroundScheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация Flask
app = Flask(__name__)
@app.route('/')
def index():
    return "Telegram-бот работает!"

# Конфигурация бота
API_TOKEN = os.getenv('API_TOKEN')
bot = telebot.TeleBot(API_TOKEN)

# Планировщик задач
scheduler = BackgroundScheduler()
scheduler.start()

# Глобальное хранилище данных
user_data = {}
analytics_data = {
    'started_calculations': 0,
    'completed_calculations': 0,
    'abandoned_steps': {}
}

STYLES = {
    'header': '🔹',
    'error': '❌',
    'success': '✅',
    'warning': '⚠️',
    'separator': '\n────────────────────────',
    'currency': '₽'
}

EMOJI_MAP = {
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

COST_CONFIG = {
    'materials': {
        'foundation': {
            'Свайно-винтовой': {'price_per_pile': 2500, 'pile_distance': 2},
            'Ленточный': {'price_per_m3': 8000},
            'Плитный': {'price_per_m2': 2500}
        },
        'roof': {
            'Металлочерепица': 1200,
            'Мягкая кровля': 800,
            'Фальцевая кровля': 1800,
            'Пропустить': 0
        },
        'insulation': {
            'Минеральная вата': {'price_per_m3': 5000},
            'Эковата': {'price_per_m3': 4000},
            'Пенополистирол': {'price_per_m3': 6000},
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
            'price_per_m2': 8000,
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
    'Калужская обл': {'base': 1.0, 'delivery': 1.05},
    'Московская обл': {'base': 1.2, 'delivery': 1.1},
    'Другой': {'base': 1.5, 'delivery': 1.3}
}

QUESTIONS = [
    {
        'text': '📍 Регион строительства:',
        'options': ['Калужская обл', 'Московская обл', 'Другой'],
        'key': 'region',
        'row_width': 2
    },
    {
        'text': '📐 Длина дома (м):',
        'key': 'length',
        'options': ['7', '10', '12', 'Пропустить'],
        'row_width': 3
    },
    {
        'text': '📏 Ширина дома (м):',
        'key': 'width',
        'options': ['14', '10', '8', 'Пропустить'],
        'row_width': 3
    },
    {
        'text': 'Высота этажа (м):',
        'key': 'height',
        'options': ['2.5', '3.0', 'Пропустить'],
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

GUIDES = {
    'foundation': {
        'title': '🏗️ Выбор фундамента',
        'content': '''🔍 <b>Подробный гайд по фундаментам:</b>
1. <u>Свайно-винтовой</u>
   - Стоимость: 15 000-20 000 руб/м²
   - Срок монтажа: 2-3 дня
   - Грунты: болотистые, пучинистые
   - Плюсы: быстрый монтаж, низкая цена
   - Минусы: требует антикоррозийной обработки
2. <u>Ленточный</u>
   - Стоимость: 20 000-25 000 руб/м²
   - Срок монтажа: 14-21 день
   - Грунты: стабильные, песчаные
   - Плюсы: высокая несущая способность
   - Минусы: требует времени на усадку
💡 <b>Советы инженеров:</b>
✅ Всегда делайте геологию грунта
❌ Не экономьте на гидроизоляции
📆 Оптимальный сезон монтажа: лето-осень'''
    },
    'walls': {
        'title': '🧱 Каркас и стены',
        'content': '''🔍 <b>Технологии строительства:</b>
1. <u>Платформа</u>
   - Толщина стен: 200-250 мм
   - Утеплитель: базальтовая вата
   - Обшивка: OSB-3 12 мм
   - Пароизоляция: обязательна
2. <u>Двойной каркас</u>
   - Толщина стен: 300-400 мм
   - Перекрестное утепление
   - Шумоизоляция: 20-30 дБ
📐 <b>Расчет материалов:</b>
- Стойки: 50x150 мм с шагом 600 мм
- Обвязки: двойная доска 50x200 мм
- Крепеж: оцинкованные уголки'''
    },
    'roof': {
        'title': '🏛️ Кровельные системы',
        'content': '''🔍 <b>Типы кровельных систем:</b>
1. <u>Холодная кровля</u>
   - Уклон: 25-45°
   - Вентиляция: продухи + коньковый аэратор
   - Срок службы: 25-50 лет
2. <u>Теплая кровля</u>
   - Утеплитель: 250-300 мм
   - Пароизоляция: фольгированная мембрана
   - Контробрешетка: 50 мм зазор
⚡ <b>Важно:</b>
- Расчет снеговой нагрузки по СП 20.13330
- Используйте ветрозащитные планки
- Монтаж ендовы с двойным слоем гидроизоляции'''
    }
}

def get_user_data(user_id):
    user_id_str = str(user_id)
    if user_id_str not in user_data:
        user_data[user_id_str] = {
            'projects': {},
            'current_project': None,
            'last_active': datetime.now(),
            'reminders': []
        }
    return user_data[user_id_str]

def create_keyboard(items, row_width, skip_button=False):
    markup = types.ReplyKeyboardMarkup(row_width=row_width, resize_keyboard=True)
    filtered = [item for item in items if item != 'Пропустить']
    for i in range(0, len(filtered), row_width):
        markup.add(*filtered[i:i+row_width])
    if skip_button:
        markup.add('Пропустить')
    markup.add('❌ Отменить расчет')
    return markup

def schedule_reminder(user_id, project_name):
    job_id = f"reminder_{user_id}_{project_name}"
    if not scheduler.get_job(job_id):
        scheduler.add_job(
            send_reminder,
            'interval',
            days=1,
            id=job_id,
            args=[user_id, project_name],
            max_instances=3
        )
        logger.info(f"Scheduled reminder: {job_id}")

def send_reminder(user_id, project_name):
    try:
        bot.send_message(
            user_id,
            f"{STYLES['warning']} Напоминание о проекте '{project_name}'\n"
            f"Продолжить расчет? Используйте /menu"
        )
    except Exception as e:
        logger.error(f"Ошибка напоминания: {str(e)}")

def track_event(event_type, step=None):
    if event_type == 'start':
        analytics_data['started_calculations'] += 1
    elif event_type == 'complete':
        analytics_data['completed_calculations'] += 1
    elif event_type == 'abandon':
        analytics_data['abandoned_steps'][step] = analytics_data['abandoned_steps'].get(step, 0) + 1

def create_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ["🏠 Новый проект", "📚 Гайды"]
    markup.add(*buttons)
    return markup

@bot.message_handler(commands=['start', 'menu'])
def show_main_menu(message):
    user_id = message.chat.id
    user = get_user_data(user_id)
    user['last_active'] = datetime.now()
    bot.send_message(user_id, f"{STYLES['header']} Главное меню:", reply_markup=create_main_menu())

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
    progress_text = (
        f"{STYLES['header']} Шаг {current_step + 1}/{TOTAL_STEPS}\n"
        f"{question['text']}"
    )
    markup = create_keyboard(question['options'], question.get('row_width', 2), 'Пропустить' in question['options'])
    bot.send_message(user_id, progress_text, reply_markup=markup)
    bot.register_next_step_handler_by_chat_id(user_id, process_answer, current_step=current_step)

def validate_input(answer, question):
    if answer not in question['options'] and answer != 'Пропустить':
        return f"Выберите вариант из списка: {', '.join(question['options'])}"
    if question['key'] in ['length', 'width', 'height', 'terrace_area']:
        try:
            value = float(answer.replace(',', '.'))
            if value < 0:
                return "Значение не может быть отрицательным"
        except ValueError:
            return "Введите числовое значение"
    elif question['key'] in ['windows_count', 'entrance_doors', 'inner_doors']:
        if not answer.isdigit():
            return "Введите целое число"
        if int(answer) < 0:
            return "Количество не может быть отрицательным"
    return None

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
        error = validate_input(answer, question)
        if error:
            raise ValueError(error)
        if answer == 'Пропустить':
            project['data'][question['key']] = None
        else:
            if question['key'] in ['windows_count', 'entrance_doors', 'inner_doors']:
                project['data'][question['key']] = int(answer)
            elif question['key'] in ['length', 'width', 'height', 'terrace_area']:
                project['data'][question['key']] = float(answer.replace(',', '.'))
            else:
                project['data'][question['key']] = answer
        project['data']['step'] = current_step + 1
        user['last_active'] = datetime.now()
    except Exception as e:
        logger.error(f"Ошибка пользователя {user_id}: {str(e)}")
        bot.send_message(
            user_id,
            f"{STYLES['error']} Ошибка:\n{str(e)}\nПовторите ввод:",
            reply_markup=create_keyboard(
                question['options'],
                question.get('row_width', 2),
                'Пропустить' in question['options']
            )
        )
        bot.register_next_step_handler_by_chat_id(user_id, process_answer, current_step=current_step)
        track_event('abandon', current_step)
        return
    ask_next_question(user_id)

class CostCalculator:
    @staticmethod
    def calculate_total(data):
        total = 0
        details = []
        
        # Основные работы
        base_work = CostCalculator._calculate_base_works(data)
        total += base_work['total']
        details.extend(base_work['details'])
        
        # Фундамент
        foundation_cost = CostCalculator._calculate_foundation_cost(data)
        total += foundation_cost['total']
        details.extend(foundation_cost['details'])
        
        # Кровля
        roof_cost = CostCalculator._calculate_roof_cost(data)
        total += roof_cost['total']
        details.extend(roof_cost['details'])
        
        # Утепление
        insulation_cost = CostCalculator._calculate_insulation_cost(data)
        total += insulation_cost['total']
        details.extend(insulation_cost['details'])
        
        # Отделка
        exterior_cost = CostCalculator._calculate_exterior_cost(data)
        total += exterior_cost['total']
        details.extend(exterior_cost['details'])
        
        interior_cost = CostCalculator._calculate_interior_cost(data)
        total += interior_cost['total']
        details.extend(interior_cost['details'])
        
        # Окна и двери
        openings_cost = CostCalculator._calculate_openings_cost(data)
        total += openings_cost['total']
        details.extend(openings_cost['details'])
        
        # Терраса
        terrace_cost = CostCalculator._calculate_terrace_cost(data)
        total += terrace_cost['total']
        details.extend(terrace_cost['details'])
        
        # Применение коэффициентов
        total = CostCalculator._apply_coefficients(data, total, details)
        
        return round(total), details

    @staticmethod
    def _calculate_base_works(data):
        total = 0
        details = []
        floors = data.get('floors', 'Одноэтажный')
        length = data.get('length', 7)
        width = data.get('width', 14)
        height = data.get('height', 2.5)
        area = length * width
        
        multiplier = COST_CONFIG['work']['base']['floor_multiplier'][floors]
        cost = area * height * COST_CONFIG['work']['base']['price_per_m2'] * multiplier
        total += cost
        details.append(f"🔹 Основные работы ({floors}): {cost:,.0f}{STYLES['currency']}")
        return {'total': total, 'details': details}

    @staticmethod
    def _calculate_foundation_cost(data):
        total = 0
        details = []
        foundation_type = data.get('foundation')
        if not foundation_type or foundation_type == 'Пропустить':
            return {'total': 0, 'details': []}
        
        config = COST_CONFIG['materials']['foundation'][foundation_type]
        length = data.get('length', 7)
        width = data.get('width', 14)
        perimeter = 2 * (length + width)
        
        if foundation_type == 'Свайно-винтовой':
            num_piles = perimeter / config['pile_distance']
            cost = num_piles * config['price_per_pile']
            details.append(f"مصالح Свайный фундамент: {num_piles:.0f} свай")
        elif foundation_type == 'Ленточный':
            volume = perimeter * 0.4 * 0.6  # Ширина 0.4м, высота 0.6м
            cost = volume * config['price_per_m3']
            details.append(f"مصالح Ленточный фундамент: {volume:.2f} м³")
        elif foundation_type == 'Плитный':
            area = length * width
            cost = area * config['price_per_m2']
            details.append(f"愍 Плитный фундамент: {area:.2f} м²")
            
        total += cost
        return {'total': total, 'details': details}

    @staticmethod
    def _calculate_roof_cost(data):
        total = 0
        details = []
        roof_type = data.get('roof')
        if not roof_type or roof_type == 'Пропустить':
            return {'total': 0, 'details': []}
        
        length = data.get('length', 7)
        width = data.get('width', 14)
        roof_area = 2 * (length * math.sqrt((width/2)**2 + (3)**2))  # Для двускатной
        
        cost = roof_area * COST_CONFIG['materials']['roof'][roof_type]
        total += cost
        details.append(f"🏛️ Кровля ({roof_type}): {roof_area:.1f} м²")
        return {'total': total, 'details': details}

    @staticmethod
    def _calculate_insulation_cost(data):
        total = 0
        details = []
        insulation_type = data.get('insulation')
        if not insulation_type or insulation_type == 'Пропустить':
            return {'total': 0, 'details': []}
        
        thickness = data.get('insulation_thickness', 150) / 1000
        length = data.get('length', 7)
        width = data.get('width', 14)
        height = data.get('height', 2.5)
        
        wall_area = 2 * (length + width) * height
        roof_area = 2 * (length * math.sqrt((width/2)**2 + (3)**2))
        floor_area = length * width
        
        volume = (wall_area + roof_area + floor_area) * thickness
        cost = volume * COST_CONFIG['materials']['insulation'][insulation_type]['price_per_m3']
        total += cost
        details.append(f"❄️ Утепление ({insulation_type}): {volume:.2f} м³")
        return {'total': total, 'details': details}

    @staticmethod
    def _calculate_exterior_cost(data):
        total = 0
        details = []
        exterior = data.get('exterior')
        if not exterior or exterior == 'Пропустить':
            return {'total': 0, 'details': []}
        
        length = data.get('length', 7)
        width = data.get('height', 14)
        height = data.get('height', 2.5)
        wall_area = 2 * (length + width) * height
        
        cost = wall_area * COST_CONFIG['materials']['exterior'][exterior]
        total += cost
        details.append(f"🎨 Внешняя отделка ({exterior}): {wall_area:.1f} м²")
        return {'total': total, 'details': details}

    @staticmethod
    def _calculate_interior_cost(data):
        total = 0
        details = []
        interior = data.get('interior')
        if not interior or interior == 'Пропустить':
            return {'total': 0, 'details': []}
        
        length = data.get('length', 7)
        width = data.get('width', 14)
        height = data.get('height', 2.5)
        wall_area = 2 * (length + width) * height
        
        cost = wall_area * COST_CONFIG['materials']['interior'][interior]
        total += cost
        details.append(f"🛋️ Внутренняя отделка ({interior}): {wall_area:.1f} м²")
        return {'total': total, 'details': details}

    @staticmethod
    def _calculate_openings_cost(data):
        total = 0
        details = []
        windows = data.get('windows_count', 0)
        entrance = data.get('entrance_doors', 0)
        inner = data.get('inner_doors', 0)
        
        window_cost = windows * COST_CONFIG['materials']['windows']
        entrance_cost = entrance * COST_CONFIG['materials']['doors']['входная']
        inner_cost = inner * COST_CONFIG['materials']['doors']['межкомнатная']
        
        total += window_cost + entrance_cost + inner_cost
        details.append(f"🪟 Окна: {windows} шт.")
        details.append(f"🚪 Входные двери: {entrance} шт.")
        details.append(f"🚪 Межкомнатные двери: {inner} шт.")
        return {'total': total, 'details': details}

    @staticmethod
    def _calculate_terrace_cost(data):
        total = 0
        details = []
        terrace = data.get('terrace_area', 0)
        if terrace <= 0:
            return {'total': 0, 'details': []}
        
        cost = terrace * COST_CONFIG['work']['terrace']
        total += cost
        details.append(f"🌳 Терраса: {terrace} м²")
        return {'total': total, 'details': details}

    @staticmethod
    def _apply_coefficients(data, total, details):
        region = data.get('region', 'Другой')
        coeff = REGIONAL_COEFFICIENTS.get(region, {'base': 1.0, 'delivery': 1.0})
        
        total *= coeff['base']
        details.append(f"📍 Региональный коэффициент ({region}): ×{coeff['base']:.1f}")
        
        if total > 500000:
            details.append("🎁 Скидка за крупный заказ: 5%")
            total *= 0.95
        
        return total

def calculate_and_send_result(user_id):
    try:
        user = get_user_data(user_id)
        project_id = user['current_project']
        project = user['projects'][project_id]
        total, details = CostCalculator.calculate_total(project['data'])
        send_result_message(user_id, total, details)
        schedule_reminder(user_id, project['name'])
    except Exception as e:
        logger.error(f"Ошибка расчета: {str(e)}")
        bot.send_message(user_id, f"{STYLES['error']} Ошибка расчета: {str(e)}")
        track_event('abandon', project['data'].get('step', 0))
    finally:
        user['current_project'] = None

def send_result_message(user_id, total, details):
    formatted_details = []
    for item in details:
        parts = item.split(':')
        if len(parts) > 1:
            name_part = parts[0].strip()
            price_part = parts[1].strip()
            formatted_details.append(f"<b>{name_part}</b>: <code>{price_part}</code>")
        else:
            formatted_details.append(item)
    result = [
        f"{STYLES['header']} 📊 Детализированный расчет стоимости:",
        *formatted_details,
        STYLES['separator'],
        f"💰 <b>Итоговая стоимость</b>: <code>{total:,.0f} руб.</code>"
    ]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📨 Отправить специалисту")
    markup.row("🔙 Главное меню")
    bot.send_message(
        user_id,
        "\n".join(result),
        reply_markup=markup,
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda m: m.text == "📨 Отправить специалисту")
def send_to_specialist(message):
    user_id = message.chat.id
    user = get_user_data(user_id)
    project_id = user.get('current_project') or max(
        user['projects'].keys(), 
        key=lambda k: user['projects'][k]['created_at'], 
        default=None
    )
    if not project_id:
        bot.send_message(user_id, f"{STYLES['error']} Нет активных проектов")
        return
    project = user['projects'].get(project_id)
    if not project:
        bot.send_message(user_id, f"{STYLES['error']} Проект не найден")
        return
    try:
        total, details = CostCalculator.calculate_total(project['data'])
        formatted_details = []
        for item in details:
            parts = item.split(':')
            if len(parts) > 1:
                name_part = parts[0].strip()
                price_part = parts[1].strip()
                formatted_details.append(f"<b>{name_part}</b>: <code>{price_part}</code>")
            else:
                formatted_details.append(item)
        result = [
            f"{STYLES['header']} Новый запрос от @{message.from_user.username}",
            "📊 Детали расчета:",
            *formatted_details,
            STYLES['separator'],
            f"💰 <b>Итоговая стоимость</b>: <code>{total:,.0f} руб.</code>"
        ]
        bot.send_message(515650034, "\n".join(result), parse_mode='HTML')
        bot.send_message(user_id, f"{STYLES['success']} Запрос отправлен специалисту!")
    except Exception as e:
        logger.error(f"Ошибка отправки: {str(e)}")
        bot.send_message(user_id, f"{STYLES['error']} Ошибка отправки: {str(e)}")
    show_main_menu(message)

@bot.message_handler(func=lambda m: m.text == "📚 Гайды")
def show_guides_menu(message):
    user_id = message.chat.id
    user = get_user_data(user_id)
    user['last_active'] = datetime.now()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [g['title'] for g in GUIDES.values()]
    markup.add(*buttons)
    markup.add("🔙 Главное меню")
    bot.send_message(
        user_id,
        f"{STYLES['header']} Выберите раздел гайда:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text in [g['title'] for g in GUIDES.values()])
def show_guide_content(message):
    user_id = message.chat.id
    user = get_user_data(user_id)
    user['last_active'] = datetime.now()
    guide_title = message.text
    for key, guide in GUIDES.items():
        if guide['title'] == guide_title:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("🔙 К списку гайдов")
            bot.send_message(
                user_id,
                f"📖 <b>{guide['title']}</b>\n{guide['content']}",
                parse_mode='HTML',
                reply_markup=markup
            )
            break

@bot.message_handler(func=lambda m: m.text == "🔙 К списку гайдов")
def back_to_guides(message):
    show_guides_menu(message)

@bot.message_handler(func=lambda m: m.text == "🔙 Главное меню")
def back_to_main_menu(message):
    user_id = message.chat.id
    user = get_user_data(user_id)
    user['current_project'] = None
    show_main_menu(message)

def self_ping():
    while True:
        try:
            requests.get("https://karkasmaster.onrender.com")
            logger.info("Self-ping успешен")
        except Exception as e:
            logger.error(f"Ошибка self-ping: {str(e)}")
        threading.Event().wait(300)

if __name__ == '__main__':
    # Удаляем старые вебхуки
    bot.remove_webhook()
    # Запускаем бота в основном потоке
    bot_thread = threading.Thread(target=bot.polling, kwargs={
        'none_stop': True,
        'interval': 0,
        'timeout': 20
    })
    bot_thread.daemon = True
    bot_thread.start()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
