from pydantic import BaseModel


class LoginWithEmailPasswordCreds(BaseModel):
    email: str
    password: str

class CreateUserSchema(BaseModel):
    email_id: str
    password: str



