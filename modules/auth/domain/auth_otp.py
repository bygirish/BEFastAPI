from enum import Enum
from typing import Literal

from pydantic import BaseModel


class EmailOTPUseCases(Enum):
    sign_up = 'sign_up'
    login = 'login'
    change = 'change'


class EmailOTP:
    def __init__(self, email_id: str = None, lead_id: str = None,
                 user_id: bool = False,
                 is_verified: bool = False,
                 use_case: EmailOTPUseCases = None,

                 otp: str = None,
                 sent_at: int = None,
                 verified_at: int = None,
                 session_id: str = None,
                 **kwargs):
        self.email_id = email_id
        self.use_case: EmailOTPUseCases = use_case
        # self.lead_id = lead_id # Make this None, in case of email-otp-change
        # self.user_id = user_id  # Make this None, in case of email-otp-change

        self.is_verified = is_verified  # Make this False, in case of email-otp-change
        self.otp = otp
        self.sent_at = sent_at
        self.verified_at = verified_at
        self.session_id = session_id

        # self.use_case = use_case

        # self.sent_at = sent_at
        # self.otp_verified_at = otp_verified_at

    @staticmethod
    def get_table_name():
        return "email_otp"

    def get_dict(self):
        return self.__dict__


class PhoneOTPUseCases(Enum):
    change = 'change'
    redeem = 'redeem_credits'


class PhoneOTP:

    def __init__(self, reference_id: str = None, lead_id: str = None,
                 user_id: bool = False,
                 phone_number: str = None,
                 is_phone_number_verified: bool = False,
                 sent_at: int = None,
                 use_case: EmailOTPUseCases = None, **kwargs):
        self.use_case = use_case
        self.reference_id = reference_id
        self.lead_id = lead_id
        self.user_id = user_id
        self.sent_at = sent_at
        self.phone_number = phone_number
        self.is_phone_number_verified = is_phone_number_verified

    @staticmethod
    def get_table_name():
        return "phone_otp"

    def get_dict(self):
        return self.__dict__
