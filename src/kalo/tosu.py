"""Reader state -> the JSON shapes overlays expect: tosu v1 (gosumemory), tosu v2, StreamCompanion tokens, and SP.

Pure functions of the state dict from kalo.game.reader, so they can be checked without the game running.
KALPA has no pp, so every pp field carries Stellar Point (SP).
"""
from kalo.stellar import stellar_point

ACC_STEPS = (100, 99, 98, 97, 96, 95)
# osu! grade enum as StreamCompanion overlays index it (0 SSH .. 7 D)
SC_GRADE = {'P': 2, 'S++': 3, 'S+': 3, 'S': 3, 'A+': 4, 'A': 4, 'B': 5, 'C': 6, 'F': 7}
SC_STATUS = {'offline': 0, 'menu': 1, 'songselect': 1, 'playing': 2, 'results': 32}
TOSU_STATE = {'offline': (0, 'menu'), 'menu': (0, 'menu'), 'songselect': (5, 'selectPlay'),
              'playing': (2, 'play'), 'results': (7, 'resultScreen')}
MANIA = {'number': 3, 'name': 'mania'}


def play_or_empty(s):
    return s.get('play') or {}


def diff_name(pl):
    if not pl:
        return ''
    return f"{pl['mode_name']} Lv{pl['level']}" + (' LUNATIC' if pl['lunatic'] else '')


def acc_table(pl):
    """pp-at-accuracy table, as SP."""
    if not pl:
        return {str(a): 0 for a in ACC_STEPS}
    return {str(a): stellar_point(pl['level'], a * 10_000, pl['lunatic']) for a in ACC_STEPS}


def cover_file(pl):
    return f"{pl['cover']}.png" if pl.get('cover') else ''


def cover_key(path):
    """Inverse of cover_file. Keys contain dots (trackcover_track.omg), so only a .png suffix is removed."""
    return path.rsplit('/', 1)[-1].removesuffix('.png')


def sp_block(s):
    """The SP view of the current state (also /json/sp)."""
    pl, prof = play_or_empty(s), s.get('profile') or {}
    return {
        'status': s['status'],
        'profile': {'name': prof.get('name', ''), 'lane4': prof.get('sp4k', 0), 'lane5': prof.get('sp5k', 0)},
        'play': pl and {k: pl.get(k) for k in (  # song select has map fields only
            'map_id', 'title', 'level', 'keys', 'mode_name', 'lunatic', 'rate_now', 'rate_max', 'rank', 'rank_max',
            'sp_now', 'sp_max', 'sp_ap', 'sp_peak', 'sp_best', 'counted', 'profile_after', 'profile_delta')},
    }


def v1(s):
    pl, prof = play_or_empty(s), s.get('profile') or {}
    state = TOSU_STATE[s['status']][0]
    hits = {'300': pl.get('great', 0), 'geki': pl.get('perfect', 0), '100': pl.get('good', 0), 'katu': 0,
            '50': 0, '0': pl.get('miss', 0), 'sliderBreaks': 0}
    return {
        'settings': {'showInterface': False, 'folders': {'game': '', 'skin': '', 'songs': ''}},
        'menu': {
            'mainMenu': {'bassDensity': 0}, 'state': state, 'gameMode': 3, 'isChatEnabled': 0,
            'bm': {
                'time': {'firstObj': 0, 'current': pl.get('time_ms', 0), 'full': pl.get('length_ms', 0),
                         'mp3': pl.get('length_ms', 0)},
                'id': pl.get('map_id', 0), 'set': pl.get('track_id', 0), 'md5': str(pl.get('map_id', '')),
                'rankedStatus': 0,
                'metadata': {'artist': pl.get('artist', ''), 'artistOriginal': pl.get('artist', ''),
                             'title': pl.get('title', ''), 'titleOriginal': pl.get('title', ''),
                             'mapper': 'KALPA', 'difficulty': diff_name(pl)},
                'stats': {'AR': 0, 'CS': pl.get('keys', 0), 'OD': 0, 'HP': 0, 'SR': pl.get('level', 0),
                          'BPM': {'min': pl.get('bpm_min', 0), 'max': pl.get('bpm_max', 0)},
                          'fullSR': pl.get('level', 0), 'memoryAR': 0, 'memoryCS': pl.get('keys', 0),
                          'memoryOD': 0, 'memoryHP': 0, 'maxCombo': pl.get('notes', 0)},
                'path': {'full': cover_file(pl), 'folder': '', 'file': '', 'bg': cover_file(pl), 'audio': ''},
            },
            'mods': {'num': 0, 'str': 'NM'},  # Lunatic is in the difficulty name; overlays split mods.str into 2-letter mods
            'pp': {**acc_table(pl), 'strains': []},
        },
        'gameplay': {
            'gameMode': 3, 'name': prof.get('name', ''), 'score': pl.get('score', 0),
            'accuracy': pl.get('rate_now', 0) / 10_000,
            'combo': {'current': pl.get('combo', 0), 'max': pl.get('max_combo', 0)},
            'hp': {'normal': pl.get('hp', 0), 'smooth': pl.get('hp', 0)},
            'hits': {**hits, 'grade': {'current': pl.get('rank', ''), 'maxThisPlay': pl.get('rank_max', '')},
                     'unstableRate': 0, 'hitErrorArray': []},
            'pp': {'current': pl.get('sp_now', 0), 'fc': pl.get('sp_max', 0), 'maxThisPlay': pl.get('sp_peak', 0)},
            'keyOverlay': {}, 'leaderboard': {'hasLeaderboard': False, 'isVisible': False, 'ourplayer': {}, 'slots': []},
            'sp': sp_block(s)['play'] or {},
        },
        'resultsScreen': {'name': prof.get('name', ''), 'score': pl.get('score', 0), 'maxCombo': pl.get('max_combo', 0),
                          'mods': {'num': 0, 'str': ''}, **hits},
        'userProfile': {'name': prof.get('name', ''), 'sp': sp_block(s)['profile']},
        'tourney': {},
    }


