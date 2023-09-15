import copy
import decimal
import json
from base64 import b64decode, b64encode

from boto3.dynamodb.types import TypeSerializer, TypeDeserializer
from botocore.exceptions import ClientError
import boto3
# from bhanzu_commons.util import env
import typing as t
import logging
import concurrent.futures
import itertools

from configs.app_Config import dynamodb_table_prefix_config
from configs.env import app_region_env

serializer = TypeSerializer()

__dynamo_table_prefix = dynamodb_table_prefix_config()


def __get_table(table_name: str):
    env_table_name = __dynamo_table_prefix + "-" + table_name
    db_connection = boto3.resource("dynamodb")
    table = db_connection.Table(env_table_name)
    return table


def __get_env_table_name(table_name: str):
    return __dynamo_table_prefix + "-" + table_name


def __get_table_base_name(table_name: str):
    full_prefix = __dynamo_table_prefix + "-"
    return table_name.split(full_prefix)[-1]


def batch_writer(table_name: str):
    table = __get_table(table_name)
    return table.batch_writer()


def delete_item(table_name: str, **kwargs: t.Any):
    try:
        table = __get_table(table_name)
        response = table.delete_item(**kwargs)
        return response.get("Attributes", None), True
    except ClientError as e:
        logging.exception({
            "context": "dynamo-delete",
            "status": "error",
            "error": e.response["Error"]["Code"],
            "table_name": table_name,
            "exception": e
        })
        return e, False
    except Exception as e:
        logging.exception({
            "context": "dynamo-delete",
            "status": "error",
            "table_name": table_name,
            "error": e
        })
        return e, False


def get_item(table_name: str, **kwargs: t.Any):
    try:
        table = __get_table(table_name)
        response = table.get_item(**kwargs)
        return response.get("Item", None), True
    except KeyError as e:
        logging.exception({
            "context": "dynamo-get",
            "status": "error",
            "table_name": table_name,
            "error": e
        })
        return None, False
    except ClientError as e:
        logging.exception({
            "context": "dynamo-put",
            "status": "error",
            "table_name": table_name,
            "error": e.response["Error"]["Code"]
        })
        return None, False


def put_item(table_name: str, **kwargs: t.Any):
    try:
        print(f"table name pre {table_name}")
        table = __get_table(table_name)
        print(f"table name {table}")
        response = table.put_item(**kwargs)
        return response.get("Attributes", None), True
    except ClientError as e:
        logging.exception({
            "context": "dynamo-put",
            "status": "error",
            "table_name": table_name,
            "error": e.response["Error"]["Code"],
            "exception": e
        })
        return e, False
    except Exception as e:
        logging.exception({
            "context": "dynamo-put",
            "status": "error",
            "table_name": table_name,
            "error": e
        })
        return e, False


def query(table_name: str, **kwargs: t.Any):
    try:
        table = __get_table(table_name)
        query_kwargs = copy.deepcopy(kwargs)
        done = False
        start_key = None
        data = []
        while not done:
            if start_key:
                query_kwargs["ExclusiveStartKey"] = start_key
            response = table.query(**query_kwargs)
            data.extend(response.get("Items"))
            start_key = response.get("LastEvaluatedKey", None)
            done = start_key is None
        return data, True

    except ClientError as e:
        logging.exception({
            "context": "dynamo-query",
            "status": "error",
            "table_name": table_name,
            "error": e.response["Error"]["Code"],
            "exception": e
        })
        return e, False
    except Exception as e:
        logging.exception({
            "context": "dynamo-query",
            "status": "error",
            "table_name": table_name,
            "error": e
        })
        return e, False


def parallel_scan_table(db_client, *, table_name: str, **kwargs):
    total_segments = 25
    max_scans_in_parallel = 5

    tasks_to_do = [
        {
            **kwargs,
            "TableName": table_name,
            "Segment": segment,
            "TotalSegments": total_segments,
        }
        for segment in range(total_segments)
    ]

    scans_to_run = iter(tasks_to_do)

    with concurrent.futures.ThreadPoolExecutor() as executor:

        futures = {
            executor.submit(db_client.scan, **scan_params): scan_params
            for scan_params in itertools.islice(scans_to_run, max_scans_in_parallel)
        }

        while futures:
            done, _ = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED
            )

            for fut in done:
                yield from fut.result()["Items"]

                scan_params = futures.pop(fut)

                try:
                    scan_params["ExclusiveStartKey"] = fut.result()["LastEvaluatedKey"]
                    futures[executor.submit(db_client.scan, **scan_params)] = scan_params
                except KeyError:
                    break

            for scan_params in itertools.islice(scans_to_run, len(done)):
                futures[executor.submit(db_client.scan, **scan_params)] = scan_params


