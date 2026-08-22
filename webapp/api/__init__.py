"""FastAPI application for Aphelion Content Tools.

Replaces the hand-rolled `http.server` dispatch in `webapp/server.py`. The domain modules underneath
(`tools/lore_editor/api.py`, `tools/content_graph/*`, `webapp/git_adapter.py`, `webapp/tooling.py`,
`webapp/store/*`) are reused unchanged -- they never knew what served them over HTTP.
"""

from .app import create_app

__all__ = ["create_app"]
