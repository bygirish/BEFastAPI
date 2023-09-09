from enum import Enum
from typing import Literal


class CampaignType(str, Enum):
    AcquireUserCampaign = "AcquireUserCampaign"
    SurveyCampaign = "SurveyCampaign"
    QuizCampaign = "QuizCampaign"


class Campaign:
    id: str
    title: str
    description: str
    images: list[str] = []
    video: str
    start_date: int
    end_date: int
    limit: int
    category: str
    tags: list[str] = []
    participants_reward: str
    status: Literal['active', 'inactive'] = 'inactive'
    type: CampaignType = None


