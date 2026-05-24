# Data Model & Architecture Design

This document details the database schema and structural paradigms used to construct the BreatheESG Ingestion platform.

---

## 1. Multi-Tenancy Isolation Pattern

To defend against accidental cross-tenant data leakage, the platform utilizes a **Shared Database, Shared Schema (Discriminator Column)** strategy, backed by context-aware query isolation:

```
[ HTTP Request / X-Tenant-ID ] 
         │
         ▼
┌────────────────────────────────────────┐
│ TenantMiddleware (Context Setter)      │
└────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ TenantScopedManager (Query Filter)     │
└────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ TenantScopedModel Base Class           │
│ objects = TenantScopedManager()        │
└────────────────────────────────────────┘
```

1. **Middleware Injection**: The `TenantMiddleware` intercepts every incoming HTTP request, reads the `X-Tenant-ID` header (or `tenant_id` query parameter), and saves it into a thread-safe and async-safe Python `contextvars.ContextVar`.
2. **Queryset Level Filter**: The `TenantScopedModel` abstract base class overrides the default manager with `TenantScopedManager`. This manager intercepts all standard querysets (`get_queryset()`) and automatically appends a `.filter(tenant_id=current_tenant_id)` clause.
3. **Database Write Safety**: In `TenantScopedModel.save()`, if a tenant context is active and the model instance does not already have a tenant bound, it automatically assigns `self.tenant_id = active_tenant_id` from the contextvar.
4. **Administrative Bypass**: The manager `global_objects = models.Manager()` is declared explicitly to bypass isolation filters for administrative commands (e.g. seeding, database migrations).

---

## 2. Ingestion Tracking & Raw Preservation

Preserving original data is a key requirement for ESG auditability. If an auditor asks where a number came from, we must trace it back to the exact cell in the source file:

* **DataSource**: Represents the upload event. Stored metadata includes filename, row count, uploading analyst name, and status. It computes and checks a SHA-256 hash of the file bytes to prevent duplicate uploads.
* **RawRecord**: Stores every row of the CSV exactly as uploaded in a `JSONField` called `raw_data`. It tracks a row-level `import_status` (`UNPROCESSED`, `VALIDATED`, `FAILED_VALIDATION`, `NORMALIZED`) and a list of parsing `errors`.
* **NormalizedEmissionRecord**: Holds the structured, normalized carbon data. It has a `ForeignKey` linking it back to the corresponding `RawRecord` (and thus `DataSource`), establishing a clear line of custody.

---

## 3. Scope 1/2/3 Handling

Emissions are mapped according to the Greenhouse Gas (GHG) Protocol corporate standard:

| GHG Scope | Classification | Data Source | Input Units | Calculation Basis |
| :--- | :--- | :--- | :--- | :--- |
| **Scope 1** | Direct fuel combustion | SAP ERP Export | Liters, Gallons, Cubic Meters | Fuel volume converted to liters/m3 * IPCC/EPA fuel-type emission factors. |
| **Scope 2** | Indirect energy | Utility Bills | kWh | Electrical consumption * grid region factors. Non-calendar periods split daily. |
| **Scope 3** | Other indirect travel | Booking Logs | Flights (IATA), Hotels, Spend | Flights distance (miles) * short/medium/long tiers. Hotel nights. Ground transport USD spend. |

---

## 4. Audit Trail & Record Locking

Once carbon data is finalized, it must be locked to prevent tampering. Changes made prior to approval must be recorded:

* **Governance Locking**: When an analyst approves a record, the database sets `review_status = 'APPROVED'` and `is_locked = True`. Serializer validation rules reject any future update request on locked records, ensuring data permanence.
* **ReviewAction (Audit Logs)**: Every state modification (`CREATE`, `EDIT`, `APPROVE`, `REJECT`) creates a `ReviewAction` log. For edits, it stores a snapshot of changed attributes (`changes` JSONField) containing the before-and-after values along with the mandatory analyst justification comment.
