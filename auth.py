import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]


def get_credentials() -> Credentials:
    """
    Load Google OAuth2 credentials.
    On Render: reads from GOOGLE_TOKEN_JSON and GOOGLE_CREDENTIALS_JSON env vars.
    Locally: reads from token.json and credentials.json files.
    """
    creds = None

    # Try loading token from environment variable (Render deployment)
    token_json_str = os.getenv("GOOGLE_TOKEN_JSON")
    if token_json_str:
        token_data = json.loads(token_json_str)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    # Fall back to local token.json file
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    # If still no valid creds, run local OAuth flow (only works locally)
    if not creds or not creds.valid:
        credentials_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if credentials_json_str:
            credentials_data = json.loads(credentials_json_str)
            flow = InstalledAppFlow.from_client_config(credentials_data, SCOPES)
        elif os.path.exists("credentials.json"):
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        else:
            raise RuntimeError(
                "No Google credentials found. Set GOOGLE_CREDENTIALS_JSON env var "
                "or place credentials.json in the project root."
            )
        creds = flow.run_local_server(port=0)

    return creds
