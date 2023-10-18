from enum import Enum
from typing import Literal

from pydantic import BaseModel

from modules.auth.domain.auth import UserProfile


class LeadStatus(Enum):
    pending = 'pending'
    auth_created = 'auth_created'


class Lead:
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

    def __init__(self, lead_id: str = None, email_id: str = None,
                 is_email_id_verified: bool = False,
                 phone_number: str = None,
                 is_phone_number_verified: str = None,
                 hashed_password: str = None,
                 user_profiles: list[UserProfile] = [], first_name: str = None,
                 last_name: str = None, lead_status: LeadStatus = LeadStatus.pending.value,
                 updated_at: int = None, **kwargs):
        self.lead_id = lead_id
        self.email_id = email_id
        self.is_email_id_verified = is_email_id_verified
        self.hashed_password = hashed_password
        self.first_name = first_name
        self.last_name = last_name

        self.phone_number = phone_number
        self.is_phone_number_verified = is_phone_number_verified
        self.user_profiles = user_profiles

        self.lead_status: LeadStatus = lead_status
        self.updated_at = updated_at

    @staticmethod
    def get_table_name():
        return "user_leads"

    def get_dict(self):
        return self.__dict__
