#!/usr/bin/env python3
"""
Generate valid Home Assistant auth files with working JWT token.

This creates:
1. A valid long-lived access token (JWT)
2. Matching .storage/auth file
3. Updated test_constants.py

Run: python tests/e2e/scripts/generate_auth.py
"""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
STORAGE_DIR = Path(__file__).parent.parent / "initial_test_state" / ".storage"
TEST_CONSTANTS_PATH = BASE_DIR / "tests" / "test_constants.py"


def base64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_jwt(payload: dict, secret: str) -> str:
    """Generate a JWT token."""
    header = {"alg": "HS256", "typ": "JWT"}

    header_b64 = base64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = base64url_encode(json.dumps(payload, separators=(",", ":")).encode())

    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    signature_b64 = base64url_encode(signature)

    return f"{message}.{signature_b64}"


def generate_token_hash(token: str) -> str:
    """Generate token hash as HA stores it."""
    return hashlib.sha512(token.encode()).hexdigest()


def main():
    # Generate random secrets
    user_id = secrets.token_hex(16)
    token_id = secrets.token_hex(16)
    credential_id = secrets.token_hex(16)
    jwt_key = secrets.token_hex(64)
    raw_token = secrets.token_hex(64)

    # Create JWT
    now = datetime.now(UTC)
    # Token expires in 2035 (10+ years)
    exp = int(datetime(2035, 1, 1, tzinfo=UTC).timestamp())
    iat = int(now.timestamp())

    jwt_payload = {"iss": token_id, "iat": iat, "exp": exp}

    access_token = generate_jwt(jwt_payload, jwt_key)
    token_hash = generate_token_hash(raw_token)

    # Create auth file
    auth_data = {
        "version": 1,
        "minor_version": 1,
        "key": "auth",
        "data": {
            "users": [
                {
                    "id": user_id,
                    "group_ids": ["system-admin"],
                    "is_owner": True,
                    "is_active": True,
                    "name": "test",
                    "system_generated": False,
                    "local_only": False,
                }
            ],
            "groups": [
                {"id": "system-admin", "name": "Administrators"},
                {"id": "system-users", "name": "Users"},
                {"id": "system-read-only", "name": "Read Only"},
            ],
            "credentials": [
                {
                    "id": credential_id,
                    "user_id": user_id,
                    "auth_provider_type": "homeassistant",
                    "auth_provider_id": None,
                    "data": {"username": "test"},
                }
            ],
            "refresh_tokens": [
                {
                    "id": token_id,
                    "user_id": user_id,
                    "client_id": None,
                    "client_name": "E2E Tests",
                    "client_icon": None,
                    "token_type": "long_lived_access_token",
                    "created_at": now.isoformat(),
                    "access_token_expiration": 315360000.0,
                    "token": token_hash,
                    "jwt_key": jwt_key,
                    "last_used_at": None,
                    "last_used_ip": None,
                    "expire_at": None,
                    "credential_id": None,
                    "version": "2024.1.0",
                }
            ],
        },
    }

    # Create auth_provider file
    # Password hash for "test" - using bcrypt format HA expects
    auth_provider_data = {
        "version": 1,
        "minor_version": 1,
        "key": "auth_provider.homeassistant",
        "data": {
            "users": [
                {
                    "username": "test",
                    "password": "$2b$12$LQv3c1yqBo9fkvVeHoVBu.NBY0pCc6bGm6Hk9ZLqWXCgE4FLUMYyK",
                }
            ]
        },
    }

    # Write auth files
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    with open(STORAGE_DIR / "auth", "w") as f:
        json.dump(auth_data, f, indent=2)

    with open(STORAGE_DIR / "auth_provider.homeassistant", "w") as f:
        json.dump(auth_provider_data, f, indent=2)

    # Write test_constants.py
    test_constants_content = f'''"""
Test constants shared across test modules.

This module centralizes test configuration values to ensure consistency
across all test environments.
"""

# Long-lived access token for test Home Assistant instance
# This token is embedded in tests/e2e/initial_test_state/.storage/auth
# Expires: 2035 (10+ years from token creation)
TEST_TOKEN = "{access_token}"

# Test user credentials (for UI access if needed)
TEST_USER = "test"
TEST_PASSWORD = "test"
'''

    with open(TEST_CONSTANTS_PATH, "w") as f:
        f.write(test_constants_content)

    print("Generated auth files:")
    print(f"  {STORAGE_DIR / 'auth'}")
    print(f"  {STORAGE_DIR / 'auth_provider.homeassistant'}")
    print(f"  {TEST_CONSTANTS_PATH}")
    print()
    print(f"Token ID: {token_id}")
    print(f"User ID: {user_id}")
    print(f"Access Token (first 50 chars): {access_token[:50]}...")
    print()
    print("Token expires: 2035-01-01")


if __name__ == "__main__":
    main()
