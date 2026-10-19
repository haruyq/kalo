"""Track jackets read from the local KALPA install at runtime. Images live only in memory.

Only the name -> bundle-file index is cached on disk (no image data); it rebuilds when the install changes.
"""
import functools
import io
import json
import os
import sys
import threading
import types

# UnityPy's audio exporter imports fmod_toolkit, which loads FMOD's proprietary fmod.dll, at import time but
# only calls it to convert audio. Jackets never need it, so a stub keeps fmod.dll out of the process and the exe.
sys.modules.setdefault('fmod_toolkit', types.ModuleType('fmod_toolkit'))

import UnityPy  # noqa: E402  (after the stub)
from PIL import ImageOps  # noqa: E402  (Pillow comes with UnityPy)

PREFIX = 'Assets/res/assetbundle/trackcover/'


class Covers:
    def __init__(self, game_data_dir, index_path):
        self.dir = os.path.join(game_data_dir, 'StreamingAssets', 'aa', 'StandaloneWindows64')
        self.index_path = index_path
        self.index = None
        threading.Thread(target=self._load_index, daemon=True).start()

    def _signature(self):
        cat = os.stat(os.path.join(self.dir, '..', 'catalog.bin'))
        return f"{len(os.listdir(self.dir))}:{cat.st_size}:{int(cat.st_mtime)}"

    def _load_index(self):
        try:
            self._build_index()
        except OSError as e:  # unexpected install layout: run without jackets, but say why
            print(f'\n[covers] jackets disabled: {e}')

    def _build_index(self):
        sig = self._signature()
        try:
            with open(self.index_path, encoding='utf-8') as f:
                cached = json.load(f)
            if cached['signature'] == sig:
                self.index = cached['covers']
                return
        except (OSError, ValueError, KeyError):
            pass
        print('\n[covers] building jacket index (first run or game updated, ~1 min)...')
        covers = {}
        for name in os.listdir(self.dir):
            if name.endswith('.bundle'):
                for path in UnityPy.load(os.path.join(self.dir, name)).container:
                    if path.startswith(PREFIX):
                        covers[path[len(PREFIX):].rsplit('.', 1)[0]] = name
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump({'signature': sig, 'covers': covers}, f)
        self.index = covers
        print(f'\n[covers] {len(covers)} jackets indexed')

    def png(self, key, width=None, height=None, crop=False):
        """PNG bytes for a Track.CoverFileName, or None (unknown key / index not ready).

        No size: the original. With width/height: fit inside, or with crop fill and center-crop
        (StreamCompanion's /backgroundImage contract; overlays size their box and expect a matching image).
        """
        bundle = (self.index or {}).get(key)  # only indexed names: no path from the URL reaches the disk
        return self._png(key, bundle, width, height, crop) if bundle else None

    @functools.lru_cache(maxsize=64)
    def _png(self, key, bundle, width, height, crop):
        for obj in UnityPy.load(os.path.join(self.dir, bundle)).objects:
            if obj.type.name == 'Texture2D' and (tex := obj.read()).m_Name == key:
                img = tex.image
                if width and height:
                    img = ImageOps.fit(img, (width, height)) if crop else ImageOps.contain(img, (width, height))
                buf = io.BytesIO()
                img.save(buf, 'PNG')
                return buf.getvalue()
        return None
