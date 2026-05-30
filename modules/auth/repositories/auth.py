import datetime
import logging
from typing import Tuple, Annotated, List

from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

from modules.auth.domain.auth import Auth
from modules.auth.domain.auth_otp import EmailOTP
from modules.auth.domain.lead import Lead
from modules.auth.utils.data_formatters import remove_empty_auth_gsi_key
from schemas.exceptions import DBException, ApplicationException
from utils.dynamodb import dynamo
from utils.time_utils import get_current_timestamp


def get_auth_user_repository(user_id: str = None, email_id: str = None):
    query_args = {
        "ScanIndexForward": False,
        "Limit": 1,
    }

    if user_id is not None:
        query_args.update({
            "KeyConditionExpression": Key("user_id").eq(user_id),
        })
    elif email_id is not None:
        query_args.update({
            "IndexName": "email_id_idx",
            "KeyConditionExpression": Key("email_id").eq(email_id),
        })


    records, st = dynamo.query(Auth.get_table_name(), **query_args)
    if st is True:
        n_records = len(records)
        if n_records == 0:
            return None
        else:
            # if n_records > 1:
            #     logging.exception({
            #
            #     })
            return records[0]
    else:
        raise ApplicationException("Failed in: check_user_exists_with_email_id_repository",
                                   400, records)


def get_user_lead_with_email_id_repository(email_id: str):
    query_args = {
        "IndexName": "email_id_idx",
        "KeyConditionExpression": Key("email_id").eq(email_id),
        "ScanIndexForward": False,
        "Limit": 1,
    }
    records, st = dynamo.query(Lead.get_table_name(), **query_args)
    if st is True:
        n_records = len(records)
        if n_records == 0:
            return None
        else:
            # if n_records > 1:
            #     logging.exception({
            #
            #     })
            return records[0]
    else:
        raise ApplicationException("Failed in: get_user_lead_with_email_id_repository",
                                   400, records)


def create_user_lead_with_email_id_repository(new_lead: Lead) -> Annotated[bool, "is_lead_created"]:
    lead_item_dict = new_lead.get_dict()
    lead_item_dict.update({
        "updated_at": get_current_timestamp()
    })
    lead_record = {
        "Item": lead_item_dict
    }
    resp, st = dynamo.put_item(Lead.get_table_name(), **lead_record)
    if resp is None:
        return st
    else:
        raise ApplicationException("Failed in: create_user_lead_with_email_id_repository",
                                   400, resp)


def update_user_lead_repository(new_lead: Lead) -> Annotated[bool, "is_lead_created"]:
    lead_item_dict = new_lead.get_dict()
    lead_item_dict.update({
        "updated_at": get_current_timestamp()
    })
    lead_record = {
        "Item": lead_item_dict
    }
    resp, st = dynamo.put_item(Lead.get_table_name(), **lead_record)
    if resp is None:
        return st
    else:
        raise ApplicationException("Failed in: update_user_lead_repository",
                                   400, resp)


def create_sent_email_otp_repository(email_otp: EmailOTP):
    email_otp_dict = email_otp.get_dict()
    email_otp_dict.update({
        "updated_at": get_current_timestamp()
    })
    email_otp_record = {
        "Item": email_otp_dict
    }
    resp, st = dynamo.put_item(EmailOTP.get_table_name(), **email_otp_record)
    if resp is None:
        return st
    else:
        raise ApplicationException("Failed in: send_email_otp_repository",
                                   400, resp)


def get_sent_email_otp_by_email_id_repository(email_id: str, past_time_limit: int):
    allowed_limit_timestamp = get_current_timestamp() - past_time_limit

    query_args = {
        "KeyConditionExpression": Key("email_id").eq(email_id) & (Key("updated_at").gte(
            allowed_limit_timestamp) if past_time_limit else True),
        "ScanIndexForward": False,
    }
    records, st = dynamo.query(EmailOTP.get_table_name(), **query_args)
    if st is True:
        n_records = len(records)
        if n_records == 0:
            return None
        else:
            return records
    else:
        raise ApplicationException("Failed in: get_sent_email_otp_by_email_id_repository",
                                   400, records)
    pass


def get_sent_email_otp_by_session_id_repository(session_id: str, email_id: str = None):
    query_args = {
        "IndexName": "session_id_idx",
        "KeyConditionExpression": Key("session_id").eq(session_id),
        "FilterExpression": Attr("email_id").eq(email_id),  # if email_id is not None else "",
        "ScanIndexForward": False,
        # "Limit": 1,
    }
    records, st = dynamo.query(EmailOTP.get_table_name(), **query_args)
    if st is True:
        n_records = len(records)
        if n_records == 0:
            return None
        else:
            return records
            # if n_records > 1:
            #     logging.exception({
            #
            #     })
            # return records[0]
    else:
        raise ApplicationException("Failed in: get_sent_email_otp_repository",
                                   400, records)
    pass


# def update_sent_email_otp_repository(update_sent_email_otp: EmailOTP):
#     email_otp_dict = update_sent_email_otp.get_dict()
#     email_otp_record = {
#         "Item": email_otp_dict
#     }
#     resp, st = dynamo.put_item(EmailOTP.get_table_name(), **email_otp_record)
#     if resp is None:
#         return st
#     else:
#         raise ApplicationException("Failed in: update_sent_email_otp_repository",
#                                    400, resp)


def create_auth_user_repository(auth_record: Auth, lead_record: Lead = None,
                                attach_transaction_items: List = []):
    transaction_items = attach_transaction_items

    if lead_record is not None:
        lead_record_dict = lead_record.get_dict()
        lead_record_dict.update({
            "updated_at": get_current_timestamp()
        })
        transaction_items.append({
            "action": "Put",
            "TableName": Lead.get_table_name(),
            "Item": lead_record_dict
        })

    auth_record_dict = auth_record.get_dict()
    remove_empty_auth_gsi_key(auth_record_dict)
    auth_record_dict.update({
        "updated_at": get_current_timestamp()
    })
    transaction_items.append({
        "action": "Put",
        "TableName": Auth.get_table_name(),
        "Item": auth_record_dict
    })
    # response, status = None, None
    response, status = dynamo.put_items_in_transaction(transaction_items)
    print("response, status", response, status)
    return response, status


def update_auth_user_repository(auth_record: Auth):
    # fake_users_db[new_user.email_id] = new_user
    print("new user", auth_record, auth_record.__dict__)
    auth_record_dict: dict = auth_record.__dict__
    remove_empty_auth_gsi_key(auth_record_dict)

    auth_record_dict.update({
        "updated_at": get_current_timestamp()
    })
    print("auth_record_dict", auth_record_dict)
    auth_record_data = {
        "Item": auth_record_dict
    }
    resp, st = dynamo.put_item(Auth.get_table_name(), **auth_record_data)
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

# def get_user_by_user_id_repository(user_id: str):
#     if user_id in fake_users_db:
#         user_dict = fake_users_db[user_id]
#         return user_dict
