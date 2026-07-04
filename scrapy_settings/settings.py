BOT_NAME = "buyerhunter"

SPIDER_MODULES = ["backend.spiders"]
NEWSPIDER_MODULE = "backend.spiders"

ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 16
DOWNLOAD_DELAY = 2
CONCURRENT_REQUESTS_PER_DOMAIN = 8

DOWNLOAD_TIMEOUT = 30
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
}

FEED_EXPORT_ENCODING = "utf-8"
LOG_LEVEL = "INFO"

# Playwright
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": ["--no-sandbox", "--disable-dev-shm-usage"],
}

ITEM_PIPELINES = {
    "backend.spiders.pipelines.ValidationPipeline": 100,
    "backend.spiders.pipelines.CleanupPipeline": 200,
    "backend.spiders.db_pipelines.SQLitePipeline": 300,
    "backend.spiders.db_pipelines.CSVExportPipeline": 400,
}

SQLITE_DB_PATH = "buyerhunter.db"
CSV_OUTPUT_PATH = "exports/crawl_output.csv"

HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 3600
HTTPCACHE_DIR = ".httpcache"
RANDOMIZE_DOWNLOAD_DELAY = True

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
