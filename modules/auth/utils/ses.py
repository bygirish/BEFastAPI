import logging

import boto3
from botocore.exceptions import ClientError

from configs.env import app_region_env
from schemas.exceptions import ApplicationException

# Create a new SES resource and specify a region.
client = boto3.client('ses', region_name=app_region_env())
CHARSET = "UTF-8"


def send_email_ses(subject: str, body_html: str, recipient: str, sender: str = None,
                   config_set: any = {}, body_text: str = ""):
    # Try to send the email.
    try:
        # Provide the contents of the email.
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    recipient,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': body_html,
                    },
                    'Text': {
                        'Charset': CHARSET,
                        'Data': body_text,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': subject,
                },
            },
            Source=sender,
            # If you are not using a configuration set, comment or delete the
            # following line
            # ConfigurationSetName=CONFIGURATION_SET,
        )
    # Display an error if something goes wrong.
    except ClientError as e:
        logging.exception({
            "context": "ses_email_client",
            "status": "error",
            "error": e.response["Error"]["Code"],
            "exception": e
        })
        raise ApplicationException("Error in sending Email", 400, e)
    else:
        logging.info({
            "context": "ses_email_client",
            "status": "email sent",
            "message id": response['MessageId'],
        })
        # print("Email sent! Message ID:"),
        # print(response['MessageId'])
