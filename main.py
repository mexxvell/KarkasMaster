import requests
import os
import logging
import math
from datetime import datetime
from flask import Flask, request, send_file
import telebot
from telebot import types
from apscheduler.schedulers.background import BackgroundScheduler
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def index():
    return "Telegram-бот работает!"

API_TOKEN = os.getenv('API_TOKEN')
bot = telebot.TeleBot(API_TOKEN)

scheduler = BackgroundScheduler()
scheduler.start()

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
    'region': '📍',
    'wall_frame': '🪵',
    'wall_insulation': '🧽',
    'wall_cladding': '얇'
}

COST_CONFIG = {
    'materials': {
        'foundation': {
            'Свайно-винтовой': {'price_per_pile': 2500, 'depth': 2.5},
            'Ленточный': {'price_per_m3': 5000},
            'Плитный': {'price_per_m2': 3000}
        },
        'wall_frame': {
            'Каркас 50x150': {'price_per_m3': 8000},
            'Двойной каркас': {'price_per_m3': 12000}
        },
        'wall_insulation': {
            'Минеральная вата': {'price_per_m3': 3000, 'min_thickness': 150},
            'Эковата': {'price_per_m3': 2500, 'min_thickness': 100},
            'Пенополистирол': {'price_per_m3': 4000, 'min_thickness': 50}
        },
        'wall_cladding': {
            'OSB-3': {'price_per_m2': 400},
            'Вагонка': {'price_per_m2': 500},
            'Штукатурка': {'price_per_m2': 300},
            'Сайдинг': {'price_per_m2': 450}
        },
        'roof': {
            'Металлочерепица': {'price_per_m2': 500, 'slope_factor': 1.2},
            'Мягкая кровля': {'price_per_m2': 700, 'slope_factor': 1.1},
            'Фальцевая кровля': {'price_per_m2': 900, 'slope_factor': 1.3}
        },
        'insulation': {
            'Минеральная вата': {'price_per_m3': 3000, 'min_thickness': 150},
            'Эковата': {'price_per_m3': 2500, 'min_thickness': 100},
            'Пенополистирол': {'price_per_m3': 4000, 'min_thickness': 50}
        },
        'exterior': {
            'Сайдинг': {'price_per_m2': 400},
            'Вагонка': {'price_per_m2': 500},
            'Штукатурка': {'price_per_m2': 300}
        },
        'interior': {
            'Вагонка': {'price_per_m2': 600},
            'Гипсокартон': {'price_per_m2': 400}
        },
        'windows': {'price_per_unit': 8000},
        'doors': {
            'входная': {'price': 15000},
            'межкомнатная': {'price': 8000}
        }
    },
    'work': {
        'excavation': {'price_per_m3': 1500},
        'concrete_works': {'price_per_m3': 3000},
        'carpentry': {'price_per_m2': 1000},
        'roof_installation': {'price_per_m2': 800},
        'insulation_work': {'price_per_m3': 2000},
        'exterior_work': {'price_per_m2': 500},
        'interior_work': {'price_per_m2': 700}
    }
}

REGIONAL_COEFFICIENTS = {
    'Калужская обл': 1.0,
    'Московская обл': 1.2,
    'Другой': 1.5
}

