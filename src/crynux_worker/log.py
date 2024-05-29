import logging
import os
from logging.handlers import RotatingFileHandler



def init(log_dir: str, log_level: str, log_filename: str = "crynux-worker.log", root: bool = False):
    stream_handler = logging.StreamHandler()

    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, log_filename)
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
    logger.setLevel(log_level)
