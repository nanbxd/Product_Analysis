import redis.asyncio as redis
from datetime import timedelta
from config_reader import config
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+

MOSCOW_TZ = ZoneInfo("Europe/Moscow")  # можешь сменить на свой
ALMATY_TZ = ZoneInfo("Asia/Almaty")
async def get_reset_time(user_id: int, limit_type: str) -> dict[str]:
    key = f"user:{user_id}:{limit_type}_count"
    ttl = await r.ttl(key)
    if ttl <= 0:
        return "уже восстановлен"

    moscow_time = datetime.now(MOSCOW_TZ) + timedelta(seconds=ttl)
    almaty_time = datetime.now(ALMATY_TZ) + timedelta(seconds=ttl)
    return {
            'almaty': almaty_time.strftime("%d.%m %H:%M"), 
            'moscow': moscow_time.strftime("%d.%m %H:%M")
        }

# Настройки Redis
REDIS_URL = config.reddis_db.get_secret_value()
r = redis.from_url(
    REDIS_URL, 
    decode_responses=True,
    socket_connect_timeout=10,
    socket_keepalive=True,
    retry_on_timeout=True,
    health_check_interval=30  # Проверять соединение каждые 30 секунд
)


# Лимиты
DAILY_MSG_LIMIT = 100
DAILY_IMG_LIMIT = 20
DAILY_PIND_LIMIT = 4
DAILY_TAO_LIMIT = 3

TTL = 24 * 60 * 60  # 24 часа в секундах

async def check_limit(user_id: int, limit_type: str) -> bool:
    """
    Проверяем лимит для пользователя.
    limit_type: "msg", "img", "pindu", "tao"
    """
    key = f"user:{user_id}:{limit_type}_count"
    count = await r.get(key)
    if count is None:
        await r.set(key, 0, ex=TTL)  # Создаем ключ с TTL
        count = 0
    return int(count) < {
        "msg": DAILY_MSG_LIMIT,
        "img": DAILY_IMG_LIMIT,
        "pindu": DAILY_PIND_LIMIT,
        "tao": DAILY_TAO_LIMIT
    }[limit_type]

async def increment_limit(user_id: int, limit_type: str):
    key = f"user:{user_id}:{limit_type}_count"

    # если ключа нет — создаём с TTL
    if not await r.exists(key):
        await r.set(key, 1, ex=TTL)
        return 1

    # если есть — просто увеличиваем
    return await r.incr(key)

async def get_remaining(user_id: int, limit_type: str) -> int:
    key = f"user:{user_id}:{limit_type}_count"

    max_limit = {
        "msg": DAILY_MSG_LIMIT,
        "img": DAILY_IMG_LIMIT,
        "pindu": DAILY_PIND_LIMIT,
        "tao": DAILY_TAO_LIMIT
    }[limit_type]

    count = await r.get(key)
    count = int(count) if count else 0

    return max_limit - count

# async def clearid(id):
#     await r.delete(f"user:{id}:msg_count")
#     await r.delete(f"user:{id}:img_count")
#     await r.delete(f"user:{id}:tao_count")
#     await r.delete(f"user:{id}:pindu_count")