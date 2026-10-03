# PulseOps Controllable Demo Application

This directory contains the instrumented FastAPI application used to simulate normal, slow, and error traffic patterns for PulseOps monitoring.

## Available Endpoints

- `GET /`: Root application metadata.
- `GET /api/health`: Healthy service check.
- `GET /api/users`: Example user records.
- `GET /api/orders`: Example order records.
- `GET /api/slow?delay=3`: Simulated slow endpoint (bounded between `0.0` and `10.0` seconds).
- `GET /api/error`: Simulated server error returning HTTP 500.
- `POST /api/demo/run`: Runs a controlled mix of healthy, slow, and failing requests to populate NexPulse events, derived metrics, and logs.

Administrators can run the showcase from the NexPulse Operational Control Center. It generates six requests, then asks NexPulse to evaluate alert rules so the resulting alert and incident can be explored in the workspace. Set `VITE_DEMO_APP_URL` for the frontend when the demo service is not at `http://127.0.0.1:8001`; set `DEMO_ALLOWED_ORIGINS` on the demo service to the frontend origin.

## Running Locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the FastAPI development server:
   ```bash
   uvicorn app:app --reload --port 8001
   ```
3. Interactive API documentation:
   `http://localhost:8001/docs`

## Running Tests

Execute the Phase 1 test suite:
```bash
pytest test_app.py
```

