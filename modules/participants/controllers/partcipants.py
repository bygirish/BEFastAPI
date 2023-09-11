import http

from fastapi import APIRouter

router = APIRouter(prefix="/participants", tags=[])


@router.get("/v1")
def getParticipantDetails():
    """"""
