"""Track jackets, served where overlays look for beatmap backgrounds."""
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from kalo import tosu
from kalo.game.reader import reader

router = APIRouter()
Side = Annotated[int | None, Query(ge=1, le=4096)]


@router.get('/Songs/{name:path}')           # tosu v1 / gosumemory
@router.get('/files/beatmap/{name:path}')   # tosu v2
def jacket(name: str, width: Side = None, height: Side = None, crop: bool = False):
    png = reader.covers and reader.covers.png(tosu.cover_key(name), width, height, crop)
    if not png:
        raise HTTPException(404, 'no jacket')
    return Response(png, media_type='image/png')


@router.get('/backgroundImage')
def background_image(width: Side = None, height: Side = None, crop: bool = False):
    """StreamCompanion: the current map's jacket, sized to the overlay's box (crop=1 fills and center-crops)."""
    return jacket(tosu.play_or_empty(reader.state).get('cover', ''), width, height, crop)
