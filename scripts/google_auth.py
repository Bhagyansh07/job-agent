"""Google OAuth (Gmail read-only + Sheets). Run once:  python scripts/google_auth.py
interactive=False never opens a browser - it raises if no valid cached token exists (for unattended sync)."""
from common import ROOT

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/spreadsheets"]
# Cold email uses its own token file so the existing read-only grant keeps working.
SEND_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_SEND = ROOT / "secrets" / "token_send.json"


def creds(interactive=True):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    tok = ROOT / "secrets" / "token.json"
    cred = ROOT / "secrets" / "credentials.json"
    c = None
    if tok.exists():
        c = Credentials.from_authorized_user_file(str(tok), SCOPES)
    if not c or not c.valid:
        if c and c.expired and c.refresh_token:
            c.refresh(Request())
        elif interactive:
            flow = InstalledAppFlow.from_client_secrets_file(str(cred), SCOPES)
            c = flow.run_local_server(port=0)
        else:
            raise RuntimeError("Google token missing/expired - run: python scripts/google_auth.py")
        tok.parent.mkdir(exist_ok=True)
        tok.write_text(c.to_json())
    return c


def creds_send(interactive=True):
    """Gmail send-only credentials. First run needs an interactive browser grant:
    python scripts/google_auth.py --send"""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    cred = ROOT / "secrets" / "credentials.json"
    c = None
    if TOKEN_SEND.exists():
        c = Credentials.from_authorized_user_file(str(TOKEN_SEND), SEND_SCOPES)
    if not c or not c.valid:
        if c and c.expired and c.refresh_token:
            c = Credentials.from_authorized_user_file(str(TOKEN_SEND), SEND_SCOPES)
            c.refresh(Request())
        elif interactive:
            if not cred.exists():
                raise RuntimeError("REAUTH_NEEDED: secrets/credentials.json missing - create a "
                                   "Google Cloud OAuth desktop client first")
            flow = InstalledAppFlow.from_client_secrets_file(str(cred), SEND_SCOPES)
            c = flow.run_local_server(port=0)
        else:
            raise RuntimeError("REAUTH_NEEDED: run python scripts/google_auth.py --send once")
        TOKEN_SEND.parent.mkdir(exist_ok=True)
        TOKEN_SEND.write_text(c.to_json())
    return c


def service(name, version, interactive=True):
    from googleapiclient.discovery import build
    return build(name, version, credentials=creds(interactive=interactive), cache_discovery=False)


if __name__ == "__main__":
    import sys
    if "--send" in sys.argv:
        creds_send(interactive=True)
        print("Gmail send auth OK")
    else:
        creds(interactive=True)
        print("Google auth OK")
