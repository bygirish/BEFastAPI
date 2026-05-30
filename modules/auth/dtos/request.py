# from enum import Enum
from enum import Enum
from typing import Literal, Union

import pydantic
from pydantic import BaseModel

from modules.auth.domain.auth import ProfileType, Auth
from modules.auth.domain.auth_otp import EmailOTPUseCases, PhoneOTPUseCases


class CheckAuthDetailsWithEmailId(BaseModel):
    email_id: str
    campaign_id: Union[str, None]
    # profile_type: str


class CreateUserLeadWithEmailId(BaseModel):
    email_id: str
    password: str
    first_name: str
    last_name: str

    profile_type: ProfileType
    campaign_id: Union[str, None]

    def get_dict(self):
        return self.__dict__


class SendEmailOTPSchema(BaseModel):
    email_id: str
    use_case: EmailOTPUseCases


class VerifyEmailOTPSchema(BaseModel):
    email_id: str
    use_case: EmailOTPUseCases
    otp: str
    session_id: str


class UpdateAuthProfileData(BaseModel):
    profile_data: pydantic.dataclasses.dataclass(Auth)


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