QUESTIONS = [
    {
        'text': '📍 Регион строительства:',
        'options': ['Калужская обл', 'Московская обл', 'Другой'],
        'key': 'region',
        'row_width': 2
    },
    {
        'text': '🏠 Стиль дома:',
        'options': ['A-frame', 'BARNHOUSE', 'ХОЗБЛОК', 'Скандинавский стиль'],
        'key': 'house_style',
        'row_width': 2
    },
    {
        'text': '📐 Ширина дома (м):',
        'options': ['4', '6', '8', '10'],
        'key': 'width',
        'row_width': 4,
        'validation': lambda x: 4 <= float(x) <= 12
    },
    {
        'text': '📏 Длина дома (м):',
        'options': ['8', '10', '12', '14'],
        'key': 'length',
        'row_width': 4,
        'validation': lambda x: 6 <= float(x) <= 16
    },
    {
        'text': '瓴 Высота этажа (м):',
        'options': ['2.5', '3.0'],
        'key': 'height',
        'row_width': 2,
        'validation': lambda x: x in ['2.5', '3.0'],
        'condition': lambda data: data['house_style'] == 'Скандинавский стиль'
    },
    {
        'text': 'этажность 🏠:',
        'options': ['Одноэтажный', 'Двухэтажный', 'С мансардой'],
        'key': 'floors',
        'row_width': 2,
        'condition': lambda data: data['house_style'] == 'Скандинавский стиль'
    },
    {
        'text': 'Кровля 🏛️:',
        'options': ['Металлочерепица', 'Мягкая кровля'],
        'key': 'roof_type',
        'row_width': 2,
        'condition': lambda data: data['house_style'] == 'Скандинавский стиль'
    },
    {
        'text': 'Утепление стен ❄️:',
        'options': ['Минеральная вата', 'Эковата', 'Пенополистирол'],
        'key': 'wall_insulation_type',
        'row_width': 2
    },
    {
        'text': 'Толщина утеплителя (мм) 📏:',
        'options': ['50', '100', '150', '200'],
        'key': 'wall_insulation_thickness',
        'row_width': 4,
        'validation': lambda x, data: int(x) >= COST_CONFIG['materials']['wall_insulation'][data['wall_insulation_type']]['min_thickness']
    },
    {
        'text': 'Внешняя отделка 🎨:',
        'options': ['Сайдинг', 'Вагонка', 'Штукатурка'],
        'key': 'exterior_type',
        'row_width': 2
    },
    {
        'text': 'Внутренняя отделка 🛋️:',
        'options': ['Вагонка', 'Гипсокартон'],
        'key': 'interior_type',
        'row_width': 2
    },
    {
        'text': 'Количество окон 🪟:',
        'options': [str(x) for x in range(1, 11)],
        'key': 'window_count',
        'row_width': 5,
        'validation': lambda x: 1 <= int(x) <= 10,
        'condition': lambda data: data['house_style'] == 'Скандинавский стиль'
    },
    {
        'text': 'Входные двери 🚪:',
        'options': [str(x) for x in range(1, 6)],
        'key': 'entrance_doors',
        'row_width': 5,
        'validation': lambda x: 1 <= int(x) <= 5
    },
    {
        'text': 'Межкомнатные двери 🚪:',
        'options': [str(x) for x in range(1, 11)],
        'key': 'interior_doors',
        'row_width': 5,
        'validation': lambda x: 1 <= int(x) <= 10
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

def create_keyboard(user_id, items, row_width, skip_button=False, back_button=False):
    markup = types.ReplyKeyboardMarkup(row_width=row_width, resize_keyboard=True)
    filtered = [item for item in items if item != 'Пропустить']
    for i in range(0, len(filtered), row_width):
        markup.add(*filtered[i:i+row_width])
    if skip_button:
        markup.add('Пропустить')
    if back_button:
        user = get_user_data(user_id)
        current_project = user['current_project']
        if current_project and 'step' in user['projects'][current_project]['data']:
            markup.add('🔙 Назад')
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
        'data': {
            'foundation_type': 'Свайно-винтовой',
            'roof_type': 'Фальцевая кровля',
            'wall_insulation_type': 'Минеральная вата',
            'wall_insulation_thickness': 150,
            'window_count': 1,
            'entrance_doors': 1,
            'interior_doors': 0
        },
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
    
    if project['data'].get('house_style') in ['A-frame', 'BARNHOUSE', 'ХОЗБЛОК']:
        project['data'].setdefault('floors', 'Одноэтажный')
        project['data'].setdefault('roof_type', 'Фальцевая кровля')
        project['data'].setdefault('window_count', 1)
        project['data'].setdefault('height', 3.0 if project['data']['house_style'] == 'A-frame' else 2.5)
    
    while current_step < TOTAL_STEPS:
        question = QUESTIONS[current_step]
        if 'condition' in question and not question['condition'](project['data']):
            current_step += 1
            project['data']['step'] = current_step
        else:
            break
    
    if current_step >= TOTAL_STEPS:
        calculate_and_send_result(user_id)
        return
    
    question = QUESTIONS[current_step]
    progress_text = (
        f"{STYLES['header']} Шаг {current_step + 1}/{TOTAL_STEPS}\n"
        f"{question['text']}"
    )
    markup = create_keyboard(
        user_id,
        question['options'],
        question.get('row_width', 2),
        'Пропустить' in question.get('options', []),
        back_button=True
    )
    bot.send_message(user_id, progress_text, reply_markup=markup)
    bot.register_next_step_handler_by_chat_id(user_id, process_answer, current_step=current_step)

def validate_input(answer, question, user_data):
    if answer not in question['options'] and answer not in ['Пропустить', '🔙 Назад']:
        return f"Выберите вариант из списка: {', '.join(question['options'])}"
    if question['key'] == 'wall_insulation_thickness':
        min_thickness = COST_CONFIG['materials']['wall_insulation'][user_data['wall_insulation_type']]['min_thickness']
        if int(answer) < min_thickness:
            return f"Минимальная толщина для {user_data['wall_insulation_type']} - {min_thickness} мм"
    if question['key'] in ['width', 'length', 'height']:
        try:
            value = float(answer.replace(',', '.'))
            if 'validation' in question and not question['validation'](answer):
                return "Недопустимое значение"
        except ValueError:
            return "Введите числовое значение"
    if question['key'] in ['window_count', 'entrance_doors', 'interior_doors']:
        if not answer.isdigit() and answer not in ['Пропустить', '🔙 Назад']:
            return "Введите целое число"
        if int(answer) < 0:
            return "Количество не может быть отрицательным"
    return None

def process_answer(message, current_step):
    user_id = message.chat.id
    user = get_user_data(user_id)
    project = user['projects'][user['current_project']]
    
    if message.text == "🔙 Назад":
        if current_step > 0:
            project['data']['step'] = current_step - 1
            return ask_next_question(user_id)
        else:
            return show_main_menu(message)
    if message.text == "❌ Отменить расчет":
        del user['projects'][user['current_project']]
        user['current_project'] = None
        return show_main_menu(message)
    
    question = QUESTIONS[current_step]
    try:
        answer = message.text.strip()
        error = validate_input(answer, question, project['data'])
        if error:
            raise ValueError(error)
        if answer == 'Пропустить':
            project['data'][question['key']] = None
        else:
            if question['key'] in ['window_count', 'entrance_doors', 'interior_doors']:
                project['data'][question['key']] = int(answer)
            elif question['key'] in ['width', 'length', 'height']:
                project['data'][question['key']] = float(answer.replace(',', '.'))
            elif question['key'] == 'wall_insulation_thickness':
                project['data'][question['key']] = int(answer)
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
                user_id,
                question['options'],
                question.get('row_width', 2),
                'Пропустить' in question.get('options', []),
                back_button=True
            )
        )
        bot.register_next_step_handler_by_chat_id(user_id, process_answer, current_step=current_step)
        track_event('abandon', current_step)
        return
    
    ask_next_question(user_id)

