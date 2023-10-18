import json
from typing import Annotated
from uuid import uuid4

from fastapi import HTTPException, status, Depends
from jose import JWTError

from modules.auth.domain.auth import Auth, ProfileType
from modules.auth.domain.auth_otp import EmailOTP, EmailOTPUseCases
from modules.auth.domain.lead import Lead
from modules.auth.repositories.auth import get_user_by_email_id_repository, \
    create_user_lead_with_email_id_repository, \
    get_auth_user_with_email_id_repository, get_user_lead_with_email_id_repository, \
    create_sent_email_otp_repository, get_sent_email_otp_by_session_id_repository, \
    update_user_lead_repository, \
    create_auth_user_repository, get_sent_email_otp_by_email_id_repository
from modules.auth.dtos.request import CreateUserSchema, CreateUserLeadWithEmailId, \
    SendEmailOTPSchema, VerifyEmailOTPSchema
from modules.auth.utils.email_templates.send_signup_otp import send_signup_otp
from modules.auth.utils.otp import generate_otp, generate_session_id
from modules.auth.utils.ses import send_email_ses
from modules.auth.utils.utils import create_access_token, \
    oauth2_scheme, \
    get_jwt_token_payload, TokenData, get_password_hash, authenticate_user_by_email_id
from schemas.exceptions import ApplicationException, CustomHTTPException
from utils.data_generators import generate_unique_id_for_db
from utils.dynamodb import dynamo
from utils.time_utils import get_current_timestamp
from operator import itemgetter


def check_user_exists_with_email_id_use_case(email_id: str):
    auth_record = get_auth_user_with_email_id_repository(email_id)
    lead_record = get_user_lead_with_email_id_repository(email_id)

    is_lead_user = False
    is_auth_user = False

    if auth_record:
        is_lead_user = True
        is_auth_user = True
    if lead_record:
        is_lead_user = True
        is_auth_user = False

    return {
        "is_lead_user": is_lead_user,
        "is_auth_user": is_auth_user,
    }


def create_user_lead_with_email_id_use_case(payload: CreateUserLeadWithEmailId):
    payload_dict = payload.get_dict()
    # check if lead already exists with email_id
    existing_lead = get_user_lead_with_email_id_repository(payload_dict.get('email_id'))
    if existing_lead:
        return {
            "lead_id": existing_lead.get("lead_id", None),
            "message": "lead already exists"
        }

    lead = Lead(**{
        "lead_id": generate_unique_id_for_db(),
        "email_id": payload_dict.get('email_id'),
        "hashed_password": get_password_hash(payload_dict.get('password')),
        "first_name": payload_dict.get('first_name'),
        "last_name": payload_dict.get('last_name'),
        "user_profiles": [
            {
                "profile_type": payload_dict.get('profile_type'),
                "source_campaign": payload_dict.get('campaign_id', None)
            }
        ],
    })
    print("lead payload", lead.get_dict())
    is_created = create_user_lead_with_email_id_repository(lead)

    if is_created:
        email_payload = SendEmailOTPSchema(email_id=payload_dict.get('email_id'),
                                           use_case=EmailOTPUseCases.sign_up)
        print("email_payload", email_payload)
        # send_email_otp_use_case(email_payload)
        return {
            "lead_id": lead.lead_id
        }


def send_email_otp_use_case(payload: SendEmailOTPSchema):
    email_id = payload.email_id
    use_case = payload.use_case.value
    otp = generate_otp()
    session_id = generate_session_id()

    past_sent_otps = get_sent_email_otp_by_email_id_repository(email_id, 60)

    if past_sent_otps is not None and len(past_sent_otps) > 0:
        raise ApplicationException("Please wait for 1 minute since last attempt", status.HTTP_425_TOO_EARLY)

    email_otp_object = EmailOTP(**{
        "email_id": email_id,
        "is_verified": False,
        "use_case": use_case,
        "otp": str(otp),
        "sent_at": get_current_timestamp(),
        "verified_at": None,
        "session_id": session_id
    })

    is_created = create_sent_email_otp_repository(email_otp_object)

    if is_created:
        send_signup_otp(email_id, otp)
        return {
            "session_id": session_id,
            "message": "OTP sent successfully"
        }


def verify_email_otp_use_case(payload: VerifyEmailOTPSchema):
    email_id = payload.email_id
    use_case = payload.use_case
    otp = payload.otp
    session_id = payload.session_id
    print("payload", payload)
    latest_otp_record = get_sent_email_otp_by_session_id_repository(session_id, email_id)
    print("latest_otp_record", latest_otp_record)
    sent_otp, is_verified = (latest_otp_record["otp"], latest_otp_record["is_verified"]) if latest_otp_record is not None else (None, False)
    print("latest_otp_record", latest_otp_record, sent_otp == otp)

    if sent_otp is None or (sent_otp is not None and is_verified is True):
        raise CustomHTTPException('no sent otp found', status.HTTP_404_NOT_FOUND)

    else:
        if sent_otp == otp and is_verified is False:
            if use_case.value == EmailOTPUseCases.sign_up.value:
                # create_auth_record
                # update_lead_record
                # generate token
                latest_otp_record.update({
                    "is_verified": True,
                    "verified_at": get_current_timestamp(),
                    "updated_at": get_current_timestamp(),
                })
                lead_record_dict = get_user_lead_with_email_id_repository(email_id)

                if lead_record_dict is not None:

                    lead_record_dict['is_email_id_verified'] = True
                    lead_record = Lead(**lead_record_dict)

                    auth_record_dict = {**lead_record_dict}
                    auth_record_dict['user_id'] = auth_record_dict.pop('lead_id')
                    auth_record = Auth(**auth_record_dict)

                    update_otp_verification_transaction_item = {
                            "action": "Put",
                            "TableName": EmailOTP.get_table_name(),
                            "Item": latest_otp_record
                        }

                    response, st = create_auth_user_repository(auth_record, lead_record, [update_otp_verification_transaction_item])

                    if st is True:
                        # generate auth token
                        access_token = create_access_token(
                            data={"sub": json.dumps({
                                "email_id": email_id,
                                "user_id": auth_record.user_id,
                            })}
                        )
                        return {
                            "access_token": access_token,
                            "message": "OTP verified. Auth account created successfully",
                        }
                    else:
                        return {
                            "message": "OTP couldn't be verified. Auth account couldn't be created",
                        }
                else:
                    raise CustomHTTPException('no lead record found for the email id',
                                              status.HTTP_404_NOT_FOUND)

            return True
        else:
            return False

    # is_created = send_email_otp_repository(email_otp_object)
    #
    # if is_created:
    #     send_signup_otp(email_id, otp)
    #     return {
    #         "message": "OTP sent successfully"
    #     }


