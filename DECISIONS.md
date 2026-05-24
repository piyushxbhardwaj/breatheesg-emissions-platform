# Architectural Decisions & Assumptions

This document explains the core technical decisions and assumptions made when building the ESG Ingestion engine.

---

## 1. SAP Fuel & Procurement Integration Decisions
* **Decision**: Support case-insensitive headers in both German and English (e.g. `Materialnummer` or `Material Number`, `Menge` or `Quantity`, `Einheit` or `Unit`, `Werk` or `Plant`, `Buchungsdatum` or `Posting Date`).
* **Justification**: SAP ERP configurations are heavily dependent on company localization. Mixed-language columns are a primary source of ingestion failures in real-world platforms.
* **Assumptions**: 
  - Standardized plant code mappings are resolved to a single string identifier.
  - Non-standard volume units (e.g., Gallons) are mathematically converted to Liters (liquids) or Cubic Meters (gases) using conversion constants prior to multiplying by the emission factors.

---

## 2. Utility Electricity Splitting Decisions
* **Decision**: Implement a **daily average calendar-month splitting** algorithm for utility periods that cross calendar boundaries.
* **Justification**: Utility companies issue invoices based on physical reading dates (e.g. Nov 12 - Dec 11), not calendar months. Aggregating raw invoices directly into calendar-month reporting leads to double-counting and massive shifts.
* **Algorithm**:
  1. Determine the total duration of the billing invoice (in days).
  2. Compute daily average usage: `daily_usage = total_kwh / total_days`.
  3. Detect calendar month boundaries intersected by the invoice.
  4. Generate separate `NormalizedEmissionRecord` items for each segment, assigning proportional kWh.
  5. Link each segment back to the single parent `RawRecord` via ForeignKey.

---

## 3. Corporate Travel Calculation Decisions
* **Decision**: Embed an IATA airport code database to calculate flight distances using the **Haversine great-circle formula** if the file does not contain a distance metric.
* **Justification**: Travel agents and booking systems often export flights with origin/destination codes (JFK, LHR) but exclude distance. Haversine calculations guarantee distance estimations without relying on external API networks.
* **Flight Tiering**:
  - Distance < 300 miles: Classed as **Short-haul** (DEFRA factor applied).
  - Distance 300 to 2300 miles: Classed as **Medium-haul**.
  - Distance > 2300 miles: Classed as **Long-haul**.
* **Spend-Based Fallback**: For ground transport logs where distance is omitted and cannot be mapped, we apply a spend-based factor (e.g., kg CO2e per dollar spent on taxi/train transit).

---

## 4. Ingestion Idempotency Decisions
* **Decision**: Require SHA-256 file content hash checks during upload.
* **Justification**: Accidental double-clicks or uploading the same CSV template multiple times causes duplicate carbon records.
* **Enforcement**:
  - Hash is computed on the file contents in-memory.
  - If a `DataSource` entry with the same hash exists under that specific tenant context, the upload is rejected with a `400 Bad Request` immediately. This isolates duplicate uploads within a tenant context while allowing different tenants to upload identical templates.
