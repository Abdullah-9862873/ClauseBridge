import logging

from core.config import settings


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    return logger


logger = setup_logger(settings.app_name)
