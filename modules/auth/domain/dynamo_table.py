import boto3

from modules.auth.domain.auth import Auth
from utils.dynamodb import dynamo


def create_table(dyn_resource=None):
    """
    Creates a DynamoDB table.

    :param dyn_resource: Either a Boto3 or DAX resource.
    :return: The newly created table.
    """
    if dyn_resource is None:
        dyn_resource = boto3.resource('dynamodb')

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


if __name__ == '__main__':
    dax_table = create_table()
    print(f"Created table.")
