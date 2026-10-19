"""The FastAPI app: routers from kalo.routers, plus overlays/<name>/ served at /<name>/ like tosu."""
import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from kalo.game.reader import reader
from kalo.paths import OVERLAYS_DIR
from kalo.routers import calculate, files, overlays, state

# Windows' registry can map .js to text/plain, which breaks overlays that load ES modules.
for ext, media_type in (('.js', 'text/javascript'), ('.mjs', 'text/javascript'), ('.css', 'text/css'),
                        ('.svg', 'image/svg+xml'), ('.woff2', 'font/woff2')):
    mimetypes.add_type(media_type, ext)


@asynccontextmanager
async def lifespan(_app):
    reader.start()
    yield


app = FastAPI(title='kalo', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['*'])
for module in (state, calculate, files, overlays):
    app.include_router(module.router)

# Last, so the routes above win. html=True serves index.html and redirects folder URLs to a trailing slash.
app.mount('/', StaticFiles(directory=OVERLAYS_DIR, html=True, check_dir=False), name='overlays')
