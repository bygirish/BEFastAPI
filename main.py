from typing import Union
import uvicorn
from fastapi import FastAPI
import logging

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}

logger = logging.getLogger("gunicorn.error")
@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}


if __name__ == "__main__":
    logger.info("Starting fast api app for BE Service")
    uvicorn.run(app="main:app", host="127.0.0.1", port=8080, reload=True)