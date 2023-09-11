import http

from fastapi import APIRouter

router = APIRouter(prefix="/influencer", tags=['Influencer'])


@router.get("/v1")
def getInfluencerDetails():
    """"""
