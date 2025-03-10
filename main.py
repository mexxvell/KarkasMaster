import requests
import os
import logging
from datetime import datetime
from flask import Flask, request
import telebot
from telebot import types
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
            'Свайно-винтовой': {'price_per_pile': 2500, 'depth': 2.5},
            'Ленточный': {'price_per_m3': 5000},
            'Плитный': {'price_per_m2': 3000}
        },
        'walls': {
            'Каркасные': {'price_per_m2': 1200, 'thickness': 0.15},
            'Брусовые': {'price_per_m3': 10000, 'thickness': 0.2}
        },
        'roof': {
            'Металлочерепица': {'price_per_m2': 500, 'slope_factor': 1.2},
            'Мягкая кровля': {'price_per_m2': 700, 'slope_factor': 1.1},
            'Фальцевая кровля': {'price_per_m2': 900, 'slope_factor': 1.3}
        },
        'insulation': {
            'Минеральная вата': {'price_per_m3': 3000, 'density': 35},
            'Эковата': {'price_per_m3': 2500, 'density': 45},
            'Пенополистирол': {'price_per_m3': 4000, 'density': 25}
        },
        'exterior': {
            'Сайдинг': {'price_per_m2': 400, 'consumption': 1.1},
            'Вагонка': {'price_per_m2': 500, 'consumption': 1.05},
            'Штукатурка': {'price_per_m2': 300, 'consumption': 1.2}
        },
        'interior': {
            'Вагонка': {'price_per_m2': 600, 'consumption': 1.1},
            'Гипсокартон': {'price_per_m2': 400, 'consumption': 1.05}
        },
        'windows': {'price_per_unit': 8000, 'avg_area': 1.5},
        'doors': {
            'входная': {'price': 15000, 'avg_area': 2.0},
            'межкомнатная': {'price': 8000, 'avg_area': 1.8}
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
        'validation': lambda x: x in ['2.5', '3.0']
    },
    {
        'text': 'этажность 🏠:',
        'options': ['Одноэтажный', 'Двухэтажный', 'С мансардой'],
        'key': 'floors',
        'row_width': 2
    },
    {
        'text': 'Фундамент 🏗️:',
        'options': ['Свайно-винтовой', 'Ленточный', 'Плитный'],
        'key': 'foundation_type',
        'row_width': 2
    },
    {
        'text': 'Кровля 🏛️:',
        'options': ['Металлочерепица', 'Мягкая кровля', 'Фальцевая кровля'],
        'key': 'roof_type',
        'row_width': 2
    },
    {
        'text': 'Утепление ❄️:',
        'options': ['Минеральная вата', 'Эковата', 'Пенополистирол'],
        'key': 'insulation_type',
        'row_width': 2
    },
    {
        'text': 'Тип стен 🧱:',
        'options': ['Каркасные', 'Брусовые'],
        'key': 'wall_type',
        'row_width': 2
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
        'validation': lambda x: 1 <= int(x) <= 10
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
    if question['key'] in ['width', 'length', 'height']:
        try:
            value = float(answer.replace(',', '.'))
            if 'validation' in question and not question['validation'](answer):
                return "Недопустимое значение"
        except ValueError:
            return "Введите числовое значение"
    elif question['key'] in ['window_count', 'entrance_doors', 'interior_doors']:
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
            if question['key'] in ['window_count', 'entrance_doors', 'interior_doors']:
                project['data'][question['key']] = int(answer)
            elif question['key'] in ['width', 'length', 'height']:
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
    def calculate_walls(data):
        wall_type = data['wall_type']
        config = COST_CONFIG['materials']['walls'][wall_type]
        perimeter = 2 * (data['width'] + data['length'])
        height = data['height']
        
        if wall_type == 'Каркасные':
            wall_area = perimeter * height
            return wall_area * config['price_per_m2']
        elif wall_type == 'Брусовые':
            thickness = config['thickness']
            volume = perimeter * height * thickness
            return volume * config['price_per_m3']
        return 0

    @staticmethod
    def calculate_roof(data):
        roof_type = data['roof_type']
        config = COST_CONFIG['materials']['roof'][roof_type]
        width = data['width']
        length = data['length']
        
        if data['floors'] == 'Одноэтажный':
            slope = 25
        else:
            slope = 35
            
        roof_length = math.sqrt((width/2)**2 + (width/2 * math.tan(math.radians(slope)))**2)
        roof_area = 2 * roof_length * length * config['slope_factor']
        return roof_area * config['price_per_m2']

    @staticmethod
    def calculate_insulation(data):
        insulation_type = data['insulation_type']
        config = COST_CONFIG['materials']['insulation'][insulation_type]
        perimeter = 2 * (data['width'] + data['length'])
        height = data['height']
        
        wall_area = perimeter * height
        volume_walls = wall_area * config['density'] / 1000
        cost_walls = volume_walls * config['price_per_m3']
        
        roof_area = DimensionCalculator.calculate_roof(data) / COST_CONFIG['materials']['roof'][data['roof_type']]['price_per_m2']
        volume_roof = roof_area * config['density'] / 1000
        cost_roof = volume_roof * config['price_per_m3']
        
        return cost_walls + cost_roof

    @staticmethod
    def calculate_windows(data):
        count = data['window_count']
        return count * COST_CONFIG['materials']['windows']['price_per_unit']

    @staticmethod
    def calculate_doors(data):
        entrance = data['entrance_doors']
        interior = data['interior_doors']
        return (entrance * COST_CONFIG['materials']['doors']['входная']['price']) + (interior * COST_CONFIG['materials']['doors']['межкомнатная']['price'])

    @staticmethod
    def calculate_works(data):
        work_cost = 0
        perimeter = 2 * (data['width'] + data['length'])
        height = data['height']
        
        work_cost += perimeter * 0.5 * 1.2 * COST_CONFIG['work']['excavation']['price_per_m3']
        work_cost += perimeter * height * COST_CONFIG['work']['carpentry']['price_per_m2']
        return work_cost

class CostCalculator:
    @staticmethod
    def calculate_total(data):
        total = 0
        details = []
        
        # Фундамент
        foundation = DimensionCalculator.calculate_foundation(data)
        details.append(f"{EMOJI_MAP['foundation']} Фундамент: {foundation:,.0f}{STYLES['currency']}")
        
        # Стены
        walls = DimensionCalculator.calculate_walls(data)
        details.append(f"🧱 Стены: {walls:,.0f}{STYLES['currency']}")
        
        # Кровля
        roof = DimensionCalculator.calculate_roof(data)
        details.append(f"{EMOJI_MAP['roof']} Кровля: {roof:,.0f}{STYLES['currency']}")
        
        # Утепление
        insulation = DimensionCalculator.calculate_insulation(data)
        details.append(f"{EMOJI_MAP['insulation']} Утепление: {insulation:,.0f}{STYLES['currency']}")
        
        # Окна
        windows = DimensionCalculator.calculate_windows(data)
        details.append(f"{EMOJI_MAP['windows']} Окна: {windows:,.0f}{STYLES['currency']}")
        
        # Двери
        doors = DimensionCalculator.calculate_doors(data)
        details.append(f"{EMOJI_MAP['doors']} Двери: {doors:,.0f}{STYLES['currency']}")
        
        # Работы
        works = DimensionCalculator.calculate_works(data)
        details.append(f"🛠️ Работы: {works:,.0f}{STYLES['currency']}")
        
        # Суммирование
        total = sum([foundation, walls, roof, insulation, windows, doors, works])
        
        # Региональный коэффициент
        region_coeff = REGIONAL_COEFFICIENTS.get(data.get('region', 'Другой'), 1.0)
        total *= region_coeff
        details.append(f"{EMOJI_MAP['region']} Региональный коэффициент: ×{region_coeff:.1f}")
        
        # Скидки
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

# Обработчик вебхуков
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
