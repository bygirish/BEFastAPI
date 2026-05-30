import http
import os
from typing import Annotated

from fastapi import APIRouter, UploadFile, File, Form, Depends

from modules.file.dtos.request import UploadImageSchema, DownloadImageSchema
from schemas.exceptions import ApplicationException
from schemas.response import SuccessResponse, ErrorResponse
from utils.s3.s3 import s3_upload_file_object, s3_download
from utils.time_utils import get_current_timestamp

router = APIRouter(prefix="/file", tags=['file'])

# Reference
# https://stackoverflow.com/questions/65504438/how-to-add-both-file-and-json-body-in-a-fastapi-post-request
@router.post("/v1/upload/image", summary="upload image")
def upload_image_file(
        image_file: Annotated[
            UploadFile, File(description="A file read as UploadFile")],
        image_data: UploadImageSchema = Depends()):
    """
        - update image file to s3 bucket

    """
    try:
        print("image_data", image_data)
        bucket_name = image_data.bucket_name
        folder_path_under_bucket = image_data.folder_path_under_bucket
        # profile_data = req_body.profile_data
        # print("image_file", bucket_name, folder_path_under_bucket, image_file)
        print("image_file", image_file.filename, image_file.headers, image_file.file)
        print("image_file", image_file.headers.get("content-type"))

        image_name = "-".join(image_file.filename.split())
        unique_image_name = f"{str(get_current_timestamp())}-{image_name}"

        folder_path = f"{folder_path_under_bucket}/" if folder_path_under_bucket else ""
        file_path = f"{folder_path}{unique_image_name}"  # profile_id/image_name

        result = s3_upload_file_object(s3_bucket=bucket_name, file_path=file_path,
                                       file_obj=image_file.file)
        print("result", result)

        return SuccessResponse({
            "message": "successful upload",
            "s3_file_url": result
        }).json_response()
    except ApplicationException as ae:
        print("Exception ", ae, ae.status_code, ae.error)
        return ErrorResponse([
            ae.__str__(),
            ae.error
        ], ae.status_code).json_response()


@router.get("/v1/download/image", summary="download image")
def download_image_file(image_data: DownloadImageSchema):
    """
        - Download private image file from s3 bucket

    """
    try:

        print(image_data)
        result = s3_download(image_data.bucket_name, image_data.s3_image_path,
                             image_data.save_as_image_name if image_data.save_as_image_name is not None else image_data.s3_image_path)
        print("result", result)

        return SuccessResponse({
            "message": "successful download",
            "image_path": result
        }).json_response()
    except ApplicationException as ae:
        print("Exception ", ae, ae.status_code, ae.error)
        return ErrorResponse([
            ae.__str__(),
            ae.error
        ], ae.status_code).json_response()
