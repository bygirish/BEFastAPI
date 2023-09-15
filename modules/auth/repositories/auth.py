import datetime

from boto3.dynamodb.conditions import Key

from modules.auth.domain.auth import Auth
from modules.auth.utils.data_formatters import remove_empty_auth_gsi_key
from utils.dynamodb import dynamo
from utils.time_utils import get_current_timestamp

fake_users_db = {
    "johndoe1": {
        "user_id": "johndoe1",
        "email_id": "u1@gmail.com",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
    },
    "johndoe1": {
        "user_id": "johndoe2",
        "email_id": "u2@gmail.com",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZsdfsfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
    },
    'girish@gmail.com': {'user_id': 'd79dd36b-6ead-4f1d-b977-1c6a9d0cee79', 'email_id': 'girish@gmail.com', 'hashed_password': '$2b$12$OGH9xtnTqB2VqffNyYKLa.rD4RN/TT1fhkDZ5dSN6diQHPTgHgrxu'}
}


def create_user_repository(new_user: Auth):
    # fake_users_db[new_user.email_id] = new_user
    print("new user", new_user, new_user.__dict__)
    user_item_dict: dict = new_user.__dict__
    remove_empty_auth_gsi_key(user_item_dict)

    user_item_dict.update({
        "updated_at": get_current_timestamp()
    })
    print("user_item_dict", user_item_dict)
    user_record = {
        "Item": user_item_dict
    }
    resp, st = dynamo.put_item(Auth.get_table_name(), **user_record)
    print("resp, st", resp, st)

def update_user_repository(new_user: Auth):
    # fake_users_db[new_user.email_id] = new_user
    print("new user", new_user, new_user.__dict__)
    user_item_dict: dict = new_user.__dict__
    remove_empty_auth_gsi_key(user_item_dict)

    user_item_dict.update({
        "updated_at": get_current_timestamp()
    })
    print("user_item_dict", user_item_dict)
    user_record = {
        "Item": user_item_dict
    }
    resp, st = dynamo.put_item(Auth.get_table_name(), **user_record)
    print("resp, st", resp, st)



def update_user_repository(new_user: Auth):
    # fake_users_db[new_user.email_id] = new_user
    print("new user", new_user, new_user.__dict__)
    user_record = {
        "Item": new_user.__dict__
    }
    resp, st = dynamo.put_item(Auth.get_table_name(), **user_record)
    print("resp, st", resp, st)



def get_user_by_email_id_repository(email_id: str):
    query_args = {
        "IndexName": "email_id_idx",
        "KeyConditionExpression": Key("email_id").eq(email_id),
        "ScanIndexForward": False,
        "Limit": 1,
        # "Select": 'COUNT',
        # "ExpressionAttributeNames": {
        #     '#aid': 'account_id'
        # },
        # "ExpressionAttributeValues": {
        #     ':aid': {
        #         'N': "aid"
        # }
        # "FilterExpression": "profile_type = :profile_type",
        # "ExpressionAttributeValues": {":profile_type": "PARENT"},
    }

    resp, st = dynamo.query(Auth.get_table_name(), **query_args)
    print("resp, st", st, resp)
    if st is True:
        return resp[0] if len(resp) > 0 else None


def get_user_by_phone_number_repository(phone_number: str):
    query_args = {
        "IndexName": "phone_number_idx",
        "KeyConditionExpression": Key("phone_number").eq(phone_number),
        "ScanIndexForward": False,
        "Limit": 1,
        # "Select": 'COUNT',
        # "ExpressionAttributeNames": {
        #     '#aid': 'account_id'
        # },
        # "ExpressionAttributeValues": {
        #     ':aid': {
        #         'N': "aid"
        # }
        # "FilterExpression": "profile_type = :profile_type",
        # "ExpressionAttributeValues": {":profile_type": "PARENT"},
    }

    resp, st = dynamo.query(Auth.get_table_name(), **query_args)

    # resp, st = dynamo.get_item(Auth.get_table_name(), Key=key, IndexName='email_id_idx')
    print("resp, st", st, resp)
    if st is True:
        return resp[0] if len(resp) > 0 else None



def get_user_by_user_id_repository(user_id: str):
    if user_id in fake_users_db:
        user_dict = fake_users_db[user_id]
        return user_dict


