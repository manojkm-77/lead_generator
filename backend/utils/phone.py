import phonenumbers
from phonenumbers import NumberParseException


def normalize_phone(raw: str | None, default_country: str = "IN") -> str | None:
    if not raw:
        return None
    cleaned = raw.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    try:
        parsed = phonenumbers.parse(cleaned, default_country)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except NumberParseException:
        pass
    digits = "".join(c for c in cleaned if c.isdigit())
    if len(digits) == 10:
        return f"+91{digits}"
    if len(digits) > 10:
        return f"+{digits}"
    return None


def format_phone_display(e164: str | None) -> str | None:
    if not e164:
        return None
    try:
        parsed = phonenumbers.parse(e164, "IN")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except NumberParseException:
        return e164
