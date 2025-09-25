"""Shim settings module.

This file exists only to avoid confusion. The real Django settings live at
`NomoFlow/NomoFlow/settings.py`. We re-export everything from there so tools
that look for `NomoFlow/settings.py` can still function.
"""

# Prefer absolute import to the canonical settings module
from NomoFlow.NomoFlow.settings import *  # noqa: F401,F403

