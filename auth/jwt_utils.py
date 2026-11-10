import os
import jwt
import datetime
import uuid

from dotenv import load_dotenv

load_dotenv()

# Secret key -- in production this would be a long random secret from env
JWT_SECRET = os.environ.get("JWT_SECRET")

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")

if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters long.")

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 2
JWT_ISSUER = "secure-mcp-erp"
JWT_AUDIENCE = "secure-mcp-erp-client"

def issue_token(user: dict) -> str:
    """
    Create a signed JWT for the given user dict.

    Args:
        user: dict with keys: sub, role, student_id, name

    Returns:
        Signed JWT string
    """

    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
    "sub": str(user["sub"]),
    "role": user["role"],
    "student_id": user.get("student_id"),
    "faculty_id": user.get("faculty_id"),
    "name": user["name"],
    "iat": now,
    "exp": now + datetime.timedelta(hours=JWT_EXPIRY_HOURS),
    "iss": JWT_ISSUER,
    "aud": JWT_AUDIENCE,
    "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    return jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        options={
            "require": [
                "exp",
                "iat",
                "sub",
                "role",
                "iss",
                "aud",
                "jti",
            ]
        },
    )


def extract_token_from_header(auth_header: str | None) -> str | None:
    """
    Parse 'Bearer <token>' from an Authorization header value.

    Returns:
        Token string, or None if header is missing/malformed
    """
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None
