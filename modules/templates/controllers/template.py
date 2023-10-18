import http

from fastapi import APIRouter

router = APIRouter(prefix="/templates", tags=['business'])


@router.get("/v1")
def getTemplatesByType():
    """"""


@router.get("/v1")
def getTemplateById():
    """"""


@router.post("/v1")
def createTemplate():
    """"""


@router.put("/v1")
def updateTemplate():
    """"""


@router.put("/v1")
def deleteTemplate():
    """"""
