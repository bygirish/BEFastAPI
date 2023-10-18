from modules.auth.domain.auth import Auth


class BusinessMember(Auth):
    business_member_id: str = None
    first_name: str
    last_name: str
    # user_type = 'business_member'
    business_account_id: str = None

    # role: str = None

class Business:
    business_account_id: str = None
    name: str = None
    category: str = None
    tags: list[str] = []
    authPayload: any = None
    website_link: str = None
    user_type = 'business'
    team_members: list[BusinessMember] = []




