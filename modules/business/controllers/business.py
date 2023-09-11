import http

from fastapi import APIRouter

router = APIRouter(prefix="/business", tags=['business'])


@router.get("/v1")
def getBusinessDetails():
    """"""
