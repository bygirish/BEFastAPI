from typing import Literal, Union

from pydantic import BaseModel

ProfileType = Literal['business', 'influencer', 'admin']


class UserProfile:
    profile_type: ProfileType = None
    profile_id: Union[str, None] = None
    source_campaign: Union[str, None] = None


class Auth:
    # user_id: str = None
    # email_id: str = None
    # is_email_id_verified: bool = False
    # phone_number: str = None
    # is_phone_number_verified: bool = False
    # hashed_password: str = None
    #
    # user_profiles: list[UserProfile] = []
    # is_complete_authentic_user: bool = False
    # activeAuthTokens: list[str] = []

    def __init__(self, user_id: str = None, email_id: str = None,
                 is_email_id_verified: bool = False,
                 phone_number: str = None,
                 is_phone_number_verified: str = None,
                 hashed_password: str = None,
                 user_profiles: list[type(UserProfile)] = [],
                 is_complete_authentic_user: bool = False, active_auth_tokens: list[str] = [], updated_at: int = None, **kwargs):
        self.active_auth_tokens = active_auth_tokens
        self.is_phone_number_verified = is_phone_number_verified
        self.is_complete_authentic_user = is_complete_authentic_user
        self.user_profiles = user_profiles
        self.is_email_id_verified = is_email_id_verified
        self.user_id = user_id
        self.email_id = email_id
        self.hashed_password = hashed_password
        self.phone_number = phone_number
        self.updated_at = updated_at
        # pass

    @staticmethod
    def get_table_name():
        return "auth"

    def get_dict(self):
        return self.__dict__
