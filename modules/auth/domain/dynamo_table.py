import boto3

from modules.auth.domain.auth import Auth
from modules.auth.domain.auth_otp import EmailOTP
from modules.auth.domain.lead import Lead
from utils.dynamodb import dynamo

dyn_resource = boto3.resource('dynamodb')


def create_auth_table():
    """
    Creates a DynamoDB table.

    :param dyn_resource: Either a Boto3 or DAX resource.
    :return: The newly created table.
    """

    table_name = dynamo.__get_env_table_name(Auth.get_table_name())
    params = {
        'TableName': table_name,
        'KeySchema': [
            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
            {'AttributeName': 'updated_at', 'KeyType': 'RANGE'}
        ],
        'AttributeDefinitions': [
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
            {'AttributeName': 'updated_at', 'AttributeType': 'N'},
            {'AttributeName': 'email_id', 'AttributeType': 'S'},
            {'AttributeName': 'phone_number', 'AttributeType': 'S'},
            # {'AttributeName': 'profile_id', 'AttributeType': 'S'},
        ],
        'ProvisionedThroughput': {
            'ReadCapacityUnits': 10,
            'WriteCapacityUnits': 10
        },
        'GlobalSecondaryIndexes': [
            {
                'IndexName': 'email_id_idx',
                'KeySchema': [
                    {
                        'AttributeName': 'email_id',
                        'KeyType': 'HASH'
                    },
                    {
                        'AttributeName': 'updated_at',
                        'KeyType': 'RANGE'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 1,
                    'WriteCapacityUnits': 1
                }
            },
            {
                'IndexName': 'phone_number_idx',
                'KeySchema': [
                    {
                        'AttributeName': 'phone_number',
                        'KeyType': 'HASH'
                    },
                    {
                        'AttributeName': 'updated_at',
                        'KeyType': 'RANGE'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 1,
                    'WriteCapacityUnits': 1
                }
            },
        ],
    }
    table = dyn_resource.create_table(**params)
    print(f"Creating {table_name}...")
    table.wait_until_exists()
    return table


def create_lead_table():
    """
    Creates a DynamoDB table.

    :param dyn_resource: Either a Boto3 or DAX resource.
    :return: The newly created table.
    """

    table_name = dynamo.__get_env_table_name(Lead.get_table_name())
    params = {
        'TableName': table_name,
        'KeySchema': [
            {'AttributeName': 'lead_id', 'KeyType': 'HASH'},
            # {'AttributeName': 'updated_at', 'KeyType': 'RANGE'}
        ],
        'AttributeDefinitions': [
            {'AttributeName': 'lead_id', 'AttributeType': 'S'},
            {'AttributeName': 'updated_at', 'AttributeType': 'N'},
            {'AttributeName': 'email_id', 'AttributeType': 'S'},
            # {'AttributeName': 'phone_number', 'AttributeType': 'S'},
        ],
        'ProvisionedThroughput': {
            'ReadCapacityUnits': 10,
            'WriteCapacityUnits': 10
        },
        'GlobalSecondaryIndexes': [
            {
                'IndexName': 'email_id_idx',
                'KeySchema': [
                    {
                        'AttributeName': 'email_id',
                        'KeyType': 'HASH'
                    },
                    {
                        'AttributeName': 'updated_at',
                        'KeyType': 'RANGE'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 1,
                    'WriteCapacityUnits': 1
                }
            },
            # {
            #     'IndexName': 'phone_number_idx',
            #     'KeySchema': [
            #         {
            #             'AttributeName': 'phone_number',
            #             'KeyType': 'HASH'
            #         },
            #         {
            #             'AttributeName': 'updated_at',
            #             'KeyType': 'RANGE'
            #         }
            #     ],
            #     'Projection': {
            #         'ProjectionType': 'ALL'
            #     },
            #     'ProvisionedThroughput': {
            #         'ReadCapacityUnits': 1,
            #         'WriteCapacityUnits': 1
            #     }
            # },
        ],
    }
    table = dyn_resource.create_table(**params)
    print(f"Creating {table_name}...")
    table.wait_until_exists()
    return table


def create_email_otp_table():
    """
    Creates a DynamoDB table.

    :param dyn_resource: Either a Boto3 or DAX resource.
    :return: The newly created table.
    """

    table_name = dynamo.__get_env_table_name(EmailOTP.get_table_name())
    params = {
        'TableName': table_name,
        'KeySchema': [
            {'AttributeName': 'email_id', 'KeyType': 'HASH'},
            {'AttributeName': 'updated_at', 'KeyType': 'RANGE'}
        ],
        'AttributeDefinitions': [
            {'AttributeName': 'email_id', 'AttributeType': 'S'},
            {'AttributeName': 'sent_at', 'AttributeType': 'N'},
            {'AttributeName': 'session_id', 'AttributeType': 'S'},
            {'AttributeName': 'updated_at', 'AttributeType': 'N'},
            # {'AttributeName': 'email_id', 'AttributeType': 'S'},
            # {'AttributeName': 'phone_number', 'AttributeType': 'S'},
        ],
        'ProvisionedThroughput': {
            'ReadCapacityUnits': 10,
            'WriteCapacityUnits': 10
        },
        'GlobalSecondaryIndexes': [
            {
                'IndexName': 'session_id_idx',
                'KeySchema': [
                    {
                        'AttributeName': 'session_id',
                        'KeyType': 'HASH'
                    },
                    {
                        'AttributeName': 'sent_at',
                        'KeyType': 'RANGE'
                    }
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                },
                'ProvisionedThroughput': {
                    'ReadCapacityUnits': 1,
                    'WriteCapacityUnits': 1
                }
            },
        ],
    }
    table = dyn_resource.create_table(**params)
    print(f"Creating {table_name}...")
    table.wait_until_exists()
    return table




if __name__ == '__main__':
    auth_table = create_auth_table()
    lead_table = create_lead_table()
    email_otp_table = create_email_otp_table()
    print(f"Created table.")
