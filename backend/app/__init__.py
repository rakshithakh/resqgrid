"""Read backend/.env into the environment before the app reads its settings."""

import os

_p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_p):
    for _line in open(_p, encoding="utf-8"):
        _line = _line.split(" #")[0].strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
