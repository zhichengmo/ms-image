"""Small framework helpers required by the FastAPI scaffold.

This module deliberately contains no XRay or persistence behaviour.  The
helpers are kept here so the application entrypoint can boot without pulling
in any legacy service code.
"""

LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": "INFO",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}


def get_logging_message(request: object, message: object) -> str:
    """Return a request path context without query strings or credentials."""

    method = getattr(request, "method", "")
    url = getattr(request, "url", "")
    path = getattr(url, "path", str(url).split("?", 1)[0])
    return f"{method} {path} - {message}"


__all__ = ["LOG_CONFIG", "get_logging_message"]
