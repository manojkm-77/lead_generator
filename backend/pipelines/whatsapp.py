import logging
import requests

from backend.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

API_URL = "https://graph.facebook.com/v18.0"


class WhatsAppPipeline:
    def __init__(self):
        self.token = settings.whatsapp_api_token
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def send_message(self, to_phone: str, template_name: str, language: str = "en") -> dict | None:
        if not self.token or not self.phone_number_id:
            logger.warning("WhatsApp API not configured")
            return None

        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
            },
        }

        try:
            resp = requests.post(
                f"{API_URL}/{self.phone_number_id}/messages",
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"WhatsApp send failed: {e}")
            return None

    def send_text(self, to_phone: str, message: str) -> dict | None:
        if not self.token or not self.phone_number_id:
            logger.warning("WhatsApp API not configured")
            return None

        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"body": message},
        }

        try:
            resp = requests.post(
                f"{API_URL}/{self.phone_number_id}/messages",
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"WhatsApp send failed: {e}")
            return None

    def generate_wa_link(self, phone: str, message: str = "") -> str:
        clean = phone.lstrip("+")
        base = f"https://wa.me/{clean}"
        if message:
            from urllib.parse import quote
            base += f"?text={quote(message)}"
        return base
