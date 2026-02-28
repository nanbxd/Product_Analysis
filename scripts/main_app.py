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
from scripts.api_service import PinduoduoService
#python -m scripts.main_app


logging.basicConfig(level=logging.INFO)
pdd_service = PinduoduoService(api_keys=[config.pinduoapi_key1.get_secret_value(), config.pinduoapi_key2.get_secret_value()])
client_groq = GroqAI(api_key=config.ai_groq_api.get_secret_value(), model=config.ai_groq_model.get_secret_value())
bot = Bot(token=config.tovarnyu_token.get_secret_value(), 
        default=DefaultBotProperties(parse_mode= 'HTML'))
dp = Dispatcher()

@dp.message(Command("start")) 
async def cmd_start(message: types.Message):
    await message.answer(f"Добро пожаловать! Отправьте мне комманду <b>/anal</b> с ссылкой на товар <b>/Taobao</b> или <b>Temu</b>. \n Или же команду <b>/pindname</b> с названием товара Pinduoduo ,и я сделаю анализ и помогу вам с выбором")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
    "<b>🔍 Инструкция по анализу товара на Маркетплейсах: Pinduoduo, Taobao, Temu</b>\n\n"
    "Чтобы получить детальный отчет, отправьте команду в формате:\n"
    "<code>/anal https://mobile.yangkeduo.com</code> -- для Taobao или Temu\n\n"
    "<code>/pindname 美式复古水洗弯刀牛仔</code> -- для Pinduoduo\n\n"
    "<b>📊 Пример того, что вы получите:</b>\n"
    "━━━━━━━━━━━━━━━━━━\n"
    "<b>📦 Название:</b> Худи ZARA (oversize)\n"
    "<b>💰 Цена:</b> 4 900 ₸ / 70 ¥\n"
    "<b>📈 Заказов:</b> 1 000+\n"
    "<b>⭐️ Рейтинг:</b> 4.5 / 5.0\n"
    "<b>💬 Отзывов:</b> 500 шт.\n\n"
    "<b>💡 Советы покупателей:</b>\n"
    "• <i>«Ткань плотная, идет размер в размер»</i>\n"
    "• <i>«Цвет как на фото, рекомендую к покупке»</i>\n\n"
    "<b>✅ Вердикт:</b> Рекомендуется к покупке"
)

@dp.message(Command('pindname'))
async def cmd_pindname(message: types.Message, command: CommandObject):
    await bot.send_chat_action(message.chat.id, action="typing")
    # 2. Идем в API
    if command.args is None:
        await message.answer("Пожалуйста, отправьте команду в формате: /pindname <название товара>", parse_mode= None)
        return
    product = await pdd_service.fetch_product(command.args)
    
    if product:
        photo_url = None
        if product.get('image'):
            photo_url = product['image']
            product.pop('image') 
        response = await client_groq.product_analysis(
        user_id=message.from_user.id,
        product_data=product)
        try:
            await message.answer_photo(photo_url)
        except TelegramBadRequest:
            # Если фото не загрузилось, просто игнорируем или пишем лог
            await message.answer(
                "⚠️ Изображение недоступно", 
                parse_mode=None)
            print(f"Не удалось загрузить фото")
        try:
            await message.answer(response, parse_mode="Markdown")
        except Exception:
            await message.answer(response, parse_mode=None)
    else:
        await message.answer("Ничего не нашел, возможно вы отправили некорректное название или же произошла ошибка от серверной части. Попробуйте еще раз или отправьте ссылку на товар с Taobao или Temu для анализа.")


@dp.message(Command('anal'))
async def cmd_anal(message: types.Message, command: CommandObject):
    await bot.send_chat_action(message.chat.id, action="typing")
    response = await client_groq.get_response(
        user_id=message.from_user.id,
        text=message.md_text,
    )
    
    url = None
    entities = message.entities or []

    for item in entities:
        if item.type in ["url", "text_link"]:
            url = item.extract_from(message.text)
            break
    if not url:
        url = command.args
    if not url:
        await message.answer("Пожалуйста, отправьте команду в формате: /anal <ссылка на товар>", parse_mode= None)
        return
    if not url.startswith("http"):
        await message.answer(f"Похоже, <b>{html.quote(url)}</b> не является ссылкой. Проверьте формат.")
        return

    await message.answer('-- МЕТОД АНАЛИЗА ВСЕ ЕЩЕ В РАЗРАБОТКЕ, ВЕРНИТЕСЬ ПОЗЖЕ ЛИБО ВОСПОЛЬЗУЙТЕСЬ /pindname для анализа товаров с PINDUODUO --')


@dp.message(Command('clear_context'))
async def cmd_clear_context(message: types.Message):
    await message.reply('-- Память ИИ сброшена --')
    await client_groq.clear_context(user_id=message.from_user.id)

@dp.message(F.text)
async def handle_message(message: types.Message):
    await bot.send_chat_action(message.chat.id, action="typing")
    # Отправляем запрос в Groq
    response = await client_groq.get_response(
        user_id=message.from_user.id,
        text=message.md_text,
    )

    try:
        await message.answer(response, parse_mode="Markdown")
    except Exception:
        await message.answer(response, parse_mode=None)

@dp.message(F.photo | F.document.mime_type("image/*"))
async def handle_photo(message: types.Message, bot: Bot):
    await bot.send_chat_action(message.chat.id, action="typing")

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

# Запуск процесса поллинга новых апдейтов
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())