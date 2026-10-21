from loguru import logger

from config.settings import settings

logger.add(
    "app.log",
    rotation="10 MB",
    retention="30 days",
    level=settings.LOG_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)