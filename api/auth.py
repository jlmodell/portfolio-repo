from passlib.hash import pbkdf2_sha256
from datetime import timezone

import pytz
import jwt
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv
import os
import datetime

load_dotenv()

RSA_KEY = os.environ.get("RSA_KEY", None)
assert RSA_KEY is not None, "RSA_KEY is not set"

public_key = open("/Users/jmo/.ssh/id_rsa.pub", "r").read()
private_key = open("/Users/jmo/.ssh/id_rsa", "r").read()


def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pbkdf2_sha256.verify(password, hashed_password)


def generate_token(payload: dict) -> str:
    '''
    Generates a JWT token from the given payload
    '''
    payload["exp"] = datetime.datetime.now(
        timezone.utc) + datetime.timedelta(days=5)
    return jwt.encode(payload, "secret")


def generate_secure_token(payload: dict) -> str:
    '''
    generates a secure JWT token from the given payload
    '''
    payload["exp"] = datetime.datetime.now(
        timezone.utc) + datetime.timedelta(days=5)

    serialized_key = serialization.load_ssh_private_key(
        private_key.encode(), RSA_KEY.encode())

    return jwt.encode(payload=payload, key=serialized_key, algorithm="RS256")


def decode_secure_token(token: str) -> dict:
    '''
    decodes a secure JWT token
    '''
    serialized_key = serialization.load_ssh_public_key(
        public_key.encode(), RSA_KEY.encode())

    return jwt.decode(token, serialized_key, algorithms=["RS256"])


def verify_valid_token(token: str) -> bool:
    '''
    verifies that the token is valid
    '''
    try:
        utc = pytz.UTC
        token = decode_secure_token(token)

        return datetime.datetime.utcfromtimestamp(token["exp"]).replace(tzinfo=utc) > datetime.datetime.now(timezone.utc).replace(tzinfo=utc)
    except:
        return False


if __name__ == "__main__":
    payload = {
        "username": "modell.jeff@me.com",
        "active": True,
    }
    token = generate_secure_token(payload)
    print(token)
    decoded = decode_secure_token(token)
    print(decoded)

    print(verify_valid_token(token))
