"""
Configures application-wide logging with a rotating log file and console output.
Max file size: 5 MB, keeps last 7 backups.
"""
import os
import logging
from logging.handlers import RotatingFileHandler


def setup(log_dir: str, level=logging.INFO):
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "autonoc.log")

    file_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    con_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    fh = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=7, encoding="utf-8"
    )
    fh.setFormatter(file_fmt)

    ch = logging.StreamHandler()
    ch.setFormatter(con_fmt)

    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(fh)
        root.addHandler(ch)
