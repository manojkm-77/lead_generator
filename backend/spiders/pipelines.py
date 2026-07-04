import re
from scrapy.exceptions import DropItem


class ValidationPipeline:
    def process_item(self, item, spider):
        name = item.get("company_name", "").strip()
        if not name or len(name) < 2:
            raise DropItem(f"Missing company name: {item}")

        item["company_name"] = name
        return item


class CleanupPipeline:
    def process_item(self, item, spider):
        fields = getattr(item, "fields", None) or list(item.keys()) if isinstance(item, dict) else []
        for field in fields:
            if field in item and isinstance(item[field], str):
                item[field] = re.sub(r"\s+", " ", item[field].strip())

        if item.get("website"):
            url = item["website"].strip()
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            item["website"] = url

        if item.get("phone"):
            digits = re.sub(r"[^\d+]", "", item["phone"])
            item["phone"] = digits

        return item
