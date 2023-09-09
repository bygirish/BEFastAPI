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


def login_with_email_password_use_case(email: str, password: str):
    print("In login_with_email_password_use_case")
    # check if user exists for email
    # if exists then match the hashed password
    # If matched then create token & store it in db
    # If user doesn't exist then create one in the db and return response accordingly with user_id


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


def get_user_profile_use_case(email: str = None, phone: str = None, user_id: str = None):
    print("In get_user_profile_use_case")
    # get the user profile based on whatever arg is present


def create_auth_token(profile_data: any):
    print("In create_auth_token")
    # create auth token and save it in the db


def logout_user_use_case(user_id: str):
    print("In logout_user_use_case")
    # put the jwt token in the blacklist token db


def authenticate_authorize_user_use_case(auth_token: str, allowed_user_roles: list[str] = [], allowed_user_types: list[str] = []):
    print("In authenticate_user_use_case")
    # validate the jwt token based on expiry time
    # if valid then extract the user_id, user_type and user_role
    # validate the user_type & user_role with allowed_user_types & allowed_user_roles