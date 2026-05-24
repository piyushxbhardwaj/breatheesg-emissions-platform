# BreatheESG Emissions Ingestion & Review Platform

This is a production-minded prototype for an enterprise ESG emissions data ingestion and analyst review system. It handles multi-tenant data parsing, validation, carbon footprint normalization, and audit review workflows for three core data sources:
1. **SAP Fuel & Procurement**: Handles German/English headings, mixed dates, and fuel volumes.
2. **Utility Electricity Invoices**: Splices non-calendar billing cycles across calendar months.
3. **Corporate Travel Booking Logs**: Computes travel distances (Haversine formula via IATA coordinates), hotel room-nights, and spend-based ground transport.

---

## Technical Stack
* **Backend**: Django, Django REST Framework, SQLite (default for development/tests, configuration ready for PostgreSQL).
* **Frontend**: React, Vite, Vanilla CSS.
* **Architecture**: Context-driven database-level multi-tenancy, service-layer decoupled business logic, and transaction-safe audit logging.

---

## Quick Start Instructions

### 1. Set Up and Run the Backend

Navigate to the `backend/` directory, set up the virtual environment, install dependencies, run migrations, seed standard database contexts, and start the development server:

```bash
# Move to backend
cd backend

# Create Python Virtual Environment (if not done)
python -m venv .venv

# Activate Virtual Environment
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install django djangorestframework django-cors-headers

# Make and apply database migrations
python manage.py makemigrations
python manage.py migrate

# Seed database with tenants and standard emission factors
python manage.py seed_data

# Run the Django backend development server
python manage.py runserver
```

The REST API will be running at: `http://localhost:8000/api/`

### 2. Run the Backend Test Suite
Verify that all unit tests (covering isolation, parsing, and calculations) pass:
```bash
python manage.py test
```

---

### 3. Set Up and Run the Frontend

In a separate terminal, navigate to the `frontend/` directory, install packages, and start the Vite server:

```bash
# Move to frontend
cd frontend

# Install package dependencies
npm install

# Start Vite React server
npm run dev
```

Open your browser at the dev link (usually `http://localhost:5173/`).

---

## Folder Structure Summary

* [backend/core/](file:///d:/Project/BreatheESG%20assignment/backend/core/): Main Django application settings, routing, and HTTP CORS middleware configurations.
* [backend/esg_ingest/](file:///d:/Project/BreatheESG%20assignment/backend/esg_ingest/): Core ingestion application containing models, views, serializers, and url routing.
* [backend/esg_ingest/services/](file:///d:/Project/BreatheESG%20assignment/backend/esg_ingest/services/): Business logic layer containing parser mapping, validation anomaly checks, and metric normalizers.
* [frontend/src/](file:///d:/Project/BreatheESG%20assignment/frontend/src/): React dashboard pages (Uploads, Review Queue, Approved Records) and Vanilla CSS stylesheet layout.
* [data/](file:///d:/Project/BreatheESG%20assignment/data/): Realistic sample CSV files representing the three enterprise data source formats.

---

## Supporting Architecture Documentation

Please review the companion documents detailing technical architecture and governance designs:
* [MODEL.md](file:///d:/Project/BreatheESG%20assignment/MODEL.md): Explains tenant database isolation, raw preservation, and scope calculation models.
* [DECISIONS.md](file:///d:/Project/BreatheESG%20assignment/DECISIONS.md): Justifies parsing rules, Haversine distance, and billing splitting algorithms.
* [TRADEOFFS.md](file:///d:/Project/BreatheESG%20assignment/TRADEOFFS.md): Outlines three deliberate omissions and their architectural reasoning.
* [SOURCES.md](file:///d:/Project/BreatheESG%20assignment/SOURCES.md): Analyzes real-world ERP and portal logs structures and limitations.
