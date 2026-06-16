# VBB-SmartDelay

Real-time delay prediction for five central-Berlin transit lines (U2, M10, S5, S7, Bus 22), with a sustainable bike-sharing fallback when waiting no longer makes sense.

University project for the Web Services course (Eunice University) by **Muhammad Waseem** and **Zahid Shah**.

## What it does

The system ingests live data from three public APIs, stores it in a PostgreSQL + PostGIS database, and combines the streams to produce a delay estimate that accounts for weather. When a predicted delay is large enough that walking to a nearby Nextbike would actually be faster than waiting, it suggests the bike.

| Source | Data | Format |
|---|---|---|
| VBB REST API (`v6.vbb.transport.rest`) | live departures, delays, vehicle GPS | JSON |
| OpenWeatherMap | rain, wind, temperature | JSON |
| GBFS (Nextbike Berlin) | available bikes and their locations | JSON |

## Project layout

```
vbb-smartdelay/
├── docker-compose.yml      # optional local PostgreSQL + PostGIS
├── init-db.sql             # database schema (tables + spatial indexes)
├── setup_database.py       # one-time: create the schema
├── requirements.txt
├── .env.example            # template for your secrets (copy to .env)
└── apis/
    ├── test_*.py           # quick API connectivity checks
    ├── ingest_weather.py   # fetch + store weather
    ├── ingest_vbb.py       # fetch + store vehicle positions / delays
    ├── ingest_bikes.py     # fetch + store bikes (spatial match to stops)
    ├── predict_delays.py   # core engine: weather modifier + bike policy
    ├── api_output.py       # formatted summary of predictions
    └── run_all.py          # run the whole pipeline in order
```

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure secrets.** Copy `.env.example` to `.env` and fill in your own values:
   ```bash
   cp .env.example .env
   ```
   The `.env` file holds your database connection string and API key. It is git-ignored and is never uploaded.

3. **Create the database schema** (uses a free Neon PostgreSQL instance, or your own):
   ```bash
   python setup_database.py
   ```

4. **Run the pipeline**
   ```bash
   cd apis
   python run_all.py
   ```

## How the prediction works

A lightweight, transparent rule-based model:

```
predicted_delay = raw_VBB_delay × (1 + weather_modifier)
```

The weather modifier is a small stepped penalty (heavier rain and strong wind add more). The bike fallback is **not** a fixed threshold: a bike is only suggested when the predicted extra wait is longer than the time it would take to walk to the nearest available bike and unlock it — so the app never tells you to bike when waiting is actually faster.

See the project report for the full data-flow discussion, design trade-offs, and the database-technology justification.

> Note: this is a coursework prototype, not a production service.
