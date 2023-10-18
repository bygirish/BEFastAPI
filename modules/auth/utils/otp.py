from math import floor
from random import random
from uuid import uuid4


def generate_otp(length=6):
    return floor(random()*pow(10, length))

def generate_session_id():
    return str(uuid4())