class DimensionCalculator:
    @staticmethod
    def calculate_foundation(data):
        foundation_type = data['foundation_type']
        perimeter = 2 * (data['width'] + data['length'])
        config = COST_CONFIG['materials']['foundation'][foundation_type]
        
        if foundation_type == 'Свайно-винтовой':
            piles_count = math.ceil(perimeter / 1.5)
            return piles_count * config['price_per_pile']
        elif foundation_type == 'Ленточный':
            depth = 0.8
            width = 0.4
            volume = perimeter * depth * width
            return volume * config['price_per_m3']
        elif foundation_type == 'Плитный':
            area = data['width'] * data['length']
            return area * config['price_per_m2']
        return 0

    @staticmethod
    def calculate_roof(data):
        style = data.get('house_style')
        roof_type = data.get('roof_type', 'Фальцевая кровля')
        config = COST_CONFIG['materials']['roof'][roof_type]
        width = data['width']
        length = data['length']
        
        if style == 'Скандинавский стиль':
            slope = 25 if data['floors'] == 'Одноэтажный' else 35
        else:
            slope = 45
        
        roof_length = (width / 2) / math.cos(math.radians(slope))
        roof_area = 2 * roof_length * length * config['slope_factor']
        material_cost = roof_area * config['price_per_m2']
        work_cost = roof_area * COST_CONFIG['work']['roof_installation']['price_per_m2']
        return material_cost + work_cost

    @staticmethod
    def calculate_walls(data):
        perimeter = 2 * (data['width'] + data['length'])
        height = data.get('height', 2.5)
        wall_area = perimeter * height
        
        frame_config = COST_CONFIG['materials']['wall_frame']['Каркас 50x150']
        frame_volume = wall_area * 0.15  # 150 мм толщина
        frame_cost = frame_volume * frame_config['price_per_m3']
        
        insulation_type = data['wall_insulation_type']
        insulation_config = COST_CONFIG['materials']['wall_insulation'][insulation_type]
        insulation_thickness = data.get('wall_insulation_thickness', insulation_config['min_thickness']) / 1000
        insulation_volume = wall_area * insulation_thickness
        insulation_cost = insulation_volume * insulation_config['price_per_m3']
        
        cladding_config = COST_CONFIG['materials']['wall_cladding'][data['exterior_type']]
        cladding_cost = wall_area * cladding_config['price_per_m2']
        
        work_cost = wall_area * COST_CONFIG['work']['carpentry']['price_per_m2']
        return frame_cost + insulation_cost + cladding_cost + work_cost

    @staticmethod
    def calculate_windows(data):
        count = data.get('window_count', 1)
        return count * COST_CONFIG['materials']['windows']['price_per_unit']

    @staticmethod
    def calculate_doors(data):
        entrance = data['entrance_doors']
        interior = data['interior_doors']
        return (entrance * COST_CONFIG['materials']['doors']['входная']['price']) + (interior * COST_CONFIG['materials']['doors']['межкомнатная']['price'])

    @staticmethod
    def calculate_insulation_work(data):
        insulation_volume = 2 * (data['width'] + data['length']) * data.get('height', 2.5) * (data['wall_insulation_thickness'] / 1000)
        return insulation_volume * COST_CONFIG['work']['insulation_work']['price_per_m3']

