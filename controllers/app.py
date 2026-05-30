from fastapi import APIRouter

from modules.auth.controllers import auth
from modules.business.controllers import business
from modules.campaign.controllers import campaign
from modules.influencer.controllers import influencer
from modules.participants.controllers import partcipants
from modules.participation.controllers import participation
from modules.file.controllers import file


def get_app_router():
    router = APIRouter()
    router.include_router(auth.router)
    router.include_router(business.router)
    router.include_router(campaign.router)
    router.include_router(influencer.router)
    router.include_router(partcipants.router)
    router.include_router(participation.router)
    router.include_router(file.router)
    return router
