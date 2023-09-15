import http
from typing import Union, Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from modules.auth.domain.auth import Auth
from modules.auth.schemas.request import LoginWithEmailPasswordCreds, CreateUserSchema, \
    CheckAuthDetailsWithPhoneNumber, SendPhoneOTPSchema, VerifyPhoneOTPSchema
from modules.auth.use_cases.auth import login_with_email_password_use_case, \
    get_current_user_use_case, create_user_use_case
from schemas.exceptions import ApplicationException
from schemas.response import SuccessResponse, ErrorResponse, BaseResponse

router = APIRouter(prefix="/auth", tags=['Auth'])


@router.get('/check_user_exists-with-phone-number',
            summary="Get Auth Details based on phone number")
def check_user_exists_with_phone_number(req_body: CheckAuthDetailsWithPhoneNumber):
    """
    - fetch auth details with phone_number and check if they are present
    - create auth record with phone number and profile_type

    - For campaign participants, record the phone_number in campaign_participation db [It can be helpful,
    in case otp service is down]

    - If phone number is new then sendOTP for sign_up


    """

    try:
        resp = {
            "is_exists": True,
        }
        return SuccessResponse(resp).json_response()
    except ApplicationException as ae:
        print("Exception ", ae)
        return ErrorResponse([
            ae.__str__()
        ], ae.status_code).json_response()


@router.post('/send-phone-otp',
             summary="Send Phone OTP for different cases")
def send_phone_otp(req_body: SendPhoneOTPSchema):
    """
    - send OTP

    Use cases:
        login: 'login'


        signup: 'signup'


        change: 'change'



    # send response for
    - successful otp
    - failure otp
    - max_limit otp achieved

    """
    try:
        resp = {

        }
        return SuccessResponse(resp).json_response()
    except ApplicationException as ae:
        print("Exception ", ae)
        return ErrorResponse([
            ae.__str__()
        ], ae.status_code).json_response()


@router.post('/verify-phone-otp',
             summary="verify Phone OTP for different cases")
def verify_phone_otp(req_body: VerifyPhoneOTPSchema):
    """
    - verify OTP

    Use cases:
        login: 'login'
            - get user profile details based on the profile_type and send it in the response

        signup: 'signup'
            - update auth record for phone number with is_phone_verified
            - create profile record based on profile_type
            - send the profile_data it in the response

        change: 'change'
            - update auth record with new phone number with is_phone_verified
            - send "phone_updated" message in the response


    # send response for
    - successful otp verification along with
        - the above data based on the case
    - failure otp verification

    """
    try:
        resp = {

        }
        return SuccessResponse(resp).json_response()
    except ApplicationException as ae:
        print("Exception ", ae)
        return ErrorResponse([
            ae.__str__()
        ], ae.status_code).json_response()

@router.post('/send-email-otp',
             summary="Send email OTP for different cases")
def send_email_otp(req_body: SendPhoneOTPSchema):
    """
    - send Email OTP

    Use cases:
        change: 'change'



    # send response for
    - successful otp
    - failure otp
    - max_limit otp achieved

    """
    try:
        resp = {

        }
        return SuccessResponse(resp).json_response()
    except ApplicationException as ae:
        print("Exception ", ae)
        return ErrorResponse([
            ae.__str__()
        ], ae.status_code).json_response()


@router.post('/verify-email-otp',
             summary="verify email OTP for different cases")
def verify_email_otp(req_body: VerifyPhoneOTPSchema):
    """
    - verify OTP

    Use cases:

        change: 'change'
            - update auth record with new email-id with is_email_verified
            - send "email_updated" message in the response


    # send response for
    - successful otp verification along with
        - the above data based on the case
    - failure otp verification

    """
    try:
        resp = {

        }
        return SuccessResponse(resp).json_response()
    except ApplicationException as ae:
        print("Exception ", ae)
        return ErrorResponse([
            ae.__str__()
        ], ae.status_code).json_response()


@router.post('/update-password',
             summary="update password")
def update_password(password: str):
    """
        - update auth record with new password
    """
    try:
        resp = {

        }
        return SuccessResponse(resp).json_response()
    except ApplicationException as ae:
        print("Exception ", ae)
        return ErrorResponse([
            ae.__str__()
        ], ae.status_code).json_response()


@router.post('/verify-password',
             summary="verify password")
def verify_password(password: str):
    """
        - verify the entered password with the password present in the auth record

        response:
        - success
        - failure
    """
    try:
        resp = {

        }
        return SuccessResponse(resp).json_response()
    except ApplicationException as ae:
        print("Exception ", ae)
        return ErrorResponse([
            ae.__str__()
        ], ae.status_code).json_response()






# @router.post("/v1/login/email-password")
# def loginWithEmailPassword(creds: LoginWithEmailPasswordCreds):
#     """"""
#     try:
#         email, password = creds.dict().values()
#         print("email, password", email, password)
#         resp = login_with_email_password_use_case(email, password)
#
#         return SuccessResponse(resp).json_response()
#     except ApplicationException as ae:
#         return ErrorResponse([
#             ae.__str__()
#         ], ae.status_code).json_response()
#

# @router.get("/v1/user/me")
# async def get_current_user(
#         current_user: str = Depends(get_current_user_use_case)
# ):
#     print("current_user", current_user)
#     print("current_user dict", current_user.__dict__)
#     # return current_user
#     try:
#         return SuccessResponse({
#             "user_data": current_user.__dict__
#         }).json_response()
#     except ApplicationException as ae:
#         return ErrorResponse([
#             ae.__str__()
#         ], http.HTTPStatus.ALREADY_REPORTED).json_response()
