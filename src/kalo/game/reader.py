"""Polls KALPA's memory (read-only) into one plain state dict that kalo.tosu turns into overlay formats."""
import os
import re
import threading
import time

from kalo.game.covers import Covers
from kalo.game.memory import Mono, Proc
from kalo.paths import DATA_DIR
from kalo.stellar import COUNTED_MODES, profile_sp, stellar_point

POLL_INTERVAL = 0.05  # seconds
MODE_NAMES = ('NORMAL', 'HARD', 'COSMOS')  # anything above is ASTRA (PlayListHelper)
# Global.ScoreToResult thresholds on rate, and GetRankStringByRankIndex names.
RANKS = ((1_000_000, 'P'), (990_000, 'S++'), (980_000, 'S+'), (970_000, 'S'), (950_000, 'A+'),
         (900_000, 'A'), (700_000, 'B'), (500_000, 'C'))


def rank_of(rate):
    return next((name for floor, name in RANKS if rate >= floor), 'F')


def mode_name(mode):
    return MODE_NAMES[mode] if mode < len(MODE_NAMES) else 'ASTRA'


class Reader:
    """Background thread; `state` is replaced (never mutated) so readers need no lock."""

    def __init__(self):
        self.state = {'status': 'offline'}
        self.maps = {}
        self.tracks = {}
        self.covers = None
        self.errors = set()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            try:
                self._attach_and_poll()
            except (RuntimeError, MemoryError, KeyError) as e:  # game not running / still loading / closed
                self.state = {'status': 'offline', 'error': str(e)}
                time.sleep(2)

    def _attach_and_poll(self):
        p = Proc('KALPA CosmicSymphony.exe')
        m = Mono(p)
        if not self.covers:
            DATA_DIR.mkdir(exist_ok=True)
            self.covers = Covers(os.path.splitext(p.exe_path())[0] + '_Data', DATA_DIR / 'cover_index.json')
        user_rp = m.static('KalpaCosmicSymphony.Global', 'user')
        scene_rp = m.static('GameBase.UI.SceneManager', 'currentScene')
        user = m.walk(p.ptr(user_rp), 'value')
        self.maps = {p.i64(m.f(mp, 'MapID')): {'level': p.u8(m.f(mp, 'Difficulty')),
                                               'keys': int(m.string(p.ptr(m.f(mp, 'LaneType')))[-1]),
                                               'mode': p.u8(m.f(mp, 'Mode')), 'track_id': p.i64(m.f(mp, 'TrackID'))}
                     for mp in m.list_items(m.walk(user, 'Maps'))}
        self.tracks = {}
        for t in m.list_items(m.walk(user, 'Tracks')):
            artist = m.walk(t, 'Artist')
            self.tracks[p.i64(m.f(t, 'TrackID'))] = {
                'title': m.string(p.ptr(m.f(t, 'Title'))), 'artist': m.string(p.ptr(m.f(artist, 'Name'))) if artist else '',
                'cover': m.string(p.ptr(m.f(t, 'CoverFileName'))),
                'bpm_min': p.i32(m.f(t, 'MinBPM')), 'bpm_max': p.i32(m.f(t, 'MaxBPM'))}
        best, best_at, play, mult = None, 0, None, None

        while True:
            try:
                if not p.try_read(user_rp, 8):
                    raise RuntimeError('game closed')
                user = m.walk(p.ptr(user_rp), 'value')
                scene = m.walk(p.ptr(scene_rp), 'value')
                scene_name = m.name(m.klass(scene)) if scene else None
                prof = m.walk(user, 'userProfile', 'value')
                if scene_name != 'SceneGamePlay':
                    mult = None
                if best is None or (scene_name != 'SceneGamePlay' and time.time() - best_at > 2):
                    best, best_at = self._bests(m, p, user), time.time()  # bests change after each play
                profile = {'name': m.string(p.ptr(m.f(prof, 'Nickname'))),
                           'sp4k': profile_sp(best[4].values()), 'sp5k': profile_sp(best[5].values())}

                if scene_name == 'SceneGamePlay':
                    il = m.walk(scene, 'ControlIngameBase', 'ControlIngameNotePanelLogic', 'ingameLogic')
                    if il:
                        if mult is None:
                            n, data = m.array(m.walk(il, 'config', 'gradeConfigs'))
                            mult = [p.f64(m.f(p.ptr(data + i * 8), 'ScoreMultiply')) for i in range(n)]
                            play = None  # new play (also covers quick retry)
                        play = self._play(m, p, scene, il, mult, best, play)
                    status = 'playing'
                elif scene_name and scene_name.endswith('PlayResult') and play:  # also Astra/Multi results
                    status = 'results'
                else:
                    status, play = 'menu', None
                    if scene and 'ControlPlayListTrackRanking' in m.fields(m.klass(scene)):  # normal/Astra song select
                        status = 'songselect'
                # `play` is the current beatmap: the selected one in song select, plus live values while playing.
                beatmap = self._selected(m, p, scene, best) if status == 'songselect' else play
                self.state = {'status': status, 'scene': scene_name, 'profile': profile, 'play': beatmap}
            except (MemoryError, KeyError, UnicodeDecodeError, ZeroDivisionError, TypeError) as e:
                # Usually a scene switching mid-read; retry. Show each distinct error once.
                msg = re.sub(r'0x[0-9a-f]+', '0x?', f'{type(e).__name__}: {e}')
                if msg not in self.errors:
                    self.errors.add(msg)
                    print(f'[read error] {msg}')
            time.sleep(POLL_INTERVAL)

    def _bests(self, m, p, user):
        """{keys: {map_id: best SP}} over counted modes, better of normal/lunatic per map."""
        out = {4: {}, 5: {}}
        for lun, field in ((False, 'BestMapRecords'), (True, 'BestLunaticMapRecords')):
            for r in m.list_items(m.walk(user, field)):
                mid = p.i64(m.f(r, 'MapID'))
                mp = self.maps.get(mid)
                if mp and mp['mode'] in COUNTED_MODES:
                    sp = stellar_point(mp['level'], p.i64(m.f(r, 'Rate')), lun)
                    out[mp['keys']][mid] = max(out[mp['keys']].get(mid, 0), sp)
        return out

    def _beatmap(self, map_id, lunatic, best):
        """What is known about a map before playing it: song select shows this, a play adds live values."""
        info = self.maps[map_id]
        lv, keys, mode = info['level'], info['keys'], info['mode']
        counted = mode in COUNTED_MODES
        return {'map_id': map_id, 'track_id': info['track_id'], **self.tracks.get(info['track_id'], {}),
                'level': lv, 'keys': keys, 'mode': mode, 'mode_name': mode_name(mode), 'lunatic': lunatic,
                'counted': counted, 'sp_ap': stellar_point(lv, 1_000_000, lunatic),
                'sp_best': best[keys].get(map_id, 0) if counted else 0}

    def _selected(self, m, p, scene, best):
        """Map highlighted in song select. currentRankingKey updates on every pick, panel open or not."""
        key = m.f(m.walk(scene, 'ControlPlayListTrackRanking'), 'currentRankingKey')
        map_id = p.i64(key)
        return self._beatmap(map_id, bool(p.u8(key + 8)), best) if map_id in self.maps else None

    def _play(self, m, p, scene, il, mult, best, prev):
        map_id = p.i64(m.f(m.walk(scene, 'map'), 'MapID'))
        beatmap = self._beatmap(map_id, bool(p.u8(m.f(scene, 'lunaticMode'))), best)
        lv, keys, lunatic = beatmap['level'], beatmap['keys'], beatmap['lunatic']
        n, data = m.array(p.ptr(m.f(il, 'gradeCounts')))
        counts = [p.i32(data + i * 4) for i in range(n)]  # 0 PERFECT, 1 GREAT, 2 GOOD
        misses = p.i32(m.f(il, 'MissCount'))
        total = p.i32(m.f(il, 'NoteCount'))
        weighted = sum(c * k for c, k in zip(counts, mult))
        judged = sum(counts) + misses
        # Same flooring as IngameSystemHelper.GetRate.
        rate_max = min(int((weighted + max(total - judged, 0) * mult[0]) / total * 1_000_000), 1_000_000)
        rate_now = min(int(weighted / judged * 1_000_000), 1_000_000) if judged else 1_000_000
        sp_now, sp_max = stellar_point(lv, rate_now, lunatic), stellar_point(lv, rate_max, lunatic)
        if beatmap['counted']:
            after = {**best[keys], map_id: max(beatmap['sp_best'], sp_max)}
            profile_after = profile_sp(after.values())
            profile_delta = profile_after - profile_sp(best[keys].values())
        else:
            profile_after = profile_delta = None
        return {
            **beatmap,
            'time_ms': p.i32(m.f(il, 'TimeMilliseconds')), 'length_ms': p.i32(m.f(scene, 'audioLengthInt')),
            'score': int(p.f64(m.f(il, 'Score'))), 'combo': p.i32(m.f(il, 'Combo')),
            'max_combo': p.i32(m.f(il, 'MaxCombo')), 'hp': p.f32(m.f(il, 'HP')),
            'perfect': counts[0], 'great': counts[1], 'good': counts[2], 'miss': misses,
            'notes': total, 'judged': judged,
            'rate_now': rate_now, 'rate_max': rate_max, 'rank': rank_of(rate_now),
            'rank_max': rank_of(rate_max), 'sp_now': sp_now, 'sp_max': sp_max,
            'sp_peak': max(sp_now, (prev or {}).get('sp_peak', 0)),
            'profile_after': profile_after, 'profile_delta': profile_delta,
        }


    def calc(self, map_id=None, rate=None, lunatic=None, level=None):
        """SP for an arbitrary map/rate; defaults to the current play. Returns None if unknown."""
        play = self.state.get('play') or {}
        if level is None:
            info = self.maps.get(map_id) if map_id is not None else (play and {'level': play['level']})
            if not info:
                return None
            level = info['level']
        rate = play.get('rate_now', 1_000_000) if rate is None else rate
        lunatic = play.get('lunatic', False) if lunatic is None else lunatic
        return {'level': level, 'rate': rate, 'lunatic': lunatic, 'rank': rank_of(rate),
                'sp': stellar_point(level, rate, lunatic)}


reader = Reader()  # shared by the routers; started by the app's lifespan
