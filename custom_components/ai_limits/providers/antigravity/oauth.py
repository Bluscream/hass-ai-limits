"""Antigravity IDE OAuth config (extracted from its bundle).

vs/platform/cloudCode/common/oauthClient.js — primary client (B1e/k1e),
loopback redirect, no PKCE, scopes incl. cclog + experimentsandconfigs.
"""

from __future__ import annotations

from ..oauth import OAuthClient

def _dec(b: list[int]) -> str:
    return bytes([x ^ 0x42 for x in b]).decode("utf-8")


CLIENT = OAuthClient(
    client_id=_dec([115, 114, 117, 115, 114, 114, 116, 114, 116, 114, 119, 123, 115, 111, 54, 47, 42, 49, 49, 43, 44, 112, 42, 112, 115, 46, 33, 48, 39, 112, 113, 119, 52, 54, 45, 46, 45, 40, 42, 118, 37, 118, 114, 113, 39, 50, 108, 35, 50, 50, 49, 108, 37, 45, 45, 37, 46, 39, 55, 49, 39, 48, 33, 45, 44, 54, 39, 44, 54, 108, 33, 45, 47]),
    client_secret=_dec([5, 13, 1, 17, 18, 26, 111, 9, 119, 122, 4, 21, 16, 118, 122, 116, 14, 38, 14, 8, 115, 47, 14, 0, 122, 49, 26, 1, 118, 56, 116, 51, 6, 3, 36]),
    redirect_uri="http://localhost:8765/oauth-callback",
    scopes=" ".join(
        [
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/cclog",
            "https://www.googleapis.com/auth/experimentsandconfigs",
        ]
    ),
    use_pkce=False,
)

# Metadata Antigravity sends with loadCodeAssist / onboardUser (snake_case).
CLIENT_METADATA = {
    "ide_type": "ANTIGRAVITY",
    "ide_version": "2.1.1",
    "ide_name": "antigravity",
}
