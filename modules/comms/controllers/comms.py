import http

from fastapi import APIRouter

router = APIRouter(prefix="/comms", tags=['business'])


@router.get("/v1")
def sendComms():
    """"""


def scheduleComms():
    """"""