from groq import AsyncGroq
import base64
from scripts.AI_promt import context, ai_hints, pinduo_analyse_promt, taobao_analyse_promt, default_analyse_prompt

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
        
        if len(self.history[user_id]) > 11:
            # Сохраняем системную инструкцию (она всегда на 0 месте)
            system_prompt = self.history[user_id][0]
            # Берем только последние 10 сообщений
            last_messages = self.history[user_id][-10:]
            # Собираем новый список: Инструкция + последние 10 сообщений
            self.history[user_id] = [system_prompt] + last_messages

        try:
            completion = await self.client.chat.completions.create(
                model=self.aimodel,
                messages=self.history[user_id]
            )
            response = completion.choices[0].message.content
            self.history[user_id].append({"role": "assistant", "content": response})
            return response
        except Exception as e:
            return f"Ошибка: {e}"

    async def clear_context(self, user_id: int):
        self.history[user_id] = [{"role": "system", "content": context+ai_hints}]

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
            return f"Ошибка при анализе изображения: {e}"
        

    async def product_analysis(self, user_id: int, product_data: dict, market: str = None) -> str:
        if user_id not in self.history:
            await self.clear_context(user_id)
        if market == 'Pinduoduo':
            command = '/pindname'
            analyse_promt = pinduo_analyse_promt
        elif market == 'Taobao':
            command == '/taoimg'
            analyse_promt = taobao_analyse_promt
        else:
            command == 'для анализа'
            analyse_promt = default_analyse_prompt
        # Формируем сообщение с данными товара
        product_message = {
            "role": "user",
            "content": f"Запрос от команды {command}. {analyse_promt} - Данные о товаре --> {product_data}"
        }

        full_messages = self.history[user_id] + [product_message]

        try:
            completion = await self.client.chat.completions.create(
                messages=full_messages,
                model=self.aimodel
            )
            response = completion.choices[0].message.content
        
            # Записываем в историю запрос и ответ
            self.history[user_id].append({"role": "user", "content": f"[Анализ товара]: {product_data['title']}"})
            self.history[user_id].append({"role": "assistant", "content": response})
        
            return response
        except Exception as e:
            return f"Ошибка при анализе товара: {e}"
    @staticmethod
    def encode_image(image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode('utf-8')