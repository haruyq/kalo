"""Checks that need no running game. Run: uv run python tests/test_core.py (pytest also collects them)."""
from kalo import tosu
from kalo.game.reader import rank_of
from kalo.stellar import profile_sp, stellar_point


def test_stellar_point_matches_server_values():
    # (level, rate, lunatic) -> SP as reported by the KALPA server
    cases = [
        (18, 1_000_000, False, 21.0),       # AP
        (19, 999_890, False, 21.7418),      # 99-100% band
        (20, 996_938, False, 22.5203),      # 99% band, below
        (15, 974_393, False, 15.3295),      # 97-98% band
        (13, 974_568, False, 13.3426),
        (14, 960_412, False, 13.0206),      # 95-97% band
        (19, 986_883, True, 22.5678),       # Lunatic x1.1
        (18, 986_595, True, 21.4441),
    ]
    for level, rate, lunatic, expected in cases:
        assert abs(stellar_point(level, rate, lunatic) - expected) < 1e-4, (level, rate, lunatic)


def test_profile_sp_is_top30_over_30():
    records = [15.3295, 13.3404, 13.2594, 13.1517, 13.0206, 12.4028, 12.1472, 9.2773]  # fewer than 30
    assert abs(profile_sp(records) - 3.39763) < 1e-5
    assert profile_sp([21.0] * 40) == 21.0


def test_rank_thresholds():
    assert [rank_of(r) for r in (1_000_000, 990_000, 989_999, 970_000, 950_000, 0)] == ['P', 'S++', 'S+', 'S', 'A+', 'F']


PROFILE = {'name': 'player', 'sp4k': 21.5, 'sp5k': 3.84}
SELECTED = {'map_id': 9193, 'track_id': 1, 'title': 'OMG', 'artist': 'Halv', 'cover': 'trackcover_track.omg',
            'bpm_min': 170, 'bpm_max': 170, 'level': 18, 'keys': 4, 'mode': 2, 'mode_name': 'COSMOS',
            'lunatic': True, 'counted': True, 'sp_ap': 23.1, 'sp_best': 20.7}
PLAYING = {**SELECTED, 'time_ms': 61_000, 'length_ms': 120_000, 'score': 990_000, 'combo': 300, 'max_combo': 450,
           'hp': 80.0, 'perfect': 900, 'great': 20, 'good': 3, 'miss': 1, 'notes': 1500, 'judged': 924,
           'rate_now': 991_000, 'rate_max': 996_000, 'rank': 'S++', 'rank_max': 'S++',
           'sp_now': 22.9, 'sp_max': 23.0, 'sp_peak': 23.0, 'profile_after': 21.6, 'profile_delta': 0.1}
STATES = {
    'offline': {'status': 'offline'},
    'songselect': {'status': 'songselect', 'profile': PROFILE, 'play': SELECTED},
    'playing': {'status': 'playing', 'profile': PROFILE, 'play': PLAYING},
}


def test_every_format_builds_in_every_state():
    for name, state in STATES.items():
        for build in (tosu.v1, tosu.v2, tosu.v2_precise, tosu.sc_tokens, tosu.sp_block):
            assert isinstance(build(state), dict), (name, build.__name__)


def test_pp_fields_carry_sp():
    s = STATES['playing']
    assert tosu.v1(s)['gameplay']['pp'] == {'current': 22.9, 'fc': 23.0, 'maxThisPlay': 23.0}
    assert tosu.v2(s)['play']['pp']['maxAchievable'] == 23.1
    assert tosu.sc_tokens(s)['ppIfRestFced'] == tosu.sc_tokens(s)['spIfRestFced'] == 23.0


def test_song_select_shows_selected_map():
    v1 = tosu.v1(STATES['songselect'])
    assert v1['menu']['state'] == 5
    assert v1['menu']['bm']['metadata']['title'] == 'OMG'
    assert v1['menu']['bm']['path']['full'] == 'trackcover_track.omg.png'
    assert abs(v1['menu']['pp']['100'] - 23.1) < 1e-9  # Lv18 AP, Lunatic


def test_cover_key_round_trips_dotted_names():
    pl = {'cover': 'trackcover_track.omg'}
    for path in (tosu.cover_file(pl), 'sub/' + tosu.cover_file(pl), pl['cover']):  # /Songs/…, /files/…, /backgroundImage
        assert tosu.cover_key(path) == 'trackcover_track.omg', path


def test_lunatic_is_in_difficulty_not_mods():
    # Overlays split mods.str into 2-letter mod icons, so it must never carry LUNATIC.
    s = STATES['playing']
    assert tosu.v1(s)['menu']['mods']['str'] == 'NM'
    assert tosu.v2(s)['play']['mods']['name'] == ''
    assert tosu.v1(s)['menu']['bm']['metadata']['difficulty'] == 'COSMOS Lv18 LUNATIC'


if __name__ == '__main__':
    tests = [f for n, f in sorted(globals().items()) if n.startswith('test_')]
    for t in tests:
        t()
    print(f'{len(tests)} checks passed')
