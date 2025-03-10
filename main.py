import os
import logging
import threading
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
    'Калужская обл': 1,
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
    if question['key'] in ['area', 'terrace_area']:
        try:
            value = float(answer.replace(',', '.'))
            if 'max' in question and value > question['max']:
                return f"Максимальное значение: {question['max']} кв.м"
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
            elif question['key'] in ['area', 'terrace_area']:
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
        base_cost = CostCalculator._calculate_base_works(data)
        total += base_cost['total']
        details.extend(base_cost['details'])
        materials_cost = CostCalculator._calculate_materials(data)
        total += materials_cost['total']
        details.extend(materials_cost['details'])
        additional_cost = CostCalculator._calculate_additional(data)
        total += additional_cost['total']
        details.extend(additional_cost['details'])
        total = CostCalculator._apply_coefficients(data, total, details)
        return round(total, 2), details

    @staticmethod
    def _calculate_base_works(data):
        total = 0
        details = []
        floor_type = data.get('floors', 'Одноэтажный')
        area = float(data.get('area', 100))
        base_config = COST_CONFIG['work']['base']
        cost = area * base_config['price'] * base_config['floor_multiplier'][floor_type]
        total += cost
        details.append(f"{EMOJI_MAP['foundation']} <b>Основные работы ({floor_type})</b>: {cost:,.0f}{STYLES['currency']}")
        return {'total': total, 'details': details}

    @staticmethod
    def _calculate_materials(data):
        total = 0
        details = []
        area = float(data.get('area', 100))
        foundation = data.get('foundation')
        if foundation and foundation != 'Пропустить':
            cost = COST_CONFIG['materials']['foundation'][foundation]
            total += cost
            details.append(f"{EMOJI_MAP['foundation']} Фундамент ({foundation}): {cost:,.0f}{STYLES['currency']}")
        roof = data.get('roof')
        if roof and roof != 'Пропустить':
            roof_area = CostCalculator._calculate_roof_area(data)
            cost = roof_area * COST_CONFIG['materials']['roof'][roof]
            total += cost
            details.append(f"{EMOJI_MAP['roof']} Кровля ({roof}): {cost:,.0f}{STYLES['currency']}")
        insulation = data.get('insulation')
        if insulation and insulation != 'Пропустить':
            thickness = float(data.get('insulation_thickness', 150))
            material = COST_CONFIG['materials']['insulation'][insulation]
            cost = (thickness / 100) * area * material['price']
            total += cost
            details.append(f"{EMOJI_MAP['insulation']} Утеплитель ({insulation} {thickness}мм): {cost:,.0f}{STYLES['currency']}")
        for category in ['exterior', 'interior']:
            material = data.get(category)
            if material and material != 'Пропустить':
                cost = area * COST_CONFIG['materials'][category][material]
                total += cost
                details.append(f"{EMOJI_MAP[category]} {'Внешняя' if category == 'exterior' else 'Внутренняя'} отделка ({material}): {cost:,.0f}{STYLES['currency']}")
        return {'total': total, 'details': details}

    @staticmethod
    def _calculate_additional(data):
        total = 0
        details = []
        windows = int(data.get('windows_count', 0))
        entrance_doors = int(data.get('entrance_doors', 0))
        inner_doors = int(data.get('inner_doors', 0))
        cost = (
            windows * COST_CONFIG['materials']['windows'] +
            entrance_doors * COST_CONFIG['materials']['doors']['входная'] +
            inner_doors * COST_CONFIG['materials']['doors']['межкомнатная']
        )
        total += cost
        details.append(f"{EMOJI_MAP['windows']} Окна: {windows} шт. - {windows*COST_CONFIG['materials']['windows']:,.0f}{STYLES['currency']}")
        details.append(f"{EMOJI_MAP['doors']} Входные двери: {entrance_doors} шт. - {entrance_doors*COST_CONFIG['materials']['doors']['входная']:,.0f}{STYLES['currency']}")
        details.append(f"{EMOJI_MAP['doors']} Межкомнатные двери: {inner_doors} шт. - {inner_doors*COST_CONFIG['materials']['doors']['межкомнатная']:,.0f}{STYLES['currency']}")
        terrace_area = float(data.get('terrace_area', 0))
        if terrace_area > 0:
            cost = terrace_area * COST_CONFIG['work']['terrace']
            total += cost
            details.append(f"{EMOJI_MAP['terrace']} Терраса ({terrace_area} м²): {cost:,.0f}{STYLES['currency']}")
        return {'total': total, 'details': details}

    @staticmethod
    def _apply_coefficients(data, total, details):
        region = data.get('region', 'Другой')
        region_coeff = REGIONAL_COEFFICIENTS.get(region, 1.0)
        total *= region_coeff
        details.append(f"{EMOJI_MAP['region']} Региональный коэффициент ({region}): ×{region_coeff}")
        selected_items = sum(1 for k in data if data.get(k) and k not in ['area', 'floors', 'region'])
        if selected_items > 5:
            total *= 0.9
            details.append(f"🎁 Скидка за комплексный заказ: 10%")
        area = float(data.get('area', 100))
        if area > 200:
            total *= 0.95
            details.append(f"🎁 Скидка за большую площадь: 5%")
        return total

    @staticmethod
    def _calculate_roof_area(data):
        area = float(data.get('area', 100))
        floors = data.get('floors', 'Одноэтажный')
        if floors == 'Двухэтажный':
            return area * 0.6
        elif floors == 'С мансардой':
            return area * 1.1
        return area * 0.8

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
    threading.Thread(target=self_ping, daemon=True).start()
    bot_thread = threading.Thread(target=bot.polling, kwargs={'none_stop': True})
    bot_thread.daemon = True
    bot_thread.start()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