class CostCalculator:
    @staticmethod
    def calculate_total(data):
        total = 0
        details = []
        
        foundation = DimensionCalculator.calculate_foundation(data)
        details.append(f"{EMOJI_MAP['foundation']} Фундамент: {foundation:,.0f}{STYLES['currency']}")
        
        roof = DimensionCalculator.calculate_roof(data)
        details.append(f"{EMOJI_MAP['roof']} Кровля: {roof:,.0f}{STYLES['currency']}")
        
        walls = DimensionCalculator.calculate_walls(data)
        details.append(f"{EMOJI_MAP['wall_frame']} Каркас: {walls:,.0f}{STYLES['currency']}")
        
        insulation = DimensionCalculator.calculate_insulation_work(data)
        details.append(f"{EMOJI_MAP['insulation']} Утепление: {insulation:,.0f}{STYLES['currency']}")
        
        windows = DimensionCalculator.calculate_windows(data)
        details.append(f"{EMOJI_MAP['windows']} Окна: {windows:,.0f}{STYLES['currency']}")
        
        doors = DimensionCalculator.calculate_doors(data)
        details.append(f"{EMOJI_MAP['doors']} Двери: {doors:,.0f}{STYLES['currency']}")
        
        region_coeff = REGIONAL_COEFFICIENTS.get(data.get('region', 'Другой'), 1.0)
        total = sum([foundation, roof, walls, insulation, windows, doors]) * region_coeff
        details.append(f"{EMOJI_MAP['region']} Региональный коэффициент: ×{region_coeff:.1f}")
        
        if data.get('window_count', 0) > 5:
            total *= 0.95
            details.append("🎁 Скидка 5% за окна")
        if data['width'] * data['length'] > 80:
            total *= 0.97
            details.append("🎁 Скидка 3% за площадь")
        
        return round(total), details