def scan(table_name: str, **kwargs: t.Any):
    try:
        env_table_name = __dynamo_table_prefix + "-" + table_name
        db_client = boto3.resource("dynamodb").meta.client

        data = []
        for item in parallel_scan_table(db_client, table_name=env_table_name, **kwargs):
            data.append(item)
        return data, True
    except ClientError as e:
        logging.exception({
            "context": "dynamo-scan",
            "status": "error",
            "table_name": table_name,
            "error": e.response["Error"]["Code"],
            "exception": e
        })
        return e, False
    except Exception as e:
        logging.exception({
            "context": "dynamo-scan",
            "status": "error",
            "table_name": table_name,
            "error": e
        })
        return e, False


def old_scan(table_name: str, **kwargs: t.Any):
    try:
        table = __get_table(table_name)
        scan_kwargs = copy.deepcopy(kwargs)
        done = False
        start_key = None
        data = []
        while not done:
            if start_key:
                scan_kwargs["ExclusiveStartKey"] = start_key
            response = table.scan(**scan_kwargs)
            data.extend(response.get("Items"))
            start_key = response.get("LastEvaluatedKey", None)
            done = start_key is None
        return data, True

    except ClientError as e:
        logging.exception({
            "context": "dynamo-scan",
            "status": "error",
            "table_name": table_name,
            "error": e.response["Error"]["Code"],
            "exception": e
        })
        return e, False
    except Exception as e:
        logging.exception({
            "context": "dynamo-scan",
            "status": "error",
            "table_name": table_name,
            "error": e
        })
        return e, False


def update_item(table_name, **kwargs):
    try:
        table = __get_table(table_name)
        response = table.update_item(**kwargs)
        return response.get("Attributes", None), True
    except ClientError as e:
        logging.exception({
            "context": "dynamo-update",
            "status": "error",
            "error": e.response["Error"]["Code"],
            "table_name": table_name,
            "exception": e
        })
        return e, False
    except Exception as e:
        logging.exception({
            "context": "dynamo-update",
            "status": "error",
            "table_name": table_name,
            "error": e
        })
        return e, False


def update_item_dict(table_name: str, key: dict, update_dict: dict, **kwargs):
    update_expression_names = {}
    update_expression_values = {}
    update_expression_array = []

    for key, value in update_dict.items():
        update_expression_names["#" + key] = key
        update_expression_values[":" + key] = value
        update_expression_array.append(f"#{key}  = :{key}")

    update_expression = "SET " + ", ".join(update_expression_array)
    update_args = {
        "Key": key,
        "UpdateExpression": update_expression,
        "ExpressionAttributeNames": update_expression_names,
        "ExpressionAttributeValues": update_expression_values
    }
    update_args.update(kwargs)
    return update_item(table_name, **update_args)


def get_all_item(table_name: str):
    try:
        table = __get_table(table_name)
        response = table.scan()
        return response.get("Items", None), True
    except KeyError as e:
        logging.exception({
            "context": "dynamo-get",
            "status": "error",
            "table_name": table_name,
            "error": e
        })
        return None, False
    except ClientError as e:
        logging.exception({
            "context": "dynamo-put",
            "status": "error",
            "table_name": table_name,
            "error": e.response["Error"]["Code"]
        })
        return None, False


def put_items_in_transaction(item_list):
    try:
        dynamodb_client = boto3.client("dynamodb")
        transaction_items = []
        for each in item_list:
            if each["action"] == "ConditionCheck":
                transaction_items.append({
                    "ConditionCheck": {
                        "TableName": __get_env_table_name(each["TableName"]),
                        "Key": __convert_to_transaction_dict(each["Key"]),
                        "ConditionExpression": each["ConditionExpression"],
                        "ExpressionAttributeValues": __convert_to_transaction_dict(
                            each["ExpressionAttributeValues"])
                    }
                })
            if each["action"] == "Put":
                transaction_items.append({
                    "Put": {
                        "TableName": __get_env_table_name(each["TableName"]),
                        "Item": __convert_to_transaction_dict(each["Item"])
                    }
                })
            if each["action"] == "Update":
                action_config = {
                    "Update": {
                        "TableName": __get_env_table_name(each["TableName"]),
                        "ExpressionAttributeValues": __convert_to_transaction_dict(
                            each["ExpressionAttributeValues"]),
                        "Key": __convert_to_transaction_dict(each["Key"]),
                        "UpdateExpression": each["UpdateExpression"]
                    }
                }
                if "ConditionExpression" in each:
                    action_config["Update"]["ConditionExpression"] = each["ConditionExpression"]
                transaction_items.append(action_config)
        response = dynamodb_client.transact_write_items(
            TransactItems=transaction_items
        )
        return response, True
    except Exception as e:
        logging.exception({
            "context": "put_items_in_transaction",
            "status": "error",
            "error": e
        })
        return e, False


def __convert_to_transaction_dict(db_dict):
    transaction_dict = {}
    for key, val in db_dict.items():
        transaction_dict[key] = serializer.serialize(val)
    return transaction_dict


def get_paginated_data(table_name, offset, limit):
    table = __get_table(table_name)
    queryCount = 1
    response = table.scan(Limit=limit)
    data = response['Items']
    if (offset == 1):
        return data
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'], Limit=limit)
        data = response['Items']
        queryCount += 1
        if (queryCount == offset):
            return data
    return data