def v2(s):
    pl, prof = play_or_empty(s), s.get('profile') or {}
    num, name = TOSU_STATE[s['status']]
    hits = {'0': pl.get('miss', 0), '50': 0, '100': pl.get('good', 0), '300': pl.get('great', 0),
            'geki': pl.get('perfect', 0), 'katu': 0, 'sliderBreaks': 0, 'sliderEndHits': 0, 'sliderTickHits': 0}
    acc = pl.get('rate_now', 0) / 10_000
    mods = {'checksum': '', 'number': 0, 'name': '', 'array': [], 'rate': 1}  # Lunatic: see diff_name
    pp_detail = lambda total: {'aim': 0, 'speed': 0, 'accuracy': 0, 'difficulty': 0, 'flashlight': 0, 'total': total}
    lane_sp = prof.get('sp4k' if pl.get('keys', 4) == 4 else 'sp5k', 0)
    return {
        'client': 'kalpa', 'server': '', 'state': {'number': num, 'name': name},
        'session': {'playTime': 0, 'playCount': 0},
        'settings': {'interfaceVisible': False, 'replayUIVisible': False, 'mode': MANIA,
                     'skin': {'name': ''}, 'resolution': {}, 'client': {'updateAvailable': False, 'branch': 0, 'version': ''}},
        'profile': {'userStatus': {'number': 0, 'name': ''}, 'banchoStatus': {'number': 0, 'name': ''},
                    'id': 0, 'name': prof.get('name', ''), 'mode': MANIA, 'rankedScore': 0, 'level': 0,
                    'accuracy': 0, 'pp': lane_sp, 'playCount': 0, 'globalRank': 0,
                    'countryCode': {'number': 0, 'name': ''}, 'backgroundColour': '',
                    'sp': sp_block(s)['profile']},
        'beatmap': {
            'isKiai': False, 'isBreak': False, 'isConvert': False,
            'time': {'live': pl.get('time_ms', 0), 'firstObject': 0, 'lastObject': pl.get('length_ms', 0),
                     'mp3Length': pl.get('length_ms', 0)},
            'status': {'number': 0, 'name': 'unknown'}, 'checksum': str(pl.get('map_id', '')),
            'id': pl.get('map_id', 0), 'set': pl.get('track_id', 0), 'mode': MANIA,
            'artist': pl.get('artist', ''), 'artistUnicode': pl.get('artist', ''),
            'title': pl.get('title', ''), 'titleUnicode': pl.get('title', ''),
            'mapper': 'KALPA', 'version': diff_name(pl),
            'stats': {'stars': {'live': pl.get('level', 0), 'total': pl.get('level', 0)},
                      'ar': {'original': 0, 'converted': 0}, 'cs': {'original': pl.get('keys', 0), 'converted': pl.get('keys', 0)},
                      'od': {'original': 0, 'converted': 0}, 'hp': {'original': 0, 'converted': 0},
                      'bpm': {'common': pl.get('bpm_max', 0), 'min': pl.get('bpm_min', 0), 'max': pl.get('bpm_max', 0),
                              'realtime': pl.get('bpm_max', 0)},
                      'objects': {'circles': 0, 'sliders': 0, 'spinners': 0, 'holds': 0, 'total': pl.get('notes', 0)},
                      'maxCombo': pl.get('notes', 0)},
        },
        'play': {
            'playerName': prof.get('name', ''), 'mode': MANIA, 'score': pl.get('score', 0), 'accuracy': acc,
            'healthBar': {'normal': pl.get('hp', 0), 'smooth': pl.get('hp', 0)}, 'hits': hits, 'hitErrorArray': [],
            'combo': {'current': pl.get('combo', 0), 'max': pl.get('max_combo', 0)}, 'mods': mods,
            'rank': {'current': pl.get('rank', ''), 'maxThisPlay': pl.get('rank_max', '')},
            'pp': {'current': pl.get('sp_now', 0), 'fc': pl.get('sp_max', 0), 'maxAchieved': pl.get('sp_peak', 0),
                   'maxAchievable': pl.get('sp_ap', 0),
                   'detailed': {'current': pp_detail(pl.get('sp_now', 0)), 'fc': pp_detail(pl.get('sp_max', 0))}},
            'unstableRate': 0,
            'sp': sp_block(s)['play'] or {},
        },
        'leaderboard': [],
        'performance': {'accuracy': acc_table(pl), 'graph': {'series': [], 'xaxis': []}},
        'resultsScreen': {'scoreId': 0, 'name': prof.get('name', ''), 'mode': MANIA, 'score': pl.get('score', 0),
                          'accuracy': acc, 'hits': hits, 'mods': mods, 'maxCombo': pl.get('max_combo', 0),
                          'rank': pl.get('rank', ''), 'pp': {'current': pl.get('sp_now', 0), 'fc': pl.get('sp_max', 0)},
                          'createdAt': ''},
        'folders': {'game': '', 'skin': '', 'songs': '', 'beatmap': ''},
        'files': {'beatmap': '', 'background': cover_file(pl), 'audio': ''},
        'directPath': {'beatmapFile': '', 'beatmapBackground': cover_file(pl), 'beatmapAudio': '',
                       'beatmapFolder': '', 'skinFolder': ''},
    }


