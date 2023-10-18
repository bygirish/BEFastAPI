from fastapi import HTTPException, status


class ApplicationException(Exception):
    """Still an exception raised when uncommon things happen"""

    def __init__(self, message, status_code, error=None):
        self.message = message
        self.status_code = status_code
        self.error = error

    def __str__(self):
        return f"Application Error with status code '{self.status_code}' and message '{self.message}'. Error is '{str(self.error)}'"


class CustomHTTPException(Exception):
    def __init__(self, message="Http Exception", status_code=status.HTTP_401_UNAUTHORIZED,
                 error=None):
        self.message = message
        self.status_code = status_code
        self.error = error

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": message,
                "error": error
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


class DBException(Exception):
    """raised when db operations fail"""

    def __init__(self, message, status_code):
        self.message = message
        self.status_code = status_code

    def __str__(self):
        return f"DB operation failed with message `{self.message}`, error occurred with status code: {self.status_code}"
