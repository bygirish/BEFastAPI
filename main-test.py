from modules.auth.domain.auth import Auth
from modules.auth.domain.dynamo_table import create_table
from modules.auth.repositories.auth import create_user_repository, get_user_by_email_id_repository
from modules.auth.schemas.request import CreateUserSchema
from modules.auth.use_cases.auth import create_user_use_case
from modules.auth.utils.utils import get_password_hash
from utils.data_generators import generate_unique_id_for_db
import random
from math import floor

if __name__ == "__main__":
    # print(int(datetime.datetime.now().timestamp()))
    # auth_user = Auth(**{
    #     "user_id": generate_unique_id_for_db(),
    #     "email_id": "girish.test"+str(floor(random.random()*1000))+"gmail.com",
    #     "hashed_password": get_password_hash("123456"),
    # })
    #
    # print("auth_user", auth_user.__dict__)
    # create_user_repository(auth_user)

    res = get_user_by_email_id_repository("girish.test543gmail.com")
    print("==============")
    print(res)