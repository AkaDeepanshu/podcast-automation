"""Per-job logger: console + log file, optional extra handlers (e.g. Redis)."""

import logging
from pathlib import Path


def get_job_logger(
    job_id: str,
    logs_dir: str,
    extra_handlers: list[logging.Handler] | None = None,
) -> logging.Logger:
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    log_path = Path(logs_dir) / f"{job_id}.log"

    logger = logging.getLogger(job_id)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # Idempotent base handlers (Celery workers reuse process/loggers).
    if not getattr(logger, "_podcast_base_handlers", False):
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(fmt)
        logger.addHandler(console_handler)

        logger._podcast_base_handlers = True  # type: ignore[attr-defined]

    if extra_handlers:
        for handler in extra_handlers:
            if handler not in logger.handlers:
                if handler.formatter is None:
                    handler.setFormatter(fmt)
                logger.addHandler(handler)

    return logger