def v2_precise(s):
    return {'currentTime': play_or_empty(s).get('time_ms', 0), 'keys': {}, 'hitErrors': [], 'tourney': []}


def sc_tokens(s):
    """StreamCompanion token names that overlays commonly read, plus sp* tokens."""
    pl, prof = play_or_empty(s), s.get('profile') or {}
    return {
        'status': SC_STATUS[s['status']], 'rawStatus': SC_STATUS[s['status']], 'gameMode': 'OsuMania',
        'titleRoman': pl.get('title', ''), 'titleUnicode': pl.get('title', ''),
        'artistRoman': pl.get('artist', ''), 'artistUnicode': pl.get('artist', ''),
        'creator': 'KALPA', 'diffName': diff_name(pl), 'mods': '',
        'mapid': pl.get('map_id', 0), 'mapsetid': pl.get('track_id', 0), 'md5': str(pl.get('map_id', '')),
        'mStars': pl.get('level', 0), 'mCS': pl.get('keys', 0),
        'mMainBpm': pl.get('bpm_max', 0), 'mMinBpm': pl.get('bpm_min', 0), 'mMaxBpm': pl.get('bpm_max', 0),
        'time': pl.get('time_ms', 0) / 1000, 'totaltime': pl.get('length_ms', 0),
        'backgroundImageLocation': pl.get('cover', ''), 'osuFileName': '', 'dir': '',
        'username': prof.get('name', ''), 'score': pl.get('score', 0), 'acc': pl.get('rate_now', 0) / 10_000,
        'combo': pl.get('combo', 0), 'currentMaxCombo': pl.get('max_combo', 0), 'maxCombo': pl.get('notes', 0),
        'geki': pl.get('perfect', 0), 'c300': pl.get('great', 0), 'katsu': 0, 'c100': pl.get('good', 0),
        'c50': 0, 'miss': pl.get('miss', 0), 'sliderBreaks': 0, 'playerHp': pl.get('hp', 0),
        'grade': SC_GRADE.get(pl.get('rank'), 9), 'maxGrade': SC_GRADE.get(pl.get('rank_max'), 9),
        'ppIfMapEndsNow': pl.get('sp_now', 0), 'ppIfRestFced': pl.get('sp_max', 0),
        'noChokePp': pl.get('sp_max', 0), 'osu_mSSPP': pl.get('sp_ap', 0), 'mania_m1000000PP': pl.get('sp_ap', 0),
        'spIfMapEndsNow': pl.get('sp_now', 0), 'spIfRestFced': pl.get('sp_max', 0), 'spAllPerfect': pl.get('sp_ap', 0),
        'spBest': pl.get('sp_best', 0), 'spProfileAfter': pl.get('profile_after') or 0,
        'spProfileDelta': pl.get('profile_delta') or 0,
        'spProfile4K': prof.get('sp4k', 0), 'spProfile5K': prof.get('sp5k', 0),
        'kalpaRank': pl.get('rank', ''), 'kalpaRate': pl.get('rate_now', 0), 'kalpaLunatic': pl.get('lunatic', False),
    }
