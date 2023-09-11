import http

from fastapi import APIRouter

router = APIRouter(prefix="/campaign", tags=[])


@router.get("/v1")
def getCampaignDetails():
    """"""
