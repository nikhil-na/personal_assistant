from fastmcp import FastMCP
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
import json
from typing import Optional

mcp = FastMCP("PersonalAssistant")

with open(os.path.join(os.path.dirname(__file__), "utils.json"), "r") as f:
    data = json.load(f)

MOCK_EMAILS = data["mock_emails"]
MOCK_GMAIL_CONTACTS = data["mock_gmail_contacts"]

load_dotenv()
ENV_EMAIL = os.getenv("EMAIL_ADDRESS")
ENV_PASS = os.getenv("EMAIL_PASSWORD")
ENV_SERVER = os.getenv("SMTP_SERVER")
ENV_PORT = os.getenv("SMTP_PORT")


@mcp.tool()
def fetch_emails(name: Optional[str], email: Optional[str]) -> dict:
    """Fetches unread emails when provided with a recipient's name or email address."""
    
    if not name and not email:
        return {"error": "Please provide either a name or an email address to search."}

    lookup_name = name.lower().strip() if name else None
    lookup_email = email.lower().strip() if email else None

    matched_emails = []
    for item in MOCK_EMAILS:
        item_name = item.get("name", "").lower()
        item_email = item.get("email", "").lower()

        name_match = lookup_name and lookup_name == item_name
        email_match = lookup_email and lookup_email == item_email

        if name_match or email_match:
            matched_emails.append(item)

    if not matched_emails:
        return {"error": f"No emails found matching Name: '{name}' or Email: '{email}'."}

    return {
        "emails": matched_emails
    }

@mcp.tool()
def search_gmail_contacts(name: str):
    """
    Searches for a contact in the user's Gmail contacts by name.
    Always use this tool when the user provides a name instead of providing an email address, or when they ask to find a contact.
    If the contact is not already known, request the email address and add it when provided.
    """

    look_up = name.lower().strip()
    for contact in MOCK_GMAIL_CONTACTS:
        if look_up in contact["name"].lower():
            return {"name": contact["name"], "email": contact["email"]}
    return {"error": "Contact not found. Please provide an email address to add this contact."}

@mcp.tool()
def add_email_database(name:str, email:str):
    new_contact = {"name": name.strip(), "email": email.strip()}
    MOCK_GMAIL_CONTACTS.append(new_contact)
    print(f"Added contact: {new_contact['name']} ({new_contact['email']})")
    # write back to json so it persists
    data["mock_gmail_contacts"] = MOCK_GMAIL_CONTACTS
    with open(os.path.join(os.path.dirname(__file__), "utils.json"), "w") as f:
        json.dump(data, f, indent=4)
    
    return {"success": f"Added {name} ({email}) to contacts."}

@mcp.tool()
def send_email(recipient: str, subject: str, body: str):
    """
    Sends an email to the specified recipient with the given subject and body.
    Use this tool immediately after creating a draft email if the user confirms they want to send it.
    """
    # Create the email
    message = MIMEText(body, "plain")
    message["Subject"] = subject
    message["From"] = ENV_EMAIL
    message["To"] = recipient

    # Send the email
    with smtplib.SMTP(ENV_SERVER, ENV_PORT) as server:
        server.starttls()  # Secure connection
        server.login(ENV_EMAIL, ENV_PASS)
        server.sendmail(ENV_EMAIL, recipient, message.as_string())

    return {"status": f"success to {recipient}"}

@mcp.tool()
def add(a: int, b: int):
    """A simple tool that adds two numbers."""
    return a + b

if __name__ == "__main__":
    mcp.run(transport="stdio")