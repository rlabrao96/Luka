"""Typed errors for household / invite flows so the frontend can branch on
stable codes instead of matching localized message substrings."""


class InviteError(Exception):
    """Raised when an invite cannot be accepted.

    `code` is a stable identifier that the frontend uses to pick its UI branch.
    `message` is a Spanish-localized string shown directly to the user.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# Known error codes — keep in sync with the frontend invite page.
INVITE_NOT_FOUND = "invite_not_found"
INVITE_EXPIRED = "invite_expired"
INVITE_ALREADY_USED = "invite_already_used"
INVITE_SELF = "invite_self"
INVITE_ALREADY_MEMBER = "invite_already_member"
INVITE_EMAIL_MISMATCH = "invite_email_mismatch"
INVITE_IN_OTHER_GROUP = "invite_in_other_group"
INVITE_HOUSEHOLD_FULL = "invite_household_full"
