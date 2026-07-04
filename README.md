# BuyerHunter AI

Edible Oil Buyer Intelligence Platform — discovers publicly available business information for companies likely to buy edible oils.

## Quick Start

```bash
# Clone and setup
cp .env.example .env
# Edit .env with your API keys

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Start backend
uvicorn backend.main:app --reload --port 8000

# Start frontend
cd frontend && npm install && npm run dev
```

## Docker

```bash
docker-compose up --build
```

## API Docs

Once running, visit `http://localhost:8000/docs` for Swagger UI.

## Project Structure

```
buyerhunter/
├── backend/
│   ├── api/          # FastAPI routes
│   ├── models/       # SQLAlchemy ORM models
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # Business logic
│   ├── spiders/      # Scrapy spiders
│   ├── pipelines/    # Data processing
│   ├── utils/        # Helpers
│   └── main.py       # App entry
├── frontend/
│   └── src/          # React + Tailwind
└── docs/
```

## Spiders

| Spider | Source | Status |
|--------|--------|--------|
| indiamart | IndiaMART | Stub |
| justdial | JustDial | Stub |
| tradeindia | TradeIndia | Stub |
| googlemaps | Google Maps | Stub |
| yellowpages | Yellow Pages | Stub |
| exportersindia | ExportersIndia | Stub |
| companywebsite | Generic websites | Stub |
| linkedin_company | LinkedIn | Stub |
| gst_directory | GST Directory | Stub |

## Environment Variables

See `.env.example` for all required configuration.
