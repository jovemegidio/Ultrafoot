# -*- coding: utf-8 -*-
"""Logging centralizado do Ultrafoot."""
from __future__ import annotations

import logging
import os
from config import LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)

_fmt = logging.Formatter("[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
                         datefmt="%Y-%m-%d %H:%M:%S")

_fh = logging.FileHandler(os.path.join(LOGS_DIR, "brasfoot.log"), encoding="utf-8")
_fh.setFormatter(_fmt)
_fh.setLevel(logging.DEBUG)

_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
_sh.setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger configurado para o módulo indicado."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_fh)
        logger.addHandler(_sh)
        logger.setLevel(logging.DEBUG)
    return logger
