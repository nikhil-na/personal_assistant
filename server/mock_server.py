from fastmcp import FastMCP

mcp = FastMCP("PersonalAssistant")

# Mock data for Gmail contacts
MOCK_GMAIL_CONTACTS = [
    {"name": "Alice Johnson", "email": "alice.johnson@example.com"},
    {"name": "Bob Smith", "email": "bob.smith@example.com"},
]

@mcp.tool()
def fetch_emails(name: str, email: str):
    """Fetches all the unread email when provided with recipient's name or email address."""
    return {"name": "bob smith", "email":"this is the sample email"}

@mcp.tool()
def search_gmail_contacts(name: str):
    """
    Searches for a contact in the user's Gmail contacts by name.
    Always use this tool when the user provides a name instead of providing an email address, or when they ask to find a contact.
    """

    look_up = name.lower().strip()
    for contact in MOCK_GMAIL_CONTACTS:
        if look_up in contact["name"].lower():
            return f"Found contact: {contact['name']} ({contact['email']})"
    return f"No contact found for '{name}'."

@mcp.tool()
def create_draft_email(recipient: str, subject: str, body: str):
    """
    Creates a draft email in the user's Gmail account.
    Use this tool immediately once you have a verified email address, a clear subject, and body content.
    """
    return f"[Success]: Draft successfully created for {recipient} with subject '{subject}'."

@mcp.tool()
def send_email(recipient: str, subject: str, body: str):
    """
    Sends an email to the specified recipient with the given subject and body.
    Use this tool immediately after creating a draft email if the user confirms they want to send it.
    """
    return f"[Success]: Email sent to {recipient} with subject '{subject}'."

@mcp.tool()
def add(a: int, b: int):
    """A simple tool that adds two numbers."""
    return a + b

if __name__ == "__main__":
    mcp.run(transport="stdio")