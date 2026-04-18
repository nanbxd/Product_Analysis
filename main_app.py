import asyncio
import logging
from aiogram.exceptions import TelegramBadRequest
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters.command import Command, CommandObject
from aiogram.enums.dice_emoji import DiceEmoji
from datetime import datetime
from config_reader import config
from scripts.AI_logic import GroqAI
from aiogram.client.default import DefaultBotProperties
import html
from scripts.api_service import PinduoduoService, TaobaoService
from aiogram.filters import Command
from scripts.states_app import SearchState
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from limits import check_limit, increment_limit, get_remaining, get_reset_time
from scripts.logger_config import setup_logging
#python -m scripts.main_app
setup_logging()
logger = logging.getLogger(__name__)
logger.info("Приложение запущено")

rapid_services_keys = [config.rapidapi_key1.get_secret_value(),
                        config.rapidapi_key2.get_secret_value(), 
                        config.rapidapi_key3.get_secret_value()]

pdd_service = PinduoduoService(api_keys=rapid_services_keys)
tao_service = TaobaoService(api_keys=rapid_services_keys)
client_groq = GroqAI(api_key=config.ai_groq_api.get_secret_value(), model=config.ai_groq_model.get_secret_value()) 
bot = Bot(token=config.tovarnyu_token.get_secret_value(), 
        default=DefaultBotProperties(parse_mode= 'HTML'))
dp = Dispatcher()

@dp.message(Command("start")) 
async def cmd_start(message: types.Message):
   logger.info(f"Пользователь {message.from_user.id} вызвал /start")
   await message.answer(
    "👋 <b>Привет! Я ваш персональный ассистент по покупкам на маркетплейсах Китая.</b>\n\n"
    "Я помогу проанализировать товары и выбрать лучшее качество. Вот что я умею:\n\n"
    "📸 <b>Поиск по фото (Taobao):</b>\n"
    "Отправьте команду <code>/taoimg</code>, а затем — <b>фотографию</b> товара. "
    "Я найду его и проведу глубокий анализ.\n\n"
    "🔍 <b>Поиск по названию (Pinduoduo):</b>\n"
    "Отправьте команду <code>/pindname</code> вместе с <b>названием</b> товара. "
    "Мой ИИ проанализирует карточки и поможет с выбором.\n\n"
    "💡 <i>Просто выберите нужную команду и следуйте инструкциям!</i>",
    parse_mode="HTML"
)



@dp.message(Command("cancel"))
@dp.message(F.text == "❌ Отмена") # Ловим текст с кнопки
async def cancel_handler(message: types.Message, state: FSMContext):
    logger.info(f"Пользователь {message.from_user.id} вызвал /cancel ")
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активных действий.", reply_markup=ReplyKeyboardRemove())
        return
    await state.clear()
    # ReplyKeyboardRemove() убирает кнопку отмены и возвращает обычную клаву
    await message.answer("Действие отменено.", reply_markup=ReplyKeyboardRemove())


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    logger.info(f"Пользователь {message.from_user.id} вызвал /help")
    await message.answer(
        "<b>🤖 Товарный AI-бот</b>\n"
        "Помогаю находить и анализировать товары с китайских маркетплейсов.\n\n"

        "<b>🔎 Поиск товара:</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "• <b>/pindname название</b>\n"
        "  Поиск товара по названию (Pinduoduo)\n"
        "  <code>/pindname 美式复古水洗弯刀牛仔</code>\n\n"

        "• <b>/taoimg</b>\n"
        "  Поиск товара по фото (Taobao)\n"
        "  После команды просто отправьте изображение.\n\n"

        "<b>🧠 AI функции:</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "• Просто отправьте текст — я отвечу и помогу разобраться.\n"
        "• Отправьте фото с подписью — сделаю анализ изображения.\n\n"

        "<b>📊 После выбора товара вы получите:</b>\n"
        "• Название\n"
        "• Цену\n"
        "• Количество заказов\n"
        "• Рейтинг\n"
        "• Отзывы\n"
        "• Рекомендацию к покупке\n\n"

        "<b>❌ Отмена действия:</b>\n"
        "• /cancel — остановить текущий поиск\n\n"

        "🚀 Бот находится в стадии активной разработки."
    )

@dp.message(Command('pindname'))
async def cmd_pindname(message: types.Message, command: CommandObject, state: FSMContext):
    logger.info(f"Пользователь {message.from_user.id} вызвал /pindname")
    # лимит проверка пиндуодуо
    if not await check_limit(message.from_user.id, "pindu"):
        reset_at = await get_reset_time(message.from_user.id, "pindu")
        await message.answer("⚠️ Лимит анализов Pinduoduo на сегодня достигнут (4).\n"
            f"⏳ Лимит восстановится в:\n"
            f"<b>{reset_at['almaty']}</b> <i>(ALMATY)</i> / <b>{reset_at['moscow']}</b> <i>(MOSCOW)</i>")
        return
    # 2. Идем в API
    if command.args is None:
        await message.answer("Пожалуйста, отправьте команду в формате:\n"
                            "/pindname <i>название товара</i>")
        return
    await bot.send_chat_action(message.chat.id, action="typing")
    await increment_limit(message.from_user.id, "pindu")
    products = await pdd_service.fetch_product(command.args)
    if products and isinstance(products, list):
        # Сохраняем список и индекс в FSM
        await state.update_data(products=products, current_index=0)
        # Устанавливаем состояние поиска (чтобы калбэки понимали, в каком контексте работают)
        await state.set_state(SearchState.waiting_for_photo) 
        # Показываем первый товар через общую функцию
        await show_product_selection(message, products[0], 0)
    else:
        await message.answer("Ничего не нашел, возможно вы отправили некорректное название или же произошла ошибка от серверной части. Попробуйте еще раз или отправьте фото на товар с Taobao для анализа.")



@dp.message(Command('clear_context'))
async def cmd_clear_context(message: types.Message):
    logger.info(f"Пользователь {message.from_user.id} вызвал /clear_context")
    await message.reply('-- Память ИИ сброшена --')
    await client_groq.clear_context(user_id=message.from_user.id)

@dp.message(Command("taoimg"))
async def cmd_taoimg(message: types.Message, state: FSMContext):
    logger.info(f"Пользователь {message.from_user.id} вызвал /taoimg")
    # проверка лимита на Taobao
    if not await check_limit(message.from_user.id, "tao"):
        reset_at = await get_reset_time(message.from_user.id, "tao")
        await message.answer("⚠️ Лимит анализов Taobao на сегодня достигнут (3).\n"
            f"⏳ Лимит восстановится в:\n"
            f"<b>{reset_at['almaty']}</b> <i>(ALMATY)</i> / <b>{reset_at['moscow']}</b> <i>(MOSCOW)</i>")
        return
    # Создаем кнопку отмены
    kb = [
        [KeyboardButton(text="❌ Отмена")]
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True, # Делает кнопки маленькими и аккуратными
        one_time_keyboard=True # Кнопка скроется после одного нажатия
    )

    await message.answer(
        "Отлично! Теперь отправьте фото товара.\nИли нажмите кнопку ниже для отмены:",
        reply_markup=keyboard # Показываем кнопки
    )
    await state.set_state(SearchState.waiting_for_photo)


