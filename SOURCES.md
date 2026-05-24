# Researched Data Sources & Industry Formats

This document outlines the real-world enterprise system formats that inspired the schemas and parser mappings in this platform.

---

## 1. SAP Fuel & Procurement (ERP Ledger Exports)
* **Real-World Origins**: SAP ERP central procurement modules (specifically Materials Management - MM, and Financial Accounting - FI).
* **Observed Formats**:
  - Raw table dumps of `MSEG` (Document Segment: Material) and `MKPF` (Header: Material Document).
  - Columns contain localized abbreviations depending on client setup (e.g. `Werk` for Plant, `Menge` for Quantity, `ME` or `Einheit` for Unit of Measure).
* **Enterprise Limitations**:
  - Date columns are formatted based on regional database configurations (e.g. European `DD.MM.YYYY` vs ISO `YYYY-MM-DD`).
  - Units of measure are often inconsistent (e.g., liters might be represented as `L`, `Ltr`, `LIT`, or `Einheit`).

---

## 2. Utility Electricity Exports
* **Real-World Origins**: Utility invoice exports from regional portals (e.g., PGE, Duke Energy, National Grid, ConEd) or bulk bill-scraping services.
* **Observed Formats**:
  - CSV files containing columns: `Meter Number`, `Service Start Date`, `Service End Date`, `Usage (kWh)`, `Total Charge`.
* **Enterprise Limitations**:
  - Billing cycles do not match calendar months. Invoices are generated relative to local meter-reading routes (e.g. billing cycle spanning Nov 14 to Dec 13).
  - Tariff rates fluctuate dynamically depending on peak seasons or contract tiers.

---

## 3. Corporate Travel (Booking Logs)
* **Real-World Origins**: Exports from travel booking management hubs (specifically Concur Travel, Navan/TripActions, or flight manifest logs).
* **Observed Formats**:
  - CSV exports with columns: `Employee ID`, `Transaction Date`, `Expense Category` (Flight, Hotel, Ground), `Origin Code`, `Destination Code`, `Distance`, `Nights`, `Total Cost`.
* **Enterprise Limitations**:
  - Flight distance columns are frequently left empty because booking databases prioritize airport route logs (IATA codes) over mileage metrics.
  - Category listings include diverse transit options (train, rental cars, rideshare, taxi) which require mapping to a single spend-based Scope 3 category.