def calculate_and_send_result(user_id):
    try:
        user = get_user_data(user_id)
        project = user['projects'][user['current_project']]
        total, details = CostCalculator.calculate_total(project['data'])
        send_result_message(user_id, total, details)
        schedule_reminder(user_id, project['name'])
        project['completed'] = True  # Помечаем проект как завершенный
    except Exception as e:
        logger.error(f"Ошибка расчета: {str(e)}")
        bot.send_message(user_id, f"{STYLES['error']} Ошибка расчета: {str(e)}")
        track_event('abandon', project['data'].get('step', 0))

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
    markup.row("📨 Отправить специалисту", "🖨️ Экспорт в PDF")
    markup.row("🔙 Главное меню")
    
    bot.send_message(
        user_id,
        "\n".join(result),
        reply_markup=markup,
        parse_mode='HTML'
    )

# ИСПРАВЛЕНИЯ ДЛЯ PDF
@bot.message_handler(func=lambda m: m.text == "🖨️ Экспорт в PDF")
def export_to_pdf(message):
    user_id = message.chat.id
    user = get_user_data(user_id)
    
    # Ищем последний завершенный проект
    completed_projects = [
        p for p in user['projects'].values() 
        if p.get('completed', False)
    ]
    
    if not completed_projects:
        bot.send_message(user_id, f"{STYLES['error']} Нет завершенных проектов")
        return
    
    project = max(
        completed_projects,
        key=lambda p: p['created_at']
    )
    
    try:
        total, details = CostCalculator.calculate_total(project['data'])
        
        # Генерация PDF
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        pdf.setFont("Courier", 12)
        text = pdf.beginText(40, 750)
        
        text.textLine(f"Смета для проекта: {project['name']}")
        text.textLine(f"Дата: {datetime.now().strftime('%d.%m.%Y')}")
        text.textLine("")
        
        for line in details:
            clean_line = line.replace('<b>', '').replace('</b>', '').replace('<code>', '').replace('</code>', '')
            text.textLine(clean_line)
        
        text.textLine("")
        text.textLine(f"Итоговая стоимость: {total:,.0f} руб.")
        pdf.drawText(text)
        pdf.save()
        
        buffer.seek(0)
        bot.send_document(
            user_id,
            ('smeta.pdf', buffer),
            caption=f"🖨️ Смета проекта {project['name']}",
            reply_markup=create_main_menu()
        )
        
    except Exception as e:
        logger.error(f"Ошибка генерации PDF: {str(e)}")
        bot.send_message(user_id, f"{STYLES['error']} Ошибка генерации PDF: {str(e)}")

@bot.message_handler(func=lambda m: m.text == "📨 Отправить специалисту")
def send_to_specialist(message):
    user_id = message.chat.id
    user = get_user_data(user_id)
    
    completed_projects = [
        p for p in user['projects'].values() 
        if p.get('completed', False)
    ]
    
    if not completed_projects:
        bot.send_message(user_id, f"{STYLES['error']} Нет завершенных проектов")
        return
    
    project = max(
        completed_projects,
        key=lambda p: p['created_at']
    )
    
    try:
        total, details = CostCalculator.calculate_total(project['data'])
        formatted_details = "\n".join(details).replace(STYLES['currency'], 'руб.')
        
        result = [
            f"Новый запрос от @{message.from_user.username}",
            f"Проект: {project['name']}",
            f"Регион: {project['data'].get('region', 'Не указан')}",
            f"Площадь: {project['data']['width']}x{project['data']['length']} м",
            f"Стиль: {project['data'].get('house_style', 'Не указан')}",
            "Детали:",
            formatted_details,
            f"Итоговая стоимость: {total:,.0f} руб."
        ]
        
        bot.send_message(515650034, "\n".join(result))
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

@app.route(f'/{API_TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return '', 200

def self_ping():
    import threading
    while True:
        try:
            requests.get("https://karkasmaster.onrender.com")
            logger.info("Self-ping успешен")
        except Exception as e:
            logger.error(f"Ошибка self-ping: {str(e)}")
        threading.Event().wait(300)

if __name__ == '__main__':
    import threading
    ping_thread = threading.Thread(target=self_ping, daemon=True)
    ping_thread.start()
    
    webhook_url = f"https://karkasmaster.onrender.com/{API_TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
