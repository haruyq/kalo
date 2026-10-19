"""Overlay list page. The overlay files themselves are mounted in kalo.app, after every router."""
import html

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from kalo.game.reader import reader
from kalo.paths import OVERLAYS_DIR

router = APIRouter()


@router.get('/', response_class=HTMLResponse)
def index():
    names = sorted(d.name for d in OVERLAYS_DIR.glob('*/') if (d / 'index.html').is_file())
    items = ''.join(f'<li><a href="/{html.escape(n)}/">{html.escape(n)}</a></li>' for n in names)
    return (f'<!doctype html><meta charset="utf-8"><title>kalo</title><body style="font-family:sans-serif">'
            f'<h1>kalo</h1><p>status: {reader.state["status"]}</p><h2>Overlays</h2><ul>{items}</ul></body>')
