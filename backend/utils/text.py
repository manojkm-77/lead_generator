import re
from bs4 import BeautifulSoup


def clean_html(html: str | None) -> str | None:
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text(separator=" ", strip=True)


def normalize_whitespace(text: str | None) -> str | None:
    if not text:
        return None
    return re.sub(r"\s+", " ", text.strip())


def normalize_text(text: str | None) -> str | None:
    if not text:
        return None
    text = clean_html(text)
    return normalize_whitespace(text)


def title_case(text: str | None) -> str | None:
    if not text:
        return None
    return text.strip().title()
