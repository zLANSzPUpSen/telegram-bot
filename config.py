import logging

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = "8519453524:AAE6G4mmDfVgCoeWtcX1LVVsZHy6HdEgxSo"

# Настройки таймеров
TIMERS = {
    'registration': 30,      # 30 секунд на регистрацию
    'discussion': 120,       # 2 минуты на обсуждение
    'mafia_guess': 60        # 30 секунд на угадывание
}
