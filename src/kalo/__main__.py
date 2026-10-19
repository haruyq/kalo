"""Command line entry: `uv run kalo [port]` or `kalo.exe [port]`."""
import argparse

import uvicorn

from kalo.app import app
from kalo.paths import OVERLAYS_DIR


def main():
    parser = argparse.ArgumentParser(prog='kalo', description='tosu-compatible overlay server for KALPA: Cosmic Symphony')
    parser.add_argument('port', nargs='?', type=int, default=24050, help='default: 24050 (same as tosu)')
    port = parser.parse_args().port
    print(f'kalo: http://127.0.0.1:{port}/  (overlays from {OVERLAYS_DIR})')
    # Short graceful shutdown: open overlay WebSockets would otherwise keep Ctrl-C waiting.
    uvicorn.run(app, host='127.0.0.1', port=port, ws='websockets-sansio', log_level='warning',
                timeout_graceful_shutdown=1)


if __name__ == '__main__':
    main()
