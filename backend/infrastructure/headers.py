"""
Dynamic Browser Header Anti-Fingerprinting.

Generates realistic, randomized browser headers on every call to
bypass standard directory anti-scraping firewalls.
"""

import logging
import random

logger = logging.getLogger(__name__)

_UA_FALLBACKS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S24) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; OnePlus 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
]

_CHROME_VERSIONS = ["125.0.0.0", "124.0.0.0", "126.0.0.0", "127.0.0.0", "128.0.0.0"]
_EDGE_VERSIONS = ["125.0.0.0", "124.0.0.0"]
_FIREFOX_VERSIONS = ["127.0", "126.0", "128.0", "129.0"]
_OS_CPUS = ["Windows NT 10.0; Win64; x64", "Macintosh; Intel Mac OS X 14_5", "Macintosh; Intel Mac OS X 14_4", "X11; Linux x86_64"]
_ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-US,en;q=0.9,hi;q=0.8",
    "en-IN,en;q=0.9,hi;q=0.8",
    "en-US,en;q=0.9,es;q=0.8",
    "en-CA,en;q=0.9,fr;q=0.8",
    "en-AU,en;q=0.9",
    "en-US,en;q=0.9,ar;q=0.8",
    "en-US,en;q=0.9,fr;q=0.8,de;q=0.7",
    "en-US,en;q=0.8",
]
_ACCEPT_ENCODINGS = ["gzip, deflate, br", "gzip, deflate", "gzip, deflate, br, zstd"]
_ACCEPT_TYPES = [
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
]
_SEC_CH_UA_PLATFORMS = ["Windows", "macOS", "Linux", "Android", "iOS"]
_BITS = ["64", "32"]
_MOBILE_VALUES = ["?0", "?1"]
_ARCHS = ["x86", "x64", "arm"]


class HeaderGenerator:
    def __init__(self):
        self._use_fake_ua = False
        self._fake_ua = None
        try:
            from fake_useragent import UserAgent
            self._fake_ua = UserAgent(browsers=["chrome", "firefox", "edge", "safari"])
            self._use_fake_ua = True
        except Exception:
            pass

    def _random_ua(self) -> str:
        if self._use_fake_ua and self._fake_ua:
            try:
                return self._fake_ua.random
            except Exception:
                pass
        return random.choice(_UA_FALLBACKS)

    def generate(self, ua_override: str = "", platform_override: str = "",
                 mobile_override: bool = False) -> dict:
        ua = ua_override or self._random_ua()
        ua_lower = ua.lower()

        is_chrome = "chrome" in ua_lower and "edg" not in ua_lower
        is_firefox = "firefox" in ua_lower
        is_edge = "edg" in ua_lower and "chrome" in ua_lower
        is_safari = "safari" in ua_lower and "chrome" not in ua_lower
        is_mobile = mobile_override or "mobile" in ua_lower

        platform = platform_override
        if not platform:
            if "windows" in ua_lower:
                platform = "Windows"
            elif "mac os" in ua_lower or "macintosh" in ua_lower:
                platform = "macOS"
            elif "linux" in ua_lower and "android" not in ua_lower:
                platform = "Linux"
            elif "android" in ua_lower:
                platform = "Android"
            elif "iphone" in ua_lower or "ipad" in ua_lower:
                platform = "iOS"
            else:
                platform = random.choice(_SEC_CH_UA_PLATFORMS)

        headers = {
            "User-Agent": ua,
            "Accept": random.choice(_ACCEPT_TYPES),
            "Accept-Language": random.choice(_ACCEPT_LANGUAGES),
            "Accept-Encoding": random.choice(_ACCEPT_ENCODINGS),
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "DNT": "1",
            "Connection": "keep-alive",
        }

        if is_chrome or is_edge:
            chrome_version = random.choice(_CHROME_VERSIONS)
            major = chrome_version.split(".")[0]

            headers["Sec-Ch-Ua"] = (
                f'"Chromium";v="{major}", "Google Chrome";v="{major}"'
                if is_chrome
                else f'"Chromium";v="{major}", "Microsoft Edge";v="{random.choice(_EDGE_VERSIONS).split(".")[0]}"'
            )
            headers["Sec-Ch-Ua-Mobile"] = random.choice(_MOBILE_VALUES)
            headers["Sec-Ch-Ua-Platform"] = f'"{platform}"'
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Site"] = random.choice(["none", "same-origin", "cross-site"])
            headers["Sec-Fetch-User"] = "?1"
            headers["Upgrade-Insecure-Requests"] = "1"

        if is_firefox:
            headers["TE"] = "trailers"

        return headers

    def generate_mobile(self) -> dict:
        ua = random.choice([u for u in _UA_FALLBACKS if "mobile" in u.lower() or "android" in u.lower() or "iphone" in u.lower()])
        return self.generate(ua_override=ua, mobile_override=True)

    def generate_desktop(self) -> dict:
        ua = random.choice([u for u in _UA_FALLBACKS if "mobile" not in u.lower() and "android" not in u.lower() and "iphone" not in u.lower()])
        return self.generate(ua_override=ua)

    def randomize(self) -> dict:
        return self.generate()
