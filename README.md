# Fuel-route assessment — Django prototype

Overview

This repository contains a concise Django prototype that imports fuel station data, geocodes stations, and exposes a single API endpoint to compute a driving route and recommend economical fuel stops along that route.

Prerequisites

- Python 3.10+ (venv recommended)
- An OpenRouteService API key for routing (set as `ORS_API_KEY`)

Environment setup (.env)

1. Copy the example file and set your key:

```powershell
Copy-Item .env.example .env
```

2. Edit `.env` and set `ORS_API_KEY`.

Getting an OpenRouteService API key

1. Sign up at https://openrouteservice.org/dev/#/signup
2. Open the Dashboard -> API Keys
3. Copy 'Basic Key' it into `.env` as `ORS_API_KEY`

Quick setup

Windows (PowerShell)

```powershell
python -m venv .venv
& ".\.venv\Scripts\Activate.ps1"
pip install -r requirements.txt
python manage.py migrate
python manage.py import_fuel_prices "/full/path/to/fuel-prices-for-be-assessment.csv"
python manage.py runserver
```

macOS (Terminal)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py import_fuel_prices "/full/path/to/fuel-prices-for-be-assessment.csv"
python manage.py runserver
```

Ubuntu (bash)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py import_fuel_prices "/path/to/fuel-prices-for-be-assessment.csv"
python manage.py runserver 0.0.0.0:8000
```

Importing with a limit

Use `--limit` to process a smaller number of rows for a faster test run:

```powershell
python manage.py import_fuel_prices "/full/path/to/fuel-prices-for-be-assessment.csv" --limit 100

example:
python manage.py import_fuel_prices "e:/MyProjects/New folder/fuel-prices-for-be-assessment.csv" --limit 100
```

API usage

- Endpoint: `POST /api/route/`
- Body (JSON):

```json
{
  "start": "<address or City, State>",
  "end": "<address or City, State>"
}
```

- Response: route geometry, selected fuel stops (id, name, price, coords), estimated gallons and cost.

Three real payload examples (from the CSV locations)

```json
{ "start": "Big Cabin, OK", "end": "Gila Bend, AZ" }
```

```json
{ "start": "Tomah, WI", "end": "Council Bluffs, IA" }
```

```json
{ "start": "Jacksonville, FL", "end": "Ocala, FL" }
```

Example curl

```powershell
curl -X POST http://127.0.0.1:8000/api/route/ -H "Content-Type: application/json" -d '{"start":"Big Cabin, OK","end":"Gila Bend, AZ"}'
```

Implementation notes

- One ORS directions call is used for routing (after geocoding start/end). Station selection is a prototype: stations are filtered by proximity to route fractions and the cheapest candidate is chosen.
- Fuel cost estimate is simplified: total miles / MPG, then multiplied by average selected-stop price.

Recording the Loom demo

- Show the running server and Postman or curl performing one `POST /api/route/` request.
- Briefly open the route view and the import command to explain the approach.
- Keep recording under 5 minutes. Upload Loom and attach it with the code when submitting.

Deliverables

- This repo (code) and a Loom video demonstrating the API working and a short code walkthrough.