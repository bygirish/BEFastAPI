from modules.auth.domain.auth import Auth
from typing import Literal, List, Dict


class SocialPlatform:
    platform_name: str
    link: str


class ParticipantCampaign:
    participation_id: str
    campaign_id: str
    campaign_title: str
    associated_campaign_id: str
    status: Literal["success", "failure"]
    earned_amount: int
    submitted_at: int
    retry_attempts: int
    helpdesk_tickets: list[any]


class Participant(Auth):
    id: str
    first_name: str
    last_name: str
    personal_information: Dict[str, any] = None
    campaign_list: List[ParticipantCampaign]
    user_type = 'participants'





