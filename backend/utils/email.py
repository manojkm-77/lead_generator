import re

DISPOSABLE_DOMAINS = {
    "tempmail.com", "throwaway.email", "guerrillamail.com",
    "mailinator.com", "yopmail.com", "trashmail.com",
}

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def validate_email(email: str | None) -> str | None:
    if not email:
        return None
    email = email.strip().lower()
    if not EMAIL_REGEX.match(email):
        return None
    domain = email.split("@")[-1]
    if domain in DISPOSABLE_DOMAINS:
        return None
    return email


def extract_emails(text: str) -> list[str]:
    found = EMAIL_REGEX.findall(text)
    return [validate_email(e) for e in found if validate_email(e)]
