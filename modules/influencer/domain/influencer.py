from modules.auth.domain.auth import Auth


class SocialPlatform:
    platform_name: str
    link: str


class InfluencerCampaign:
    campaign_id: str
    campaign_title: str
    associated_campaign_id: str
    campaign_link: str
    campaign_activated_at: int
    campaign_deactivated_at: int
    successful_participation_count: int
    fail_participation_count: int
    helpdesk_tickets: list[any]


class Influencer(Auth):
    id: str
    first_name: str
    last_name: str
    category: str
    tags: list[str]
    platform_links: list[SocialPlatform]
    campaign_list: list[InfluencerCampaign]
    user_type = 'influencer'





