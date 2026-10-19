"""Build dist/kalo.exe and dist/kalo-<version>.zip (exe + empty overlays/ + licenses/). Run: uv run build.py"""
import re
import shutil
import sys
import tomllib
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).parent
DIST = ROOT / 'dist'
PROJECT = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
VERSION = PROJECT['version']
EXCLUDED = {'fmod-toolkit', 'pyfmodex'}  # stubbed out, see src/kalo/game/covers.py


def bundled_dists(names, seen):
    """Runtime dependencies, transitively, minus the excluded audio stack."""
    for name in names:
        key = re.split(r'[^A-Za-z0-9_.-]', name, maxsplit=1)[0].lower().replace('_', '-')
        if key in seen or key in EXCLUDED:
            continue
        try:
            reqs = distribution(key).requires or []
        except PackageNotFoundError:  # requirement whose marker excludes this platform/Python: not bundled
            continue
        seen.add(key)
        bundled_dists([r for r in reqs if 'extra ==' not in r], seen)
    return seen


def copy_licenses(dest):
    """Bundled libraries' license files; their licenses require the notice to travel with the binary."""
    for name in sorted(bundled_dists(PROJECT['dependencies'], set())):
        d = distribution(name)
        for f in d.files or []:
            if re.search(r'(LICEN[CS]E|COPYING|NOTICE)', f.name, re.I) and '.dist-info' in str(f):
                out = dest / d.metadata['Name'] / f.name
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f.locate(), out)
    py_license = Path(sys.base_prefix) / 'LICENSE.txt'  # the Python runtime inside the exe
    if py_license.exists():
        (dest / 'Python').mkdir(parents=True, exist_ok=True)
        shutil.copy2(py_license, dest / 'Python' / 'LICENSE.txt')


PyInstaller.__main__.run([
    str(ROOT / 'src' / 'kalo' / '__main__.py'), '--paths', str(ROOT / 'src'),
    '--name', 'kalo', '--onefile', '--console', '--noconfirm',
    '--distpath', str(DIST), '--workpath', str(ROOT / 'build'), '--specpath', str(ROOT / 'build'),
    # uvicorn imports its protocol and loop implementations by name.
    '--collect-submodules', 'uvicorn',
    # UnityPy loads texture decoders lazily, and etcpak/astc pick a CPU-specific binary via archspec at runtime.
    *[arg for pkg in ('UnityPy', 'texture2ddecoder', 'etcpak', 'astc_encoder', 'archspec')
      for arg in ('--collect-all', pkg)],
    # Audio only; game/covers.py stubs it so FMOD's proprietary fmod.dll is never shipped.
    '--exclude-module', 'fmod_toolkit', '--exclude-module', 'pyfmodex',
])

# Overlays are third-party; ship the folder empty and let users drop theirs in, like tosu's static/.
stage = DIST / f'kalo-{VERSION}'
shutil.rmtree(stage, ignore_errors=True)
(stage / 'overlays').mkdir(parents=True)
shutil.copy2(DIST / 'kalo.exe', stage)
shutil.copy2(ROOT / 'README.md', stage)
copy_licenses(stage / 'licenses')
print('built', shutil.make_archive(str(stage), 'zip', DIST, stage.name))
