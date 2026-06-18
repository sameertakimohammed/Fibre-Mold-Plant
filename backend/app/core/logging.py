"""Structured JSON logging configuration.

Configures stdlib logging (uvicorn access/error loggers + the app logger)
to emit single-line JSON via python-json-logger. Every record is stamped
with the current request id (empty string outside a request).

Call configure_logging() exactly once, as early as possible at startup.
"""
import logging
import logging.config

from pythonjsonlogger import jsonlogger

from .context import get_request_id


class RequestIdFilter(logging.Filter):
    """Inject the current request id onto every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonFormatter(jsonlogger.JsonFormatter):
    """JSON formatter with a stable set of base fields."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        if not log_record.get("request_id"):
            log_record["request_id"] = getattr(record, "request_id", "")


_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": RequestIdFilter},
    },
    "formatters": {
        "json": {
            "()": JsonFormatter,
            # timestamp -> "asctime", message -> "message"
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_id"],
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        # uvicorn ships its own handlers; force everything through ours.
        "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "app": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    logging.config.dictConfig(_LOGGING_CONFIG)
    _configured = True
