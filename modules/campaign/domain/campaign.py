from enum import Enum
from typing import Literal


class CampaignType(str, Enum):
    AcquireUserCampaign = "AcquireUserCampaign"
    SurveyCampaign = "SurveyCampaign"
    QuizCampaign = "QuizCampaign"


class AssociatedBusinessDetails:
    account_id: str
    business_title: str
    created_at: int
    created_by_id: str  # business member id
    create_by_name: str  # business member name


class Campaign:
    campaign_id: str
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

    associated_influencers: list[str] = []
    associate_business_details: AssociatedBusinessDetails = None
