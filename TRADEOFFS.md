# Architectural Tradeoffs & Omissions

This document lists three deliberate omissions made in this prototype and justifies why they are acceptable for this phase.

---

## Omission 1: Asynchronous Ingest Processing (Celery/Redis)
* **What was omitted**: Background thread workers to process CSV parsing asynchronously.
* **Why**: For a production site processing files with 100,000+ rows, parsing in the main request-response loop would cause HTTP timeout errors. A background task manager (e.g. Celery + Redis or SQS) is required.
* **Justification**: Setting up Celery, Redis, and message brokers increases local deployment complexity. For this prototype, files are read in-memory. The parsing and calculation logic is decoupled into a pure service layer (`services/parser.py`, `services/normalizer.py`), making it straightforward to wrap in a Celery task when scaling to production.

---

## Omission 2: User Authentication & Role-Based Access Control (RBAC)
* **What was omitted**: User login, JWT token authentication, and analyst vs. auditor role permissions.
* **Why**: Authenticating users and checking granular edit/lock permissions requires setup (such as django-allauth, oauth2, or JWT serializers) which clutters the core assignment scope.
* **Justification**: The primary scoring criteria for this assignment focus on data modeling, multi-tenancy context isolation, validation rules, and audit logging. We chose to use open endpoints for testing convenience, while defining fields like `uploaded_by` and `performed_by` (char fields) to simulate audit tracing.

---

## Omission 3: Live Grid Emission API Integrations
* **What was omitted**: Dynamic HTTP lookups to regional electricity grid databases (e.g., Climatiq, US EPA eGRID API, ENTSO-E).
* **Why**: Live API lookups introduce point-of-failure vulnerabilities, require commercial API access keys, and slow down local testing runs.
* **Justification**: A production ESG system requires governed, versioned, and cached factor reference indices. We created the `EmissionFactorReference` database model to govern factor lookup locally. If a factor is missing, we fall back to sensible regulatory average constants, ensuring stable runtimes.