@dp.message(SearchState.waiting_for_photo, F.photo | F.document.mime_type.startswith("image/"))
async def tao_img_handler(message: types.Message, state: FSMContext, bot: Bot): # Добавили state
    logger.info(f"Пользователь {message.from_user.id} отправил фото для анализа Taobao")
    await increment_limit(message.from_user.id, "tao")
    await message.answer("Ищу товары... подождите.")
    await bot.send_chat_action(message.chat.id, action="typing")
    # 1. Получаем список из 10 товаров
        # 1. Получаем file_id
    if message.photo:
        file_id = message.photo[-1].file_id
    else:
        file_id = message.document.file_id

    try:
        # 3. Скачиваем файл в оперативную память (BytesIO)
        file = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file.file_path)

        # Теперь передаем в сервис
        products = await tao_service.tao_imginfo(cloud_name = config.cloud_name.get_secret_value(),
                                                 upload_preset="telegram_upload",
                                                 img=file_bytes.read())

        
        if not products:
            await message.answer("Ничего не нашел. Попробуйте еще раз с другой фотографией", reply_markup=ReplyKeyboardRemove())
            await state.clear()
            return
        
        # 2. Сохраняем всё в состояние
        await state.update_data(products=products, current_index=0)
    
        # 3. Показываем первый товар
        await show_product_selection(message, products[0], 0)

    except Exception as e:
        await message.answer(f"Произошла ошибка при обработке изображения: {e}", reply_markup=ReplyKeyboardRemove())
        await state.clear()


# Добавьте этот обработчик, чтобы ловить мусор
@dp.message(SearchState.waiting_for_photo)
async def tao_invalid_handler(message: types.Message):
    logger.info(f"Пользователь {message.from_user.id} отправил не фото")
    await message.answer("Пожалуйста, отправьте фото. Чтобы отменить поиск, используйте /cancel")

@dp.message(F.photo | F.document.mime_type("image/*"))
async def ai_img_handler(message: types.Message, bot: Bot):
    logger.info(f"Пользователь {message.from_user.id} отправил фото для ии")
    await bot.send_chat_action(message.chat.id, action="typing")
    if not await check_limit(message.from_user.id, "img"):
        reset_at = await get_reset_time(message.from_user.id, "img")

        await message.answer(
            f"❌ Вы исчерпали дневной лимит обращений по фото к ИИ\n"
            f"⏳ Лимит восстановится в:\n"
            f"<b>{reset_at['almaty']}</b> <i>(ALMATY)</i> / <b>{reset_at['moscow']}</b> <i>(MOSCOW)</i>"
        )
        return
    
    await increment_limit(message.from_user.id, "img")
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    else:
        return

    text = message.caption
    # 3. Скачиваем файл в оперативную память (BytesIO)
    file_info = await bot.get_file(file_id)
    photo_bytes_io = await bot.download_file(file_info.file_path)
    
    # 4. Превращаем BytesIO в обычные bytes
    photo_bytes = photo_bytes_io.read()


    # Передаем и user_id (для истории), и сами байты
    response = await client_groq.image_analysis(
        user_id=message.from_user.id, 
        image_bytes=photo_bytes,
        user_text=text
    )
    try:
        await message.answer(response, parse_mode="Markdown")
    except Exception:
        await message.answer(response, parse_mode=None)


# -------------                          ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ --------

# --- ФУНКЦИЯ ОТРИСОВКИ ТОВАРА ---
async def show_product_selection(message: types.Message, product: dict, index: int):
    logger.info(f"Пользователь {message.from_user.id} получил карту товара")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, это он", callback_data="confirm_prod"),
            InlineKeyboardButton(text="❌ Нет, дальше", callback_data="next_prod")
        ],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_search")]
    ])
    photo_url = product.get('image')
    product_name = product.get('title', 'Unknown')
    product_link = product.get('link', 'not-found')
    text = f'Название: {product_name}/n\
            Ссылка: {product_link}\n\nЭто тот товар, который вы искали?'
    try:
        await message.answer_photo(photo_url, reply_markup=kb, caption= text, parse_mode=None)
    except TelegramBadRequest:
        # Если фото не загрузилось, просто игнорируем или пишем лог
        await message.answer(
            "⚠️ Изображение недоступно", 
            parse_mode=None)
        print(f"Не удалось загрузить фото")
        await message.answer(text, reply_markup=kb, parse_mode= None)

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="pindname", description="Поиск товара по названию (Pinduoduo)"),
        BotCommand(command="taoimg", description="Поиск товара по фото (Taobao)"),
        BotCommand(command="help", description="Справка по боту"),
        BotCommand(command="cancel", description="Отменить текущее действие"),
    ]
    await bot.set_my_commands(commands)
