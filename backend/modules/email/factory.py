from modules.email.base import EmailProvider
from modules.auth.models import User


def get_email_provider(user: User, access_token: str, refresh_token: str = None) -> EmailProvider:
    if user.email_provider == "gmail":
        from modules.email.gmail import GmailProvider

        return GmailProvider(access_token=access_token, refresh_token=refresh_token or "")
    elif user.email_provider == "outlook":
        from modules.email.outlook import OutlookProvider

        return OutlookProvider(access_token=access_token)
    raise ValueError(f"Unsupported email provider: {user.email_provider}")
