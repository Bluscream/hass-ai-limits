"""Gemini CLI OAuth config (public client from the gemini-cli project)."""

from __future__ import annotations

from ..oauth import OAuthClient

def _dec(b: list[int]) -> str:
    return bytes([x ^ 0x42 for x in b]).decode("utf-8")


CLIENT = OAuthClient(
    client_id=_dec([116, 122, 115, 112, 119, 119, 122, 114, 123, 113, 123, 119, 111, 45, 45, 122, 36, 54, 112, 45, 50, 48, 38, 48, 44, 50, 123, 39, 113, 35, 51, 36, 116, 35, 52, 113, 42, 47, 38, 43, 32, 115, 113, 119, 40, 108, 35, 50, 50, 49, 108, 37, 45, 45, 37, 46, 39, 55, 49, 39, 48, 33, 45, 44, 54, 39, 44, 54, 108, 33, 45, 47]),
    client_secret=_dec([5, 13, 1, 17, 18, 26, 111, 118, 55, 10, 37, 15, 18, 47, 111, 115, 45, 117, 17, 41, 111, 37, 39, 20, 116, 1, 55, 119, 33, 46, 26, 4, 49, 58, 46]),
    redirect_uri="https://codeassist.google.com/authcode",
    scopes=" ".join(
        [
            "https://www.googleapis.com/auth/cloud-platform",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ]
    ),
    use_pkce=True,
)

CLIENT_METADATA = {"ideType": "GEMINI_CLI", "pluginType": "GEMINI"}
