import json
import logging
from fastapi.responses import JSONResponse

from schemas.response import ErrorResponse


def log_exception(exception_type, context, exception, details=None):
    if not details:
        details = {}
    logging.exception({
        "exception_type": exception_type,
        "context": context,
        "exception": exception,
        **details
    })


def log_custom_exception(context, exception, details=None):
    log_exception("custom-exception", context, exception, details)


def log_global_exception(context, exception, details=None):
    log_exception("global-exception", context, exception, details)
    return JSONResponse(
        content=json.dumps({"error": "Something went wrong", "description": exception}),
        status_code=500
    )


def log_application_exception(context, ae, details=None):
    log_exception("application-exception", context, ae, details)
    error_response = ErrorResponse(ae.error, "application-exception")
    return JSONResponse(
        content=error_response.__dict__,
        status_code=ae.status_code
    )


def log_bad_request_exception(context, bre, details=None):
    log_exception("bad-request-exception", context, bre, details)
    error_response = ErrorResponse(bre.error, "application-exception")
    return JSONResponse(
        content=error_response.__dict__,
        status_code=bre.status_code
    )


def log_global_info(context, details=None):
    if not details:
        details = {}
    logging.info({
        "log_type": "INFO Payments",
        "context": context,
        **details
    })


def log_custom_error(context, err_string, details=None):
    if not details:
        details = {}
    logging.error({
        "context": context,
        "error": err_string,
        **details
    })
