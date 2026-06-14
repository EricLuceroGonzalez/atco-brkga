# config/logging_config.py
import logging
import logging.config


def setup_logging(level: str = "INFO", log_file: str = "logs/app.log"):
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": log_file,
                "maxBytes": 5_000_000,  # 5 MB
                "backupCount": 3,
                "formatter": "standard",
            },
        },
        "root": {"level": level, "handlers": ["console", "file"]},
    }
    logging.config.dictConfig(config)
