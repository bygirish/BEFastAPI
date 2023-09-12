import json
from typing import Annotated
from uuid import uuid4

from fastapi import HTTPException, status, Depends
from jose import JWTError

from modules.auth.domain.auth import Auth
from modules.auth.repositories.auth import get_user_by_user_id_repository, \
    get_user_by_email_id_repository, create_user_repository
from modules.auth.schemas.request import CreateUserSchema
from modules.auth.utils.utils import create_access_token, \
    oauth2_scheme, \
    get_jwt_token_payload, TokenData, get_password_hash, authenticate_user_by_email_id
from schemas.exceptions import ApplicationException, CustomHTTPException


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


def send_email_otp_use_case(email: str):
    print("In send_email_otp_use_case")


def verify_email_otp_use_case(email: str, otp: str):
    print("In verify_email_otp_use_case")
    # return with True or False for verification


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
        raise CustomHTTPException('Error in retrieving jwt token payload', status.HTTP_401_UNAUTHORIZED, je.__str__())
    user: Auth = get_user_by_email_id_repository(email_id=token_data.email_id)
    if user is None:
        raise CustomHTTPException('user not found for jwt token', status.HTTP_401_UNAUTHORIZED)
    return user


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
