"""Live game state in each overlay format, over HTTP (polling) and WebSocket (push)."""
import asyncio
import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from kalo import tosu
from kalo.game.reader import reader

TICK = 0.1  # seconds between pushes
PRECISE_TICK = 0.033

router = APIRouter()

# (HTTP path, WebSocket path or None, state -> JSON-able dict, push interval)
FORMATS = [
    ('/json', '/ws', tosu.v1, TICK),
    ('/json/v2', '/websocket/v2', tosu.v2, TICK),
    ('/json/v2/precise', '/websocket/v2/precise', tosu.v2_precise, PRECISE_TICK),
    ('/json/sc', None, tosu.sc_tokens, TICK),  # its WebSocket is /tokens below, which filters
    ('/json/sp', None, tosu.sp_block, TICK),
]


async def push(ws: WebSocket, next_message, interval=TICK, on_message=lambda msg: None):
    """Every interval, send next_message() unless it returns None, until the socket closes.

    Reading continuously is what notices a close, from the client or a server shutdown,
    while there is nothing new to send.
    """
    await ws.accept()

    async def receive():
        try:
            while True:
                on_message(await ws.receive_text())
        except WebSocketDisconnect:
            pass

    receiving = asyncio.create_task(receive())
    try:
        while not receiving.done():
            message = next_message()
            if message is not None:
                await ws.send_text(message)
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        pass
    finally:
        receiving.cancel()


def when_changed(build):
    """next_message for push(): build(state) as JSON, only when it differs from the last one sent."""
    last = None

    def next_message():
        nonlocal last
        body = json.dumps(build(reader.state), ensure_ascii=False)
        if body != last:
            last = body
            return body
        return None

    return next_message


def add_format(http_path, ws_path, build, interval):
    router.add_api_route(http_path, lambda: build(reader.state), methods=['GET'], name=build.__name__)
    if ws_path:
        async def endpoint(ws: WebSocket):
            await push(ws, when_changed(build), interval)
        router.add_api_websocket_route(ws_path, endpoint)


for fmt in FORMATS:
    add_format(*fmt)


@router.websocket('/tokens')
async def ws_tokens(ws: WebSocket):
    """StreamCompanion: the client sends `applyFilters:[...]` or a JSON list; the server sends changed tokens."""
    filters = {'wanted': None, 'sent': {}}
    opened = time.monotonic()

    def apply_filter(msg):
        try:
            filters.update(wanted=list(json.loads(msg.removeprefix('applyFilters:'))), sent={})
        except ValueError:
            pass

    def next_message():
        if filters['wanted'] is None and time.monotonic() - opened < 0.5:
            return None  # clients filter right after connecting; clients that never filter get everything
        tokens = tosu.sc_tokens(reader.state)
        wanted, sent = filters['wanted'], filters['sent']
        view = {k: tokens[k] for k in wanted if k in tokens} if wanted else tokens
        changed = {k: v for k, v in view.items() if k not in sent or sent[k] != v}
        sent.update(changed)
        return json.dumps(changed, ensure_ascii=False) if changed else None

    await push(ws, next_message, on_message=apply_filter)


@router.websocket('/websocket/commands')
async def ws_commands(ws: WebSocket):
    """tosu overlay commands: getSettings gets empty settings; nothing else applies to KALPA."""
    await ws.accept()
    try:
        while True:
            if (await ws.receive_text()).split(':', 1)[0] == 'getSettings':
                await ws.send_text(json.dumps({'command': 'getSettings', 'message': {}}))
    except WebSocketDisconnect:
        pass