def batch_get_item(**kwargs):
    try:
        batch_get_item_kwargs = copy.deepcopy(kwargs)
        request_items = batch_get_item_kwargs.pop("RequestItems")
        actual_request_items = {}
        for table_name in request_items:
            actual_table_name = __get_env_table_name(table_name)
            actual_request_items[actual_table_name] = request_items[table_name]
        client = boto3.client('dynamodb')

        result = client.batch_get_item(
            RequestItems=actual_request_items, **batch_get_item_kwargs
        )

        parsed_response = {}

        for table_name in result["Responses"]:
            parsed_response[__get_table_base_name(table_name)] = result["Responses"][table_name]

        return parsed_response, True
    except ClientError as e:
        logging.exception({
            "context": "dynamo-batch-get-item",
            "status": "error",
            "error": e.response["Error"]["Code"],
            "exception": e
        })
        return e, False
    except Exception as e:
        logging.exception({
            "context": "dynamo-batch-get-item",
            "status": "error",
            "error": e
        })
        return e, False


def default_type_error_handler(obj):
    if isinstance(obj, decimal.Decimal):
        res = decimal.Decimal(obj).as_integer_ratio()
        if res and res[1] != 1:
            return float(obj)
        else:
            return int(obj)
    else:
        return obj


def paginated_query(
        table_name: str,
        **kwargs: t.Any
):
    try:
        table = __get_table(table_name)
        query_kwargs = copy.deepcopy(kwargs)
        page_size = query_kwargs.pop('page_size', 50)
        last_evaluated_key = query_kwargs.pop('last_evaluated_key', None)
        if last_evaluated_key:
            last_evaluated_key_bytes = bytes(last_evaluated_key, encoding="utf-8")
            last_evaluated_key = b64decode(last_evaluated_key_bytes).decode("utf-8")
            last_evaluated_key = json.loads(last_evaluated_key, parse_int=decimal.Decimal,
                                            parse_float=decimal.Decimal)
        data = []
        limit = int(page_size)
        start_key = last_evaluated_key
        data_remaining = True
        while limit and data_remaining:
            query_kwargs["Limit"] = limit
            if start_key:
                query_kwargs["ExclusiveStartKey"] = start_key
            response = table.query(**query_kwargs)
            data.extend(response.get("Items"))
            start_key = response.get("LastEvaluatedKey", None)
            if not start_key:
                data_remaining = False
            limit = int(page_size) - len(data)
        if start_key:
            json_bytes = bytes(json.dumps(start_key, default=default_type_error_handler),
                               encoding="utf-8")
            start_key = b64encode(json_bytes).decode("utf-8")
        resp = {
            "items": data,
            "last_evaluated_key": start_key
        }
        return resp, True

    except ClientError as e:
        logging.exception({
            "context": "dynamo-query",
            "status": "error",
            "table_name": table_name,
            "error": e.response["Error"]["Code"],
            "exception": e
        })
        return e, False
    except Exception as e:
        logging.exception({
            "context": "dynamo-query",
            "status": "error",
            "table_name": table_name,
            "error": e
        })
        return e, False


def paginated_scan(
        table_name: str,
        **kwargs: t.Any
):
    try:
        table = __get_table(table_name)
        query_kwargs = copy.deepcopy(kwargs)
        page_size = query_kwargs.pop('page_size', 50)
        last_evaluated_key = query_kwargs.pop('last_evaluated_key', None)
        if last_evaluated_key:
            last_evaluated_key_bytes = bytes(last_evaluated_key, encoding="utf-8")
            last_evaluated_key = b64decode(last_evaluated_key_bytes).decode("utf-8")
            last_evaluated_key = json.loads(last_evaluated_key, parse_int=decimal.Decimal,
                                            parse_float=decimal.Decimal)
        data = []
        limit = int(page_size)
        start_key = last_evaluated_key
        data_remaining = True
        while limit and data_remaining:
            query_kwargs["Limit"] = limit
            if start_key:
                query_kwargs["ExclusiveStartKey"] = start_key
            response = table.scan(**query_kwargs)
            data.extend(response.get("Items"))
            start_key = response.get("LastEvaluatedKey", None)
            if not start_key:
                data_remaining = False
            limit = int(page_size) - len(data)
        if start_key:
            json_bytes = bytes(json.dumps(start_key, default=default_type_error_handler),
                               encoding="utf-8")
            start_key = b64encode(json_bytes).decode("utf-8")
        resp = {
            "items": data,
            "last_evaluated_key": start_key
        }
        return resp, True

    except ClientError as e:
        logging.exception({
            "context": "dynamo-paginated-scan",
            "status": "error",
            "table_name": table_name,
            "error": e.response["Error"]["Code"],
            "exception": e
        })
        return e, False
    except Exception as e:
        logging.exception({
            "context": "dynamo-paginated-scan",
            "status": "error",
            "table_name": table_name,
            "error": e
        })
        return e, False


def from_dynamodb_to_json(item):
    d = TypeDeserializer()
    return {k: d.deserialize(value=v) for k, v in item.items()}
