"""
Hardware access layer shared by the CLI and the GUI.

Rules for everything in this package:
- Never print. Return data (dicts/lists/strings) instead.
- Fatal problems raise OpenOMENError; its `lines` are the exact messages the
  CLI prints to stderr (the first line is the main message).
- Non-fatal problems (a sensor that can't be read, a broken profile file) are
  reported through the "openomen" logger and the function returns None/[].
- Never ask for root. Callers decide how to get privileges (the CLI re-runs
  itself with sudo, the GUI will go through pkexec).
"""

import logging

from .errors import OpenOMENError

log = logging.getLogger("openomen")

__all__ = ["OpenOMENError", "log"]
