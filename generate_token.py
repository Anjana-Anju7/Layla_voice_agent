"""
Run this script ONCE locally to generate token.json.
Then copy the contents of token.json into the GOOGLE_TOKEN_JSON env var on Render.

Usage:
    python generate_token.py
"""
import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]


def main():
    if not os.path.exists("credentials.json"):
        print("ERROR: credentials.json not found.")
        print("Download it from Google Cloud Console > APIs & Services > Credentials.")
        print("Choose 'Desktop app' type when creating OAuth credentials.")
        return

    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)

    with open("token.json", "w") as f:
        f.write(creds.to_json())

    print("\ntoken.json created successfully!")
    print("\nNext step for Render deployment:")
    print("Copy the contents below and paste as GOOGLE_TOKEN_JSON env var in Render:\n")
    with open("token.json") as f:
        print(f.read())


if __name__ == "__main__":
    main()
