import http

from fastapi import APIRouter

router = APIRouter(prefix="/campaign", tags=['Campaign'])


@router.get("/v1")
def getCampaignDetails():
    """"""
