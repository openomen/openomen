"""
OpenOMEN - control fans, power profiles and keyboard RGB on HP OMEN/Victus laptops.
audixdev - (C) Copyright 2026 - GPL-3.0 License

Package layout:
    openomen.core   hardware access; functions return data and raise OpenOMENError,
                    they never print (shared by the CLI and the GUI)
    openomen.cli    the `openomen` command line interface on top of core
"""

VERSION = "0.5.3"
APP_NAME = "OpenOMEN CLI"
