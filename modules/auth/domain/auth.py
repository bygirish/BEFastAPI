from typing import Literal

from pydantic import BaseModel


class Auth:
    user_id: str
    email_id: str
    is_email_id_verified: bool = False
    phone_number: str
    is_phone_number_verified: bool = False
    hashed_password: str
    created_at: int
    user_type: Literal['business', 'influencer', 'participant', 'admin']
    is_authentic_user_profile: bool = False
    activeAuthTokens: list[str] = []