def __convert_lead_to_auth_user():
    pass


def login_with_email_password_use_case(email: str, password: str):
    print("In login_with_email_password_use_case", email, password)
    user = authenticate_user_by_email_id(email, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": json.dumps({
            "email_id": user.email_id,
            "user_id": user.user_id
        })}
    )
    return {"access_token": access_token, "token_type": "bearer"}

    # check if user exists for email
    # if exists then match the hashed password
    # If matched then create token & store it in db
    # If user doesn't exist then create one in the db and return response accordingly with user_id


async def get_current_user_use_case(token: Annotated[str, Depends(oauth2_scheme)]) -> Auth:
    print("In get_current_user_use_case")
    # get the user profile based on the jwt token
    try:
        payload = get_jwt_token_payload(token)
        data = json.loads(payload.get("sub"))
        email_id, user_id = data.values()
        if email_id is None:
            raise ApplicationException('Email id not found in token', status.HTTP_401_UNAUTHORIZED)
        token_data = TokenData(user_id=user_id, email_id=email_id)
    except JWTError as je:
        raise CustomHTTPException('Error in retrieving jwt token payload',
                                  status.HTTP_401_UNAUTHORIZED, je.__str__())
    user: Auth = get_user_by_email_id_repository(email_id=token_data.email_id)
    if user is None:
        raise CustomHTTPException('user not found for jwt token', status.HTTP_401_UNAUTHORIZED)
    return user


def create_user_use_case(new_user: CreateUserSchema):
    email_id, password = new_user.__dict__.values()

    print(email_id, password)

    user = get_user_by_email_id_repository(email_id)
    if user is not None:
        raise ApplicationException(
            "User with this email already exist",
            status.HTTP_400_BAD_REQUEST,
        )

    user = Auth(**{
        'user_id': str(uuid4()),
        'email_id': email_id,
        'hashed_password': get_password_hash(password),
    })
    create_user_repository(user)
    return {
        "message": f'user created successfully {user}'
    }


def login_with_phone_password_use_case(phone: str, password: str):
    print("In login_with_phone_password_use_case")
    # check if user exists for phone
    # if exists then match the hashed password
    # If matched then create token & store it in db
    # If user doesn't exist then create one in the db and return response accordingly with user_id


def login_with_phone_otp_use_case(phone: str):
    print("In login_with_phone_otp_use_case")
    # send OTP
    # check if user exists for phone then return with user_id
    # If user doesn't exist then create one in the db and return response accordingly with user_id


def verify_phone_login_otp_use_case(user_id: str, phone: str, otp: str):
    print("verify_phone_login_otp_use_case")
    # verify OTP using verify_mobile_otp_use_case
    # if verified then
    # create Token
    # send user profile data


def send_mobile_otp_use_case(phone: str):
    print("In send_mobile_otp_use_case")


def verify_mobile_otp_use_case(phone: str, otp: str):
    print("In verify_mobile_otp_use_case")
    # return with True or False for verification


def login_with_email_otp_use_case(email: str):
    print("In login_with_email_otp_use_case")
    # send OTP
    # check if user exists for email then return with user_id
    # If user doesn't exist then create one in the db and return response accordingly with user_id


def verify_email_login_otp_use_case(user_id: str, phone: str, otp: str):
    print("verify_email_login_otp_use_case")
    # verify OTP using verify_email_otp_use_case
    # if verified then
    # create Token
    # send user profile data


# def send_email_otp_use_case(email: str):
#     print("In send_email_otp_use_case")


# def verify_email_otp_use_case(email: str, otp: str):
#     print("In verify_email_otp_use_case")
#     # return with True or False for verification


def create_user_profile_use_case(profile_data: any):
    print("In create_user_profile_use_case")
    # generate user_id and create a fresh record in the db
    # if password is present then hash it and save it


def update_user_profile_use_case(user_id: str, profile_data: any):
    print("In create_user_profile_use_case")
    # get the user profile data
    # ensure the logic for "is_authentic_user_profile"
    # update the profile data in the db
    # if password is present then hash it and save it


def get_user_profile_use_case(email: str = None, phone: str = None, user_id: str = None):
    print("In get_user_profile_use_case")
    # get the user profile based on whatever arg is present


def create_auth_token(profile_data: any):
    print("In create_auth_token")
    # create auth token and save it in the db


def logout_user_use_case(user_id: str):
    print("In logout_user_use_case")
    # put the jwt token in the blacklist token db


def authenticate_authorize_user_use_case(auth_token: str, allowed_user_roles: list[str] = [],
                                         allowed_user_types: list[str] = []):
    print("In authenticate_user_use_case")
    # validate the jwt token based on expiry time
    # if valid then extract the user_id, user_type and user_role
    # validate the user_type & user_role with allowed_user_types & allowed_user_roles
