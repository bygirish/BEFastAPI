import http
from typing import Union, Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from modules.auth.domain.auth import Auth
from modules.auth.schemas.request import LoginWithEmailPasswordCreds, CreateUserSchema
from modules.auth.use_cases.auth import login_with_email_password_use_case, \
    get_current_user_use_case, create_user_use_case
from schemas.exceptions import ApplicationException
from schemas.response import SuccessResponse, ErrorResponse, BaseResponse

router = APIRouter(prefix="/auth", tags=[])


@router.post('/signup', summary="Create new user")
async def create_user(data: CreateUserSchema):
    # querying database to check if user already exist
    try:
        resp = create_user_use_case(data)
        return SuccessResponse(resp).json_response()
    except ApplicationException as ae:
        print("Exception ", ae)
        return ErrorResponse([
            ae.__str__()
        ], ae.status_code).json_response()

@router.post("/v1/login/email-password")
def loginWithEmailPassword(creds: LoginWithEmailPasswordCreds):
    """"""
    try:
        email, password = creds.dict().values()
        print("email, password", email, password)
        resp = login_with_email_password_use_case(email, password)

        return SuccessResponse(resp).json_response()
    except ApplicationException as ae:
        return ErrorResponse([
            ae.__str__()
        ], ae.status_code).json_response()


@router.get("/v1/user/me")
async def get_current_user(
        current_user: str = Depends(get_current_user_use_case)
):
    print("current_user", current_user)
    print("current_user dict", current_user.__dict__)
    # return current_user
    try:
        return SuccessResponse({
        "user_data": current_user.__dict__
        }).json_response()
    except ApplicationException as ae:
        return ErrorResponse([
            ae.__str__()
        ], http.HTTPStatus.ALREADY_REPORTED).json_response()
