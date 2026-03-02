from groq import AsyncGroq
import base64
import json
from scripts.AI_promt import context, ai_hints, pinduo_analyse_prompt, taobao_analyse_prompt, default_analyse_prompt
import logging

logger = logging.getLogger(__name__)

class GroqAI:
    def __init__(self, api_key: str, model: str):
        self.client = AsyncGroq(api_key=api_key)
        self.history = {}
        self.aimodel = model

    async def get_response(self, user_id: int, text: str) -> str:
        # Инициализация истории
        if user_id not in self.history:
            await self.clear_context(user_id)
        
        self.history[user_id].append({"role": "user", "content": text})
        
        if len(self.history[user_id]) > 12:
            system_messages = self.history[user_id][:2]
            last_messages = self.history[user_id][-10:]
            self.history[user_id] = system_messages + last_messages

        try:
            completion = await self.client.chat.completions.create(
                model=self.aimodel,
                messages=self.history[user_id],
                temperature=0.4
            )
            response = completion.choices[0].message.content
            self.history[user_id].append({"role": "assistant", "content": response})
            return response
        except Exception as e:
            logger.error(f"Ошибка при получение ответа от Groq для текстового запроса")
            return f"Ошибка: {e}"

    async def clear_context(self, user_id: int):
        self.history[user_id] = [
            {"role": "system", "content": context},
            {"role": "system", "content": ai_hints}]

    async def image_analysis(self, user_id: int, image_bytes: bytes, user_text: str = None) -> str:
        if user_id not in self.history:
            await self.clear_context(user_id)

        base64_image = self.encode_image(image_bytes)
    
        # Текст пользователя или дефолтный вопрос
        prompt = user_text or "Что изображено на этом фото? Скорее всего это что то связанное с товаром в Pinduoduo, Taobao или Temu, проанализируй его если есть китайский текст то переведи на русский."

        # Формируем сообщение с картинкой
        image_message = {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }

        # ВАЖНО: Передаем историю + текущее фото
        full_messages = self.history[user_id] + [image_message]

        try:
            completion = await self.client.chat.completions.create(
                messages=full_messages,
                model=self.aimodel
            )
            response = completion.choices[0].message.content
        
            # Записываем в историю уже текстовое описание, чтобы не хранить тяжелые картинки
            self.history[user_id].append({"role": "user", "content": f"[Фото товара]: {prompt}"})
            self.history[user_id].append({"role": "assistant", "content": response})
        
            return response
        except Exception as e:
            logger.error(f"Ошибка при получение ответа от Groq для Фото запроса")
            return f"Ошибка при анализе изображения: {e}"
        

    async def product_analysis(self, user_id: int, product_data: dict, market: str = None) -> str:
        print(product_data)
        if user_id not in self.history:
            await self.clear_context(user_id)
        if market == 'Pinduoduo':
            command = '/pindname'
            analyse_promt = pinduo_analyse_prompt
        elif market == 'Taobao':
            command = '/taoimg'
            analyse_promt = taobao_analyse_prompt
        else:
            command = 'для анализа'
            analyse_promt = default_analyse_prompt
        # Формируем сообщение с данными товара
        product_message = {
            "role": "system",
            "content": (f"Запрос от команды {command}.\n"
                        f"{analyse_promt}\n\n"
                        f"Данные о товаре (JSON):\n"
                        f"{json.dumps(product_data, ensure_ascii=False, indent=2)}")}

        full_messages = self.history[user_id] + [product_message]

        try:
            completion = await self.client.chat.completions.create(
                messages=full_messages,
                model=self.aimodel
            )
            response = completion.choices[0].message.content
        
            # Записываем в историю запрос и ответ
            self.history[user_id].append({"role": "user", "content": f"[Анализ товара]: {product_data.get('title', 'тут должно было быть название товара')}"})
            self.history[user_id].append({"role": "assistant", "content": response})
        
            return response
        except Exception as e:
            logger.error(f"Ошибка при получение ответа от Groq для запроса Анализа")
            return f"Ошибка при анализе товара: {e}"
    @staticmethod
    def encode_image(image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode('utf-8')