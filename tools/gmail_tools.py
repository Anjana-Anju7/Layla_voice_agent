import base64
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest
from auth import get_credentials
import memory


def _service():
    return build("gmail", "v1", credentials=get_credentials())


def read_emails(max_results: int = 5) -> str:
    """
    Read the latest emails from the Primary inbox.
    Returns sender, subject, snippet, and message ID for each.
    """
    svc = _service()
    result = svc.users().messages().list(
        userId="me",
        maxResults=max_results,
        labelIds=["INBOX"],
        q="category:primary",
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        return "No emails found."

    # Batch fetch all messages in parallel
    email_data = {}

    def handle_response(request_id, response, exception):
        if exception:
            email_data[request_id] = {"error": str(exception)}
        else:
            email_data[request_id] = response

    batch = svc.new_batch_http_request(callback=handle_response)
    for msg in messages:
        batch.add(
            svc.users().messages().get(userId="me", id=msg["id"], format="metadata",
                                       metadataHeaders=["From", "Subject", "Date"]),
            request_id=msg["id"],
        )
    batch.execute()

    lines = []
    for i, msg in enumerate(messages, 1):
        data = email_data.get(msg["id"], {})
        headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
        sender = headers.get("From", "Unknown")
        subject = headers.get("Subject", "(no subject)")
        snippet = data.get("snippet", "")
        email_id = msg["id"]

        # Auto-learn contact
        if "<" in sender and ">" in sender:
            name = sender.split("<")[0].strip().strip('"')
            email_addr = sender.split("<")[1].rstrip(">")
            memory.learn_contact(email_addr, name)

        lines.append(f"{i}. ID:{email_id} | From: {sender} | Subject: {subject}\n   {snippet[:100]}")

    return "\n\n".join(lines)


def search_emails(query: str, max_results: int = 5) -> str:
    """
    Search emails using Gmail search syntax.
    Examples: 'from:sarah contract', 'subject:invoice', 'is:unread'
    """
    svc = _service()
    result = svc.users().messages().list(
        userId="me", maxResults=max_results, q=query
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        return f"No emails found matching: {query}"

    email_data = {}

    def handle(request_id, response, exception):
        email_data[request_id] = response if not exception else {"error": str(exception)}

    batch = svc.new_batch_http_request(callback=handle)
    for msg in messages:
        batch.add(
            svc.users().messages().get(userId="me", id=msg["id"], format="metadata",
                                       metadataHeaders=["From", "Subject", "Date"]),
            request_id=msg["id"],
        )
    batch.execute()

    lines = []
    for i, msg in enumerate(messages, 1):
        data = email_data.get(msg["id"], {})
        headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
        sender = headers.get("From", "Unknown")
        subject = headers.get("Subject", "(no subject)")
        snippet = data.get("snippet", "")
        lines.append(f"{i}. ID:{msg['id']} | From: {sender} | Subject: {subject}\n   {snippet[:100]}")

    return "\n\n".join(lines)


def get_full_email(email_id: str) -> str:
    """
    Retrieve the full body text of a specific email by its ID.
    Use when the user asks to read the full content of an email.
    """
    svc = _service()
    msg = svc.users().messages().get(userId="me", id=email_id, format="full").execute()

    def extract_body(payload):
        if payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        for part in payload.get("parts", []):
            result = extract_body(part)
            if result:
                return result
        return "(No readable body found)"

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = extract_body(msg.get("payload", {}))
    return (
        f"From: {headers.get('From', 'Unknown')}\n"
        f"Subject: {headers.get('Subject', '(no subject)')}\n"
        f"Date: {headers.get('Date', '')}\n\n"
        f"{body[:3000]}"
    )


def send_email(to: str, subject: str, body: str) -> str:
    """
    Send a new email.
    to: recipient email address
    subject: email subject line
    body: plain text email body
    """
    svc = _service()
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"Email sent to {to} with subject '{subject}'."


def reply_email(email_id: str, body: str) -> str:
    """
    Reply to an existing email thread by email ID.
    email_id: the ID of the email to reply to
    body: the reply text
    """
    svc = _service()
    original = svc.users().messages().get(userId="me", id=email_id, format="metadata",
                                          metadataHeaders=["From", "Subject", "Message-ID", "References"]).execute()

    headers = {h["name"]: h["value"] for h in original.get("payload", {}).get("headers", [])}
    thread_id = original.get("threadId")
    to = headers.get("From", "")
    subject = headers.get("Subject", "")
    if not subject.lower().startswith("re:"):
        subject = "Re: " + subject

    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    if headers.get("Message-ID"):
        msg["In-Reply-To"] = headers["Message-ID"]
        msg["References"] = headers.get("References", "") + " " + headers["Message-ID"]

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    svc.users().messages().send(
        userId="me", body={"raw": raw, "threadId": thread_id}
    ).execute()
    return f"Reply sent to {to}."


def archive_email(email_id: str) -> str:
    """
    Archive an email by removing it from the inbox (removes INBOX label).
    email_id: the ID of the email to archive
    """
    svc = _service()
    svc.users().messages().modify(
        userId="me", id=email_id, body={"removeLabelIds": ["INBOX"]}
    ).execute()
    return f"Email {email_id} archived."