# ---------------                         CALLBACKS ------------

# --- ОБРАБОТЧИК КНОПКИ "Отмена" ---
@dp.callback_query(F.data == "cancel_search")
async def next_product(callback: types.CallbackQuery, state: FSMContext):
    logger.info(f"Пользователь {callback.message.from_user.id} отменил запрос")
    await callback.message.delete()
    await callback.message.answer("Поиск товара отменен.", reply_markup=ReplyKeyboardRemove())
    await state.clear()
# --- ОБРАБОТЧИК КНОПКИ "НЕТ, ДАЛЬШЕ" ---
@dp.callback_query(F.data == "next_prod")
async def next_product(callback: types.CallbackQuery, state: FSMContext):
    logger.info(f"Пользователь {callback.message.from_user.id} пролистнул")
    data = await state.get_data()
    products = data.get('products', [])
    new_index = data.get('current_index', 0) + 1
    
    if new_index < len(products):
        await state.update_data(current_index=new_index)
        # Редактируем старое сообщение, чтобы не спамить новыми
        await callback.message.delete()
        await show_product_selection(callback.message, products[new_index], new_index)
    else:
        await callback.message.answer("Это были все найденные товары. Попробуйте другое фото.")
        await state.clear()
    await callback.answer()

# --- ОБРАБОТЧИК КНОПКИ "ДА, ОН" ---
@dp.callback_query(F.data == "confirm_prod")
async def confirm_product(callback: types.CallbackQuery, state: FSMContext):
    logger.info(f"Пользователь {callback.message.from_user.id} нашел свой товар, начинается глубокий анализ")
    await callback.answer()
    data = await state.get_data()
    product = data['products'][data['current_index']]
    
    await callback.message.answer(f"Отлично! Начинаю глубокий анализ товара")
    await bot.send_chat_action(callback.message.chat.id, action="typing")
    market = product.get('market')
    if market == 'Pinduoduo':
        response = await client_groq.product_analysis(
            user_id=callback.message.from_user.id,
            product_data=product, market=market)
    elif market == 'Taobao':
        details = await tao_service.get_item_detail(product['id'], product['idStr'])
        response = await client_groq.product_analysis(
            user_id=callback.message.from_user.id,
            product_data=details, market=market)
    if len(response) > 4096:
        for x in range(0, len(response), 4096):
            await callback.message.answer(response[x:x+4096])
    else:
        try:
            await callback.message.answer(response, parse_mode= 'Markdown')
        except:
            await callback.message.answer(response, parse_mode=None)
    await state.clear()

@dp.message(F.text)
async def ai_message_handler(message: types.Message):
    logger.info(f"Пользователь {message.from_user.id} написал сообщение для ии")
    await bot.send_chat_action(message.chat.id, action="typing")
    if not await check_limit(message.from_user.id, "msg"):
        reset_at = await get_reset_time(message.from_user.id, "msg")

        await message.answer(
            f"❌ Вы исчерпали дневной лимит обращений по тексту к ИИ\n"
            f"⏳ Лимит восстановится в:\n"
            f"<b>{reset_at['almaty']}</b> <i>(ALMATY)</i> / <b>{reset_at['moscow']}</b> <i>(MOSCOW)</i>"
        )
        return
    
    await increment_limit(message.from_user.id, "msg")
    # Отправляем запрос в Groq
    response = await client_groq.get_response(
        user_id=message.from_user.id,
        text=message.md_text,
    )

    try:
        await message.answer(response, parse_mode="Markdown")
    except Exception:
        await message.answer(response, parse_mode=None)

from aiohttp import web
import asyncio

# Функция-затычка для Render
async def health_check(request):
    return web.Response(text="Bot is alive")

async def start_health_check():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    # Указываем порт 10000 напрямую
    site = web.TCPSite(runner, "0.0.0.0", 7860)
    await site.start()


# Запуск процесса поллинга новых апдейтов
async def main():
    await set_commands(bot)
    asyncio.create_task(start_health_check())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())