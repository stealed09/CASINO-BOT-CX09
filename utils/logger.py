from loguru import logger
import sys
from config import LOG_FILE

logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}")
logger.add(LOG_FILE, level="DEBUG", rotation="10 MB", retention="7 days", compression="zip")
