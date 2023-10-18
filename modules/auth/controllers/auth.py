import http
from typing import Union, Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from modules.auth.domain.auth import Auth
from modules.auth.dtos.request import LoginWithEmailPasswordCreds, CreateUserSchema, \
    SendPhoneOTPSchema, VerifyPhoneOTPSchema, SendEmailOTPSchema, \
    VerifyEmailOTPSchema, CheckAuthDetailsWithEmailId, CreateUserLeadWithEmailId
from modules.auth.use_cases.auth import login_with_email_password_use_case, \
    get_current_user_use_case, create_user_use_case, check_user_exists_with_email_id_use_case, \
    create_user_lead_with_email_id_use_case, send_email_otp_use_case, verify_email_otp_use_case
from schemas.exceptions import ApplicationException
from schemas.response import SuccessResponse, ErrorResponse, BaseResponse

router = APIRouter(prefix="/auth", tags=['Auth'])


@router.post('/check-user-exists-with-email-id',
             summary="Get Auth Details based on email id")
def check_user_exists_with_email_id(req_body: CheckAuthDetailsWithEmailId):
    """
    - fetch auth details with email_id and check if they are present
    - create auth record with email_id and profile_type

    - For campaign participants, record the email_id in campaign_participation db [It can be helpful,
    in case otp service is down]

    - If email_id is new then sendOTP for sign_up

    """

    try:
        resp = check_user_exists_with_email_id_use_case(req_body.email_id)
        return SuccessResponse(resp).json_response()
    except ApplicationException as ae:
        print("Exception ", ae)
        return ErrorResponse([
            ae.__str__()
        ], ae.status_code).json_response()


@router.post('/create-user-lead-with-email-id',
             summary="Create user lead against email id")
def create_user_lead_with_email_id(req_body: CreateUserLeadWithEmailId):
    """
        - create user lead for the email-id. This lead will be converted to auth_record once email has been verified via otp

    """

    try:
        resp = create_user_lead_with_email_id_use_case(req_body)
        return SuccessResponse(resp).json_response()
    except ApplicationException as ae:
        print("Exception ", ae)
        return ErrorResponse([
            ae.__str__()
        ], ae.status_code).json_response()


@router.post('/send-email-otp',
             summary="Send email OTP for different cases")
def send_email_otp(req_body: SendEmailOTPSchema):
    """
    - send Email OTP

    Use cases:
    sign_up: 'sign_up'

    login: 'login'

    change: 'change' # replace the email-id in both auth and lead table for the user. Moreover,
    in email_otp table, invalidate the entry for the old email-id record


    - record the send OTP request in the db

    # send response for
    - successful otp
    - failure otp
    - max_limit otp achieved

    """
    try:
        resp = send_email_otp_use_case(req_body)
        # resp = {
        #     "status": "Success",  # "Success" | "Failure"
        #     "failure_message": ""
        #     # "max_limit_reached": False # After 3 otp attempts in the last x mins
        # }
        return SuccessResponse(resp).json_response()
    except ApplicationException as ae:
        print("Exception ", ae)
        return ErrorResponse([
            ae.__str__()
        ], ae.status_code).json_response()


@router.post('/verify-email-otp',
             summary="verify email OTP for different cases")
def verify_email_otp(req_body: VerifyEmailOTPSchema):
    """
    - verify OTP


    Use cases:
        login: 'login'
            - get user profile details based on the profile_type and send it in the response

        signup: 'signup'
            - update auth record for email_id with is_email_id_verified
            - create profile record based on profile_type
            - send the profile_data it in the response

        change: 'change'
            - update auth record with new email_id with is_email_verified
            - send "email_id_updated" message in the response


    - record the verify OTP request in the db

    # send response for
    - successful otp verification along with
        - the above data based on the case
    - failure otp verification

    """
    try:
        result = verify_email_otp_use_case(req_body)
        return SuccessResponse(result).json_response()
    except ApplicationException as ae:
        print("Exception ", ae, ae.status_code, ae.error)
        return ErrorResponse([
            ae.__str__(),
            ae.error
        ], ae.status_code).json_response()


@router.post('/send-phone-otp',
             summary="Send Phone OTP for different cases")
def send_phone_otp(req_body: SendPhoneOTPSchema):
    """
    - send OTP

    Use cases:
    change: 'change'
        change: 'change' # replace the email-id in both auth and lead table for the user. Moreover,
    in email_otp table, invalidate the entry for the old email-id record

    redeem: 'redeem_credits'



    # send response for
    - successful otp
    - failure otp
    - max_limit otp achieved

    """
    try:
        resp = {
            "status": "Success",  # "Success" | "Failure"
            "failure_message": ""
            # "max_limit_reached": False  # After 3 otp attempts in the last x mins
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

        change: 'change'
            - update auth record with new phone with is_phone_verified
            - send "phone_updated" message in the response

        redeem: 'redeem_credits'
            - update campaign participation record with new phone


    # send response for
    - successful otp verification along with
        - the above data based on the case
    - failure otp verification

    """
    try:
        resp = {
            "status": "Success",  # "Success" | "Failure"
            "failure_message": ""
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
            "status": "Success",  # "Success" | "Failure"
            "failure_message": ""
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
            "status": "Success"  # "Success" | "Failure"
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
