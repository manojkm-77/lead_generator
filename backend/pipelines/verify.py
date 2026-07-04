import re
import logging

logger = logging.getLogger(__name__)

WEBSITE_BLACKLIST = {
    "example.com", "test.com", "localhost", "facebook.com",
    "twitter.com", "instagram.com", "youtube.com",
}

WEBSITE_REGEX = re.compile(
    r"^https?://[a-zA-Z0-9][-a-zA-Z0-9]*(\.[a-zA-Z0-9][-a-zA-Z0-9]*)+\.[a-zA-Z]{2,}"
)


class VerificationPipeline:
    def verify(self, company_data: dict) -> dict:
        data = company_data.copy()
        issues = []

        if not data.get("company_name") or len(data["company_name"].strip()) < 2:
            issues.append("invalid_company_name")

        if data.get("website"):
            if not WEBSITE_REGEX.match(data["website"]):
                issues.append("invalid_website")
                data["website"] = None
            else:
                domain = data["website"].split("//")[-1].split("/")[0].lower()
                if any(b in domain for b in WEBSITE_BLACKLIST):
                    issues.append("blacklisted_website")
                    data["website"] = None

        if data.get("phone") and not re.match(r"^\+\d{10,15}$", data["phone"]):
            issues.append("invalid_phone_format")
            data["phone"] = None

        if data.get("email") and "@" not in data["email"]:
            issues.append("invalid_email")
            data["email"] = None

        data["_verification_issues"] = issues
        data["_verified"] = len(issues) == 0

        return data

    def verify_batch(self, companies: list[dict]) -> list[dict]:
        return [self.verify(c) for c in companies]
