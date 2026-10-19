"""SP for any map and accuracy; /api/calculate/pp keeps tosu's shape with SP in the pp slot."""
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from kalo.game.reader import reader

router = APIRouter(prefix='/api/calculate')

MapId = Annotated[int | None, Query(alias='mapId')]
Level = Annotated[int | None, Query(ge=0)]
Rate = Annotated[int | None, Query(ge=0, le=1_000_000, description='1000000 = 100%')]
Acc = Annotated[float | None, Query(ge=0, le=100, description='percent; ignored when rate is given')]


def calculate(map_id, level, rate, acc, lunatic):
    """Defaults to the map being played or selected; rate defaults to the current one."""
    if rate is None and acc is not None:
        rate = round(acc * 10_000)
    result = reader.calc(map_id=map_id, rate=rate, lunatic=lunatic, level=level)
    if not result:
        raise HTTPException(404, 'unknown map: pass mapId or level, or select a map in game')
    return result


@router.get('/sp')
def calculate_sp(map_id: MapId = None, level: Level = None, rate: Rate = None, acc: Acc = None,
                 lunatic: bool | None = None):
    return calculate(map_id, level, rate, acc, lunatic)


@router.get('/pp')
def calculate_pp(map_id: MapId = None, level: Level = None, rate: Rate = None, acc: Acc = None,
                 lunatic: bool | None = None):
    r = calculate(map_id, level, rate, acc, lunatic)
    return {'difficulty': {'stars': r['level']}, 'pp': r['sp'], 'sp': r['sp'],
            'accuracy': r['rate'] / 10_000, 'rank': r['rank']}
