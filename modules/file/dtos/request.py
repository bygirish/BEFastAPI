from typing import Optional, Union

from pydantic import BaseModel, Field


class UploadImageSchema(BaseModel):
    bucket_name: Union[str, None] = Field(default="profmatic-test-bucket") #"profmatic-test-bucket" # Have to make it required value
    folder_path_under_bucket: Union[str, None] = Field(default=None)#None #"profile3"

    # class Config:
    #     orm_mode = True


class DownloadImageSchema(BaseModel):
    bucket_name: str
    s3_image_path: str
    save_as_image_name: Union[str, None]

