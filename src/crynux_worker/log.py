import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

from crynux_worker.config import Config, get_config


def init(config: Optional[Config] = None, root: bool = False):
    if config is None:
        config = get_config()

    stream_handler = logging.StreamHandler()

    if not os.path.exists(config.log.dir):
        os.makedirs(config.log.dir, exist_ok=True)
    log_file = os.path.join(config.log.dir, "crynux-worker.log")
    file_handler = RotatingFileHandler(
        log_file,
        encoding="utf-8",
        delay=True,
        maxBytes=50 * 1024 * 1024,
        backupCount=5,
    )

    dt_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
    )

    stream_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    if root:
        logger = logging.getLogger()
    else:
        logger = logging.getLogger("crynux_worker")

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.setLevel(config.log.level)
