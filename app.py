import logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, ConversationHandler, PicklePersistence
import os

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния диалога
AREA, FLOORS, FOUNDATION, MATERIAL, FINISH = range(5)

# Коэффициенты для расчета
FOUNDATION_COEFF = {'ленточный': 1.0, 'свайный': 1.1, 'плитный': 1.2}
MATERIAL_COEFF = {'дерево': 1.0, 'ОСП': 1.1, 'кирпич': 1.3}
FINISH_COEFF = {'эконом': 1.0, 'стандарт': 1.2, 'премиум': 1.5}

BASE_PRICE = 10000  # Базовая стоимость за кв.м

# Инициализация бота и persistence
TOKEN = os.getenv('TELEGRAM_TOKEN')
bot = Bot(TOKEN)
persistence = PicklePersistence(filename='bot_data')

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

def start(update: Update, context) -> int:
    update.message.reply_text(
        'Добро пожаловать! Я помогу рассчитать стоимость строительства каркасного дома. '
        'Начнем с первого вопроса: \n\n'
        'Какова площадь дома (кв. м)?'
    )
    return AREA

def get_area(update: Update, context) -> int:
    try:
        area = float(update.message.text)
        if area <= 0:
            raise ValueError
        context.user_data['area'] = area
        update.message.reply_text('Сколько этажей будет в доме?')
        return FLOORS
    except ValueError:
        update.message.reply_text('Пожалуйста, введите корректное число больше нуля.')
        return AREA

def get_floors(update: Update, context) -> int:
    try:
        floors = int(update.message.text)
        if floors < 1:
            raise ValueError
        context.user_data['floors'] = floors
        update.message.reply_text('Выберите тип фундамента: ленточный, свайный, плитный.')
        return FOUNDATION
    except ValueError:
        update.message.reply_text('Пожалуйста, введите целое число больше нуля.')
        return FLOORS

def get_foundation(update: Update, context) -> int:
    foundation = update.message.text.lower()
    if foundation not in FOUNDATION_COEFF:
        update.message.reply_text('Пожалуйста, выберите из предложенных: ленточный, свайный, плитный.')
        return FOUNDATION
    context.user_data['foundation'] = foundation
    update.message.reply_text('Выберите материал стен: дерево, ОСП, кирпич.')
    return MATERIAL

def get_material(update: Update, context) -> int:
    material = update.message.text.lower()
    if material not in MATERIAL_COEFF:
        update.message.reply_text('Пожалуйста, выберите из предложенных: дерево, ОСП, кирпич.')
        return MATERIAL
    context.user_data['material'] = material
    update.message.reply_text('Выберите уровень отделки: эконом, стандарт, премиум.')
    return FINISH

def get_finish(update: Update, context) -> int:
    finish = update.message.text.lower()
    if finish not in FINISH_COEFF:
        update.message.reply_text('Пожалуйста, выберите из предложенных: эконом, стандарт, премиум.')
        return FINISH
    context.user_data['finish'] = finish

    # Расчет стоимости
    area = context.user_data['area']
    floors = context.user_data['floors']
    foundation = context.user_data['foundation']
    material = context.user_data['material']
    finish = context.user_data['finish']

    total = BASE_PRICE * area * floors * FOUNDATION_COEFF[foundation] * MATERIAL_COEFF[material] * FINISH_COEFF[finish]
    total = round(total, 2)

    update.message.reply_text(f'Стоимость строительства вашего дома: {total} руб.\n\nСпасибо, что воспользовались нашим ботом!')
    return ConversationHandler.END

def cancel(update: Update, context) -> int:
    update.message.reply_text('Расчет отменен.')
    return ConversationHandler.END

if __name__ == '__main__':
    # Настройка диспетчера
    dispatcher = Dispatcher(bot, None, workers=4, use_context=True, persistence=persistence)
    
    # Регистрация обработчиков
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            AREA: [MessageHandler(Filters.text & ~Filters.command, get_area)],
            FLOORS: [MessageHandler(Filters.text & ~Filters.command, get_floors)],
            FOUNDATION: [MessageHandler(Filters.text & ~Filters.command, get_foundation)],
            MATERIAL: [MessageHandler(Filters.text & ~Filters.command, get_material)],
            FINISH: [MessageHandler(Filters.text & ~Filters.command, get_finish)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        name='calculation_conversation',
        persistent=True
    )
    dispatcher.add_handler(conv_handler)
    
    # Запуск Flask приложения
    app.run(port=5000)