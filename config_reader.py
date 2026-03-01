from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    # Желательно вместо str использовать SecretStr 
    # для конфиденциальных данных, например, токена бота
    tovarnyu_token: SecretStr
    
    ai_groq_api: SecretStr
    ai_groq_model: SecretStr

    rapidapi_key1: SecretStr
    rapidapi_key2: SecretStr

    img_key: SecretStr
    img_secret: SecretStr
    cloud_name: SecretStr
    # Начиная со второй версии pydantic, настройки класса настроек задаются
    # через model_config
    # В данном случае будет использоваться файла .env, который будет прочитан
    # с кодировкой UTF-8
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')


# При импорте файла сразу создастся 
# и провалидируется объект конфига, 
# который можно далее импортировать из разных мест
config = Settings()