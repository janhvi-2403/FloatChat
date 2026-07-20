# FloatChat

FloatChat is a full-stack ocean data exploration project built around Argo float observations. It combines a FastAPI backend, a Streamlit dashboard, and a data processing layer to fetch, cache, and visualize oceanographic data from the Argo program.

## Overview

The project is designed to help users:
- search Argo floats by geographic region and time range
- retrieve float profile data such as temperature, salinity, and pressure
- visualize float locations and profile trends through an interactive web dashboard
- cache data efficiently to reduce repeated requests and improve performance

## What has been implemented so far

### Backend API
- FastAPI-based REST API for querying Argo data
- Endpoints for:
  - region-based data retrieval
  - float-specific data retrieval
  - float search by region
  - admin cache and monitoring endpoints

### Frontend Dashboard
- Streamlit web app for interactive querying and visualization
- Sidebar filters for longitude, latitude, date, and depth range
- Map view for float locations
- Plotly charts for temperature and salinity profiles

### Data & Caching Layer
- Integration with Argo data via the ArgoPy ecosystem
- Multi-layer caching using:
  - in-memory cache
  - Redis cache
  - PostgreSQL-backed persistence for processed results
- Rate limiting and metrics collection
- Background pre-caching for popular regions

### Data Infrastructure
- PostgreSQL database models for cached requests and related metadata
- Redis service for fast caching
- Docker Compose setup for local services
- Containerized application setup through Docker

## Tech Stack

### Core
- Python 3.12
- FastAPI
- Streamlit
- Uvicorn

### Data & Science Libraries
- ArgoPy
- xarray
- pandas
- numpy
- scipy
- plotly
- folium

### Storage & Infrastructure
- PostgreSQL
- Redis
- SQLAlchemy
- Docker
- Docker Compose

### Additional Libraries
- pydantic
- python-dotenv
- requests
- langchain / chromadb / sentence-transformers (present in dependencies for future AI/RAG workflows)

## Project Structure

```text
backend/
  main.py                 # FastAPI app entry point
  routes/                 # API routes for data and admin operations
  utils/                  # fetcher, cache, metrics, pre-cache services
frontend/
  app.py                  # Streamlit UI dashboard
models/
  database.py             # SQLAlchemy models and DB setup
services/
  rag_pipeline.py         # placeholder for future RAG-based workflows
ingestion/
  download_data.py
  ingest.py               # ingestion helpers
config.py                 # environment-driven settings
docker-compose.yml        # local services configuration
Dockerfile                # container image definition
requirements.txt         # Python dependencies
start.sh                  # local startup script
```

## Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/janhvi-2403/FloatChat.git
cd FloatChat
```

### 2. Create environment variables
Copy the sample environment file and update values if needed:

```bash
copy .env.example .env
```

### 3. Start local services with Docker Compose
```bash
docker compose up --build
```

This starts:
- Redis
- PostgreSQL
- the application service
- Chroma

### 4. Run the backend locally
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 5. Run the frontend locally
```bash
streamlit run frontend/app.py
```

## API Endpoints

### Health
- GET /health
- GET /health/ready

### Data
- POST /api/data/region
- GET /api/data/float/{float_id}
- GET /api/data/search

### Admin
- GET /api/admin/cache/status
- GET /api/admin/cache/stats
- DELETE /api/admin/cache
- POST /api/admin/cache/precache

## Configuration

The project uses environment variables defined in .env. A sample file is available at .env.example.

Key configuration values include:
- DATABASE_URL
- REDIS_URL
- CACHE_TTL_SECONDS
- RATE_LIMIT_PER_MINUTE
- API_HOST / API_PORT

## Current Status

The project already includes:
- a working FastAPI backend structure
- an interactive Streamlit frontend
- Argo data fetching and data transformation logic
- caching and monitoring infrastructure
- containerized local deployment support

There is still room for future improvements such as:
- a more polished production deployment setup
- expanded tests
- improved documentation for ingestion workflows
- full AI/RAG integration using the existing dependencies

## Next Steps

Possible future enhancements include:
- adding automated tests
- adding authentication and user roles
- improving UI/UX for data exploration
- deploying the app to cloud services
- expanding the RAG workflow and vector search capabilities

## License

This project is currently intended for personal or educational use unless otherwise specified.
