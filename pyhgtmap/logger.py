import logging

import colorlog

# Root logger for the package
logger: logging.Logger = logging.getLogger("pyhgtmap")


def configure_logging(logLevel) -> None:
    """Customize logging level and colors."""
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s - %(name)s:%(lineno)d:%(levelname)s - %(process)d - %(message)s"
        )
    )

    log_level = getattr(logging, logLevel)
    if log_level == logging.DEBUG:
        # Show other python packages' logs only in DEBUG level
        logging.getLogger().setLevel(log_level)
        logging.getLogger().addHandler(handler)
    else:
        # Only log current logger
        logger.setLevel(log_level)
        logger.addHandler(handler)
