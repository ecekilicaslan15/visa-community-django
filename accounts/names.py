"""How a member is shown on cards, in the nav, and in welcome messages."""

AVATAR_CLASSES = ("", "a2", "a3", "a4")


def display_name(user):
    """First name plus last initial ("Ayşe K."), or the username when either is missing."""
    if not getattr(user, "is_authenticated", False):
        return ""
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    if first and last:
        return f"{first} {last[0].upper()}."
    return user.get_username()


def initials(user):
    """One or two letters taken from the display name, for the avatar circle."""
    parts = []
    for raw in display_name(user).split():
        cleaned = "".join(ch for ch in raw if ch.isalnum())
        if cleaned:
            parts.append(cleaned)
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    if parts:
        return parts[0][:2].upper()
    return "?"


def avatar_class(user):
    """Stable colour class from the user id: default, a2, a3, or a4."""
    user_id = getattr(user, "pk", None)
    if not user_id:
        return ""
    return AVATAR_CLASSES[user_id % 4]
