import http

from fastapi import APIRouter

router = APIRouter(prefix="/participation", tags=['Participation'])


@router.get("/v1")
def getParticipationDetails():
    """"""
