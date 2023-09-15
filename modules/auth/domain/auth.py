from typing import Literal

from pydantic import BaseModel



class UserProfile:
    profile_type: Literal['business', 'influencer', 'participants', 'admin'] = None
    profile_id: str = None

class Auth:
    user_id: str = None
    email_id: str = None
    is_email_id_verified: bool = False
    phone_number: str = None
    is_phone_number_verified: bool = False
    hashed_password: str = None

    user_profiles: list[UserProfile] = []
    # profile_type: Literal['business', 'influencer', 'participants', 'admin'] = None
    # profile_id: str = None  # business_member_id | influencer_id | participant_id
    is_complete_authentic_user: bool = False
    activeAuthTokens: list[str] = []

    def __init__(self, user_id=None, email_id=None, is_email_id_verified=False, phone_number=None,
                 is_phone_number_verified=False, hashed_password=None, user_profiles=[], is_complete_authentic_user=False, active_auth_tokens=[]):
        self.active_auth_tokens = active_auth_tokens
        self.is_phone_number_verified = is_phone_number_verified
        self.is_complete_authentic_user = is_complete_authentic_user
        self.user_profiles = user_profiles
        self.is_email_id_verified = is_email_id_verified
        self.user_id = user_id
        self.email_id = email_id
        self.hashed_password = hashed_password
        self.phone_number = phone_number
        # pass

    @staticmethod
    def get_table_name():
        return "auth"
