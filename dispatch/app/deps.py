import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from . import config

security = HTTPBasic()


def require_auth(creds: HTTPBasicCredentials = Depends(security)) -> str:
    user_ok = secrets.compare_digest(creds.username.encode(), config.DISPATCH_USER.encode())
    pass_ok = secrets.compare_digest(creds.password.encode(), config.DISPATCH_PASS.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return creds.username
