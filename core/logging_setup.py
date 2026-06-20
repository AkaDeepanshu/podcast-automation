"""Per-job logger: writes to both console and a per-job log file."""

import logging
from pathlib import Path


def get_job_logger(job_id: str, logs_dir: str) -> logging.Logger:
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    log_path = Path(logs_dir) / f"{job_id}.log"

    logger = logging.getLogger(job_id)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger  # already configured (e.g. re-entrant call)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    return logger
