import aiohttp
import re
import logging


class PinduoduoService:
    def __init__(self, api_keys: list):
        self.url = "https://pinduoduo1.p.rapidapi.com/pinduoduo/search"
        self.host = "pinduoduo1.p.rapidapi.com"
        self.keys = api_keys 
        self.current_key_idx = 0

    def _get_headers(self):
        # Берем текущий ключ и имитируем браузер
        headers = {
            "x-rapidapi-key": self.keys[self.current_key_idx],
            "x-rapidapi-host": self.host,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        return headers

    def _rotate_key(self):
        self.current_key_idx = (self.current_key_idx + 1) % len(self.keys)
        logging.info(f"Переключились на API ключ №{self.current_key_idx}")

    async def fetch_product(self, keyword: str):
        """Основной метод поиска товара"""
        params = {"keyword": keyword, "sortType": "default"} # Ставим sales для надежности
        
        async with aiohttp.ClientSession() as session:
            for _ in range(len(self.keys)): # Пробуем ключи по очереди, если лимит исчерпан
                try:
                    async with session.get(self.url, headers=self._get_headers(), params=params, timeout=10) as resp:
                        if resp.status == 429: # Лимит исчерпан
                            self._rotate_key()
                            continue
                        
                        result = await resp.json()
                        
                        if result.get("success") and result["data"]["items"]:
                            item = result["data"]["items"][0] # Берем первый товар
                            return self._format_data(item)
                        return None
                        
                except Exception as e:
                    logging.error(f"Ошибка запроса к Pinduoduo: {e}")
                    return None
        return None

    def _format_data(self, item: dict):
        """Чистим данные: цену в юани, картинку в https"""
        return {
            "image": "https:" + item.get("thumb_url", None),
            "Название": item.get("goods_name"),
            "Тэг": item.get("tag"),
            "Продажи": item.get("side_sales_tip", "Нет данных"),
            "Цена_юань": item.get("default_price", 0) / 100,
            "Ссылка": item.get("product_url"),
            "id": item.get("goods_id")
        }