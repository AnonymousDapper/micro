# The MIT License (MIT)

# Copyright (c) 2022 AnonymousDapper

__all__ = ("get_logger",)

import logging

LOG_LEVEL = logging.INFO


class ConsoleFormatter(logging.Formatter):
    COLORS = (
        (logging.DEBUG, "\x1b[97;3m"),
        (logging.INFO, "\x1b[34m"),
        (logging.WARNING, "\x1b[93;1m"),
        (logging.ERROR, "\x1b[31;1m"),
        (logging.CRITICAL, "\x1b[41;37;1;5m"),
    )

    FORMATS = {
        level: logging.Formatter(
            f"{color}[>] %(levelname)-8s\x1b[0m \x1b[35m%(name)s:%(funcName)s:%(lineno)d\x1b[0m %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
        for level, color in COLORS
    }

    def format(self, record):
        formatter = self.FORMATS.get(record.levelno, self.FORMATS[logging.DEBUG])

        record.exc_text = None
        return formatter.format(record)


STREAM_HANDLER = logging.StreamHandler()

STREAM_HANDLER.setFormatter(ConsoleFormatter())


def get_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(STREAM_HANDLER)

    return logger
