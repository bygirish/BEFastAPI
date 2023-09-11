import http

from fastapi import APIRouter

router = APIRouter(prefix="/participants", tags=['Participants'])


@router.get("/v1")
def getParticipantDetails():
    """"""
