import logging
import sys

import structlog

from app.core.config import Environment, get_settings


def configure_logging() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Every log entry passes through these processors in order before rendering.
    # merge_contextvars must be first — it pulls in fields bound via
    # structlog.contextvars.bind_contextvars() (e.g. request_id from middleware).
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.app_env == Environment.DEVELOPMENT:
        # Coloured, aligned, human-readable output for local development.
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        # Machine-readable JSON for staging and production log aggregators.
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            # Prepares the entry to be handed off to stdlib's ProcessorFormatter.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        # Parse the logger name once and cache it — avoids per-call overhead.
        cache_logger_on_first_use=True,
    )

    # ProcessorFormatter bridges structlog and stdlib logging so that
    # third-party libraries (uvicorn, sqlalchemy, httpx) emit logs in the
    # same format as our application code.
    formatter = structlog.stdlib.ProcessorFormatter(
        # foreign_pre_chain handles entries that originated in stdlib logging.
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # uvicorn.access emits one line per request — replaced by our own
    # request logging middleware, so suppress it to avoid duplication.
    logging.getLogger("uvicorn.access").propagate = False
