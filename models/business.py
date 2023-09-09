from models.auth import Auth


# class BusinessTeamMembers(Auth):
#     first_name: str
#     last_name: str
#
class Business(Auth):
    name: str
    category: str
    tags: list[str] = []
    authPayload: any
    website_link: str
    user_type = 'business'
    # team_members: list[BusinessTeamMembers] = []
