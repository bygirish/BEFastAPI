import http

from fastapi import APIRouter

router = APIRouter(prefix="/influencer", tags=[])


@router.get("/v1")
def getInfluencerDetails():
    """"""
