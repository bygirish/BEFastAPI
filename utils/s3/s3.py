import logging

import boto3
from botocore.exceptions import ClientError
from starlette import status

from configs.env import app_region_env
from schemas.exceptions import CustomHTTPException

# from bhanzu_commons.util import env

logger = logging.getLogger(__name__)

credentials = boto3.Session().get_credentials()

aws_region = app_region_env()

_s3_resource = boto3.resource('s3', region_name=aws_region)

_s3_client = boto3.client('s3')

# https://binaryguy.tech/aws/s3/grant-public-read-access-to-s3-objects/
def s3_upload_file_object(s3_bucket, file_path, file_obj, is_public=True):
    try:
        if is_public:
            _s3_client.upload_fileobj(file_obj, s3_bucket, file_path, ExtraArgs={"ACL": "public-read"})
        else:
            _s3_client.upload_fileobj(file_obj, s3_bucket, file_path)
        file_obj_url = f"https://{s3_bucket}.s3.us-east-1.amazonaws.com/{file_path}"
        return file_obj_url
    except Exception as e:
        logging.exception({
            "context": "s3_upload_file_object",
            "status": "error",
            "error": e
        })
        raise CustomHTTPException("Error in uploading file", status.HTTP_500_INTERNAL_SERVER_ERROR, e.__str__())


def s3_upload(s3_bucket, file_path, file_name):
    try:
        s3_object = _s3_resource.Object(
            bucket_name=s3_bucket, key=file_path)

        s3_object.upload_file(file_name)
    except ClientError as e:
        logging.exception({
            "context": "s3-upload",
            "status": "error",
            "error": e
        })



def s3_download(s3_bucket, file_path, file_name):
    try:
        s3_object = _s3_resource.Object(
            bucket_name=s3_bucket, key=file_path)

        res = s3_object.download_file(file_name)

    except ClientError as e:
        logging.exception({
            "context": "s3-download",
            "status": "error",
            "error": e
        })
        return e
    return res


def s3_delete(s3_bucket, file_path):
    try:
        response = _s3_client.delete_object(
            Bucket=s3_bucket, Key=file_path)
        return response
    except ClientError as e:
        logging.exception({
            "context": "s3-delete",
            "status": "error",
            "error": e
        })
        return e


def s3_file_read(s3_bucket, file_path, attachment=False):
    try:
        fileobj = _s3_resource.Object(bucket_name=s3_bucket, key=file_path)
        filedata = fileobj.get()['Body'].read()
        if not attachment:
            filedata = filedata.decode('utf-8')
        return filedata

    except ClientError as e:
        logging.exception({
            "context": "s3_file_read",
            "status": "error",
            "error": e
        })
        return e


def s3_get_files_in_folder(s3_bucket, folder_path):
    """"
    This function returns the list of files in a folder in s3 bucket
    :param s3_bucket: s3 bucket name
    :param folder_path: folder path in s3 bucket
    """
    try:
        bucket = _s3_resource.Bucket(s3_bucket)
        file_names = []
        for bucket_object in bucket.objects.filter(Prefix=folder_path):
            file_names.append(bucket_object.key)
        return True, file_names
    except ClientError as error:
        logging.exception({
            "context": "s3_get_files_in_folder",
            "status": "error",
            "error": error
        })
        return False, error
