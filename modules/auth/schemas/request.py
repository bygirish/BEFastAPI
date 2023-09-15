from enum import Enum
from typing import Literal

from pydantic import BaseModel


class CheckAuthDetailsWithPhoneNumber(BaseModel):
    phone_number: str
    campaign_id: str
    profile_type: str


class PhoneOTPUseCases(Enum):
    login: 'login'
    signup: 'signup'
    change: 'change'


class PhoneOTPUseCases(Enum):
    login: 'login'
    signup: 'signup'
    change: 'change'


class SendPhoneOTPSchema(BaseModel):
    phone_number: str
    use_case: PhoneOTPUseCases


class VerifyPhoneOTPSchema(BaseModel):
    phone_number: str
    use_case: PhoneOTPUseCases




# class AuthRecordSchema(BaseModel):
#     user_id: str
#     email_id: str
#     phone_number: str
#     hashed_password: str

# user_profiles: list[UserProfile] = []
# profile_type: Literal['business', 'influencer', 'participants', 'admin'] = None
# profile_id: str = None  # business_member_id | influencer_id | participant_id
# is_complete_authentic_user: bool = False
# activeAuthTokens: list[str] = []


class LoginWithEmailPasswordCreds(BaseModel):
    email: str
    password: str


class CreateUserSchema(BaseModel):
    email_id: str
    password: str

    # def __init__(self, **kwargs):
    #     super().__init__(self)
    #     self.email_id = kwargs["email_id"]
    #     self.password = kwargs["password"]
