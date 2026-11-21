"""
OpenOMEN GUI (PySide6).

Reads hardware state straight from openomen.core on a background thread.
This first version is read-only: controls are shown but disabled until
privileged writes (pkexec + polkit) land.
"""
