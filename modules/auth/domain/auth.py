from typing import Literal

from pydantic import BaseModel


class Auth:
    user_id: str
    email_id: str
    # is_email_id_verified: bool = False
    # phone_number: str
    # is_phone_number_verified: bool = False
    hashed_password: str
    # created_at: int
    # user_type: Literal['business', 'influencer', 'participants', 'admin']
    # is_authentic_user_profile: bool = False
    # activeAuthTokens: list[str] = []

    def __init__(self, **kwargs):
        self.user_id = kwargs['user_id']
        self.email_id = kwargs['email_id']
        self.hashed_password = kwargs['hashed_password']
        # pass




