import aiohttp
import asyncio
import base64
import logging
from deep_translator import GoogleTranslator
loggerPind = logging.getLogger("PinduoduoService")
loggerTao = logging.getLogger("TaobaoService")

class PinduoduoService:
    def __init__(self, api_keys: list):
        self.url = "https://pinduoduo1.p.rapidapi.com/pinduoduo/search"
        self.host = "pinduoduo1.p.rapidapi.com"
        self.keys = api_keys 
        self.current_key_idx = 0
        self._session = None

    async def get_session(self):
        # Создаем сессию только когда она реально нужна внутри асинхронного метода
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    def _get_headers(self):
        # Берем текущий ключ и имитируем браузер
        headers = {
            "x-rapidapi-key": self.keys[self.current_key_idx],
            "x-rapidapi-host": self.host,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        return headers

    def _rotate_key(self):
        old_key = self.current_key_idx
        self.current_key_idx = (self.current_key_idx + 1) % len(self.keys)
        loggerPind.info(f"API лимит исчерпан. Переключились с ключа №{old_key} на ключ №{self.current_key_idx}")

    async def translateword(self, text):
        loggerPind.info('translate сработал')
        try:
            # Запускаем синхронный перевод в отдельном потоке, чтобы не блокировать бота
            search_query = await asyncio.to_thread(
                lambda: GoogleTranslator(source='auto', target='zh-CN').translate(text)
            )
            loggerPind.info(f'Результат перевода: {search_query}')
            return search_query
        except Exception as e:
            loggerPind.error(f'Ошибка при переводе запроса: {e}')
            return text

    async def fetch_product(self, keyword: str):
        """Основной метод поиска товара"""
        truekeyword = await self.translateword(keyword)
        params = {"keyword": truekeyword, "sortType": "default"} # Ставим sales для надежности
        session = await self.get_session()
        for _ in range(len(self.keys)): # Пробуем ключи по очереди, если лимит исчерпан
            try:
                async with session.get(self.url, headers=self._get_headers(), params=params, timeout=10) as resp:
                    loggerPind.info(f"Pinduoduo запрос: {resp.url}, статус: {resp.status}")
                    if resp.status == 429: 
                        self._rotate_key()
                        continue
                    try:
                        result = await resp.json()
                        loggerPind.info(f"Pinduoduo ответ (первые 500 символов): {str(result)[:500]}")
                    except Exception as e_json:
                        loggerPind.error(f"Ошибка парсинга JSON Pinduoduo: {e_json}")
                        return None
                    if result.get("success") and result["data"]["items"]:
                        products = result["data"]["items"]
                        responselist = []
                        for prod in products:
                            responselist.append(self._format_data(prod))
                        return responselist
                    return None
                

            except Exception as e:
                loggerPind.error(f"Ошибка запроса к Pinduoduo: {e}")
                return None
        return None

    def _format_data(self, item: dict):
        """Чистим данные: цену в юани, картинку в https"""
        return {
            "image": f"https:{item.get('thumb_url', None)}",
            "title": item.get("goods_name"),
            "tag": item.get("tag"),
            "sales": item.get("side_sales_tip", "Нет данных"),
            "price_yuan": item.get("default_price", 0) / 100,
            "link": item.get("product_url"),
            "id": item.get("goods_id"),
            'market': 'Pinduoduo'
        }


class TaobaoService:
    def __init__(self, api_keys: list):
        self.host = "taobao-datahub.p.rapidapi.com"
        self.keys = api_keys 
        self.current_key_idx = 0
        self.searth_img_url = "https://taobao-datahub.p.rapidapi.com/item_search_image_2"
        self.product_details_url = "https://taobao-datahub.p.rapidapi.com/item_detail"
        self._session = None # Сессию создадим позже

    async def get_session(self):
        # Создаем сессию только когда она реально нужна внутри асинхронного метода
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
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
        loggerTao.info(f"Переключились на API ключ №{self.current_key_idx}")

    async def tao_imginfo(self, cloud_name, upload_preset, img: bytes):
        online_img = await self._getwebimg(cloud_name=cloud_name,upload_preset=upload_preset,img_bytes=img)
        params = {"imgUrl": online_img, "pageSize": "10"}

        for _ in range(len(self.keys)): # Пробуем ключи по очереди, если лимит исчерпан
            try:
                session = await self.get_session()
                async with session.get(self.searth_img_url, headers=self._get_headers(), params=params, timeout=20) as resp:
                    loggerTao.info(f"Taobao image search запрос: {resp.url}, статус: {resp.status}")
                    if resp.status == 429: # Лимит исчерпан
                        self._rotate_key()
                        continue
                    elif resp.status != 200:
                        error_text = await resp.text()
                        loggerTao.error(f"Taobao ошибка запроса: {error_text[:300]}")
                        return f"Ошибка API Taobao ({resp.status}): {error_text[:100]}"
                    result = await resp.json()
                    
                    products = result.get('result', {}).get('resultList')
                    if products is None:
                        return "Товары не найдены или структура ответа изменилась"
                    responselist = []
                    for prod in products:
                        item = prod['item']
                        responselist.append({
                                    "image": f"https:{item.get('image', None)}",
                                    'title': item.get("title"),
                                    'link': f"https:{item.get('itemUrl')}",
                                    "id": item.get("itemId"),
                                    'idStr': item.get("itemIdStr"),
                                    'market': 'Taobao'
                                    })
                    return responselist

            except asyncio.TimeoutError:
                return "Ошибка: API не ответило вовремя"
            except Exception as e:
                return f"Ошибка при выполнении запроса: {e}"



    async def _getwebimg(self, cloud_name: str, upload_preset: str, img_bytes: bytes) -> str:
        """
        Загружает изображение в Cloudinary и возвращает прямую ссылку.
        """

        if not img_bytes or len(img_bytes) < 50:
            raise Exception("Файл пустой или поврежден")

        upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"

        data = aiohttp.FormData()
        data.add_field("upload_preset", upload_preset)
        data.add_field(
            "file",
            img_bytes,
            filename="upload.jpg",
            content_type="image/jpeg"
        )

        timeout = aiohttp.ClientTimeout(total=20)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(upload_url, data=data) as resp:
                loggerTao.info(f"Cloudinary upload запрос: {upload_url}, статус: {resp.status}")
                if resp.status != 200:
                    text = await resp.text()
                    loggerTao.error(f"Cloudinary ошибка: {text[:300]}")
                    raise Exception(f"Cloudinary Error {resp.status}: {text}")

                result = await resp.json()

                return result["secure_url"]  # HTTPS ссылка
            
    def _format_data(self, data: dict):
        if not data:
            return {"error": "Пустой ответ API"}

        item = data.get("result", {}).get("item")

        if not item:
            return {"error": "Товар не найден или ошибка API"}

        sku_info = item.get("sku", {})

        # 1. Общий остаток
        total_stock = sum(
            int(s.get("quantity", 0))
            for s in sku_info.get("base", [])
        )

        # 2. Характеристики
        properties = {
            p.get("name"): p.get("value")
            for p in item.get("properties", {}).get("list", [])
        }

        # 3. Цены
        default_sku = sku_info.get("def", {})
        current_price = default_sku.get("promotionPrice") or default_sku.get("price")
        old_price = default_sku.get("price")

        # 4. Формируем результат
        return {
            "item_id": item.get("itemId"),
            "title": item.get("title"),
            "category": item.get("catName"),

            "price_current": float(current_price) if current_price else 0,
            "price_original": float(old_price) if old_price else 0,
            "monthly_sales": int(item.get("sales", 0)),
            "total_stock": total_stock,

            "ships_from": item.get("delivery", {}).get("shipsFrom"),
            "shipping_fee": item.get("delivery", {})
                            .get("shipFeeDetails", [{}])[0]
                            .get("fee", "0.00"),

            "seller_name": item.get("seller", {}).get("storeTitle"),
            "seller_type": item.get("seller", {}).get("storeType"),
            "shop_rating": item.get("seller", {})
                            .get("storeEvaluates", [{}])[0]
                            .get("score"),

            "reviews_count": item.get("reviews", {}).get("count"),

            "all_props": properties,
            "url": f"https:{item.get('itemUrl')}"
        }
    
    async def get_item_detail(self, item_id: str, item_id_str: str = None):
        params = {
            "itemId": item_id,
            "itemIdStr": item_id_str
        }

        for _ in range(len(self.keys)): # Пробуем ключи по очереди, если лимит исчерпан
            try:
                session = await self.get_session()
                async with session.get(self.product_details_url, headers=self._get_headers(), params=params, timeout=20) as resp:
                    loggerTao.info(f"Taobao детальная инфа запрос: {resp.url}, статус: {resp.status}")
                    if resp.status == 429: # Лимит исчерпан
                        self._rotate_key()
                        continue
                    elif resp.status != 200:
                        error_text = await resp.text()
                        loggerTao.error(f"Taobao детальная ошибка запроса: {error_text[:300]}")
                        return f"Ошибка API Taobao ({resp.status}): {error_text[:100]}"
                    result = await resp.json()
                    loggerTao.info(f"Taobao детальная инфа ответ (первые 500 символов): {str(result)[:500]}")
                    return self._format_data(result)
                    

            except asyncio.TimeoutError:
                loggerTao.error(f"Таймаут запроса к {self.host}")

                return 'Timeout не удалось получить ответы от сервера'
            except Exception as e:
                loggerTao.exception(f"Общая ошибка запроса к {self.host}")  # тут stack trace
                return "Произошла ошибка при получение данных о товаре таобао"