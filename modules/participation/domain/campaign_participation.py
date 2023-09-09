from typing import Literal, Union


from modules.campaign.domain.campaign import CampaignType


class UserMetaData:
    responseMetaData: any


class SurveyResponseData:
    responseMetaData: any


class QuizResponseData:
    responseMetaData: any


class CampaignParticipation:
    participation_id: str
    campaign_id: str
    campaign_title: str
    associated_campaign_id: str

    participant_id: str
    influencer_id: str
    submitted_at: int
    retry_attempts: int

    status: Literal["success", "failure"] = None

    campaign_type: CampaignType
    response: Union[UserMetaData, SurveyResponseData, QuizResponseData] = None
