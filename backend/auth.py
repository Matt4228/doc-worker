import os
import secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# auto_error=False so a missing header reaches require_demo_password and gets
# the same 401 as a wrong password, instead of FastAPI's default 403.
_bearer = HTTPBearer(auto_error=False)


def require_demo_password(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Reject requests that don't carry `Authorization: Bearer <DEMO_PASSWORD>`.

    Fails closed: if DEMO_PASSWORD isn't set, every request is refused, so a
    deploy that forgets the variable breaks loudly instead of serving the
    API (and spending Anthropic credits) for anyone who finds the URL.
    """
    expected = os.environ.get("DEMO_PASSWORD")
    if not expected:
        raise HTTPException(status_code=503, detail="DEMO_PASSWORD is not configured on the server.")

    # compare_digest takes the same time whether the first character or the
    # last one is wrong, so response timing can't be used to guess the
    # password one character at a time. Encoded to bytes because it raises
    # TypeError on non-ASCII str input.
    supplied = credentials.credentials if credentials else ""
    if not secrets.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(
            status_code=401,
            detail="Missing or incorrect demo password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
