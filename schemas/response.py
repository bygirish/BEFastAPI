import json
from _decimal import Decimal
from http import HTTPStatus

from pydantic import BaseModel
import typing as t

from fastapi.responses import JSONResponse


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: t.Any) -> t.Any:
        if isinstance(obj, Decimal):
            return int(obj)
        return json.JSONEncoder.default(self, obj)


class BaseResponse:
    status_code: HTTPStatus = None
    status: t.Union[str, None] = None

    def __init__(self, status_code, status):
        super().__init__()
        self.status_code = status_code
        self.status = status

    def json_response(self, response_data={}):
        print(f'response_data is {response_data}')

        content = {
            **response_data,
            "status": self.status
        }

        content_json = json.loads(json.dumps(content, cls=CustomJSONEncoder))

        return JSONResponse(
            content=content_json,
            status_code=self.status_code
        )


class SuccessResponse(BaseResponse):
    data: t.Union[any, None]

    def __init__(self,
                 data={}, status_code=HTTPStatus.OK):
        super().__init__(status_code, "SUCCESS")
        print(f'const success response_data is {data}')
        self.data = data

    def json_response(self):
        print(f'success response_data is {self.data}')
        return super().json_response({
            "data": self.data,
        })


class ErrorResponse(BaseResponse):
    errors: list[t.Union[str, None]]

    def __init__(self,
                 errors=["global-exception"], status_code=HTTPStatus.INTERNAL_SERVER_ERROR):
        super().__init__(status_code, "FAILURE")
        print(f'const error response_data is {errors}')
        self.errors = errors

    def json_response(self):
        print(f'error response_data is {self.errors}')
        return super().json_response({
            "errors": self.errors,
        })
