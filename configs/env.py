# get env variables and pass them to dev and prod config files
from os import environ as e

__app_env = e.get("APP_ENV") if e.get("APP_ENV") and isinstance(e.get("APP_ENV"), str) else "local"
__aws_region = e.get("AWS_REGION") if e.get("AWS_REGION") and isinstance(e.get("AWS_REGION"),
                                                                         str) else "us-east-1"


def app_env():
    return __app_env


def app_region_env():
    return __aws_region



