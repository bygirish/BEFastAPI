from typing import Union
import uvicorn
from fastapi import FastAPI
import logging

from controllers.app import get_app_router

app = FastAPI()

app_router = get_app_router()

app.include_router(app_router)

if __name__ == "__main__":
    logging.info("Starting fast api app for BE Service")
    uvicorn.run(app="main:app", host="127.0.0.1", port=8080, reload=True)