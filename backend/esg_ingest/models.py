import uuid
from django.db import models
from esg_ingest.tenant_context import get_current_tenant_id

class Tenant(models.Model):
    """
    Represents client companies that subscribe to the platform.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TenantScopedManager(models.Manager):
    """
    Enforces row-level multi-tenancy isolation at the database queryset layer.
    """
    def get_queryset(self):
        tenant_id = get_current_tenant_id()
        qs = super().get_queryset()
        if tenant_id is not None:
            return qs.filter(tenant_id=tenant_id)
        return qs


class TenantScopedModel(models.Model):
    """
    Abstract base model for models that must isolate data by tenant.
    """
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="%(class)s_records")

    # Enforce queryset filtering on the primary manager
    objects = TenantScopedManager()
    
    # Expose a global objects manager specifically for admin/backend jobs
    global_objects = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Automatically assign tenant from context if not already set
        if not hasattr(self, 'tenant') or self.tenant_id is None:
            tenant_id = get_current_tenant_id()
            if tenant_id:
                self.tenant_id = tenant_id
        super().save(*args, **kwargs)


class DataSource(TenantScopedModel):
    """
    Tracks metadata and ingestion states for files uploaded by tenants.
    """
    STATUS_CHOICES = (
        ('PENDING', 'Pending Ingestion'),
        ('PARSING', 'Parsing CSV File'),
        ('COMPLETED', 'Ingestion Completed'),
        ('FAILED', 'Ingestion Failed'),
    )

    SOURCE_CHOICES = (
        ('SAP_FUEL', 'SAP Fuel & Procurement'),
        ('UTILITY_ELECTRICITY', 'Utility Electricity Invoices'),
        ('CORPORATE_TRAVEL', 'Corporate Travel Logs'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_type = models.CharField(max_length=50, choices=SOURCE_CHOICES)
    file_name = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64, help_text="SHA-256 hash of file contents for idempotency verification")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.CharField(max_length=150, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    error_message = models.TextField(blank=True, null=True)
    row_count = models.IntegerField(default=0)

    class Meta:
        # File hash should be unique within a tenant context to support multiple tenants uploading the same common templates
        unique_together = ('tenant', 'file_hash')

    def __str__(self):
        return f"{self.file_name} ({self.source_type}) - {self.status}"


class RawRecord(TenantScopedModel):
    """
    Preserves exact uploaded CSV rows before normalizations or corrections.
    """
    STATUS_CHOICES = (
        ('UNPROCESSED', 'Unprocessed'),
        ('VALIDATED', 'Validated (Success)'),
        ('FAILED_VALIDATION', 'Validation Failed'),
        ('NORMALIZED', 'Normalized'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name="raw_records")
    row_number = models.IntegerField()
    raw_data = models.JSONField(help_text="Original cell values mapped as a key-value dictionary")
    import_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNPROCESSED')
    errors = models.JSONField(default=list, blank=True, help_text="Array of parser or validator errors")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['row_number']

    def __str__(self):
        return f"RawRow {self.row_number} - Source: {self.data_source.file_name}"


class EmissionFactorReference(models.Model):
    """
    Houses governed emission factors derived from IPCC, DEFRA, EPA, etc.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=100, help_text="Broad classification, e.g., Fuel, Grid Electricity, Air Travel, Hotel")
    activity_type = models.CharField(max_length=150, help_text="Specific activity, e.g., Diesel, Grid Electricity (US eGRID), Flight (Short-haul), Hotel room-night")
    source_name = models.CharField(max_length=100, help_text="Regulatory source database, e.g. DEFRA 2023, EPA eGRID 2023, IPCC AR6")
    factor_value = models.DecimalField(max_digits=12, decimal_places=6, help_text="CO2e value per factor unit")
    unit = models.CharField(max_length=50, help_text="Unit of emission mapping, e.g., kg CO2e/liter, kg CO2e/kWh, kg CO2e/passenger-mile")
    valid_from = models.DateField()
    valid_to = models.DateField()

    class Meta:
        ordering = ['category', 'activity_type', '-valid_from']

    def __str__(self):
        return f"{self.activity_type} ({self.source_name}) - {self.factor_value} {self.unit}"


class NormalizedEmissionRecord(TenantScopedModel):
    """
    The audit-ready normalized table storing calculated CO2e emissions.
    """
    REVIEW_CHOICES = (
        ('PENDING_REVIEW', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    SCOPE_CHOICES = (
        (1, 'Scope 1 (Direct)'),
        (2, 'Scope 2 (Indirect - Utilities)'),
        (3, 'Scope 3 (Indirect - Other/Travel)'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    raw_record = models.ForeignKey(RawRecord, on_delete=models.CASCADE, related_name="normalized_records", null=True, blank=True)
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name="normalized_records")
    
    scope = models.IntegerField(choices=SCOPE_CHOICES)
    category = models.CharField(max_length=100, help_text="e.g. Stationary Combustion, Purchased Electricity, Business Travel")
    activity_type = models.CharField(max_length=150, help_text="e.g. Diesel Fuel, Purchased Electricity (MISO Grid), Air Travel - Short-haul")
    
    original_quantity = models.DecimalField(max_digits=15, decimal_places=4)
    original_unit = models.CharField(max_length=50)
    
    normalized_quantity_co2e = models.DecimalField(max_digits=15, decimal_places=6, help_text="Calculated greenhouse emissions in metric tonnes of CO2e (tCO2e)")
    factor_reference = models.ForeignKey(EmissionFactorReference, on_delete=models.PROTECT, related_name="normalized_records", null=True, blank=True)
    
    start_date = models.DateField()
    end_date = models.DateField()
    facility_or_plant = models.CharField(max_length=100)
    
    review_status = models.CharField(max_length=20, choices=REVIEW_CHOICES, default='PENDING_REVIEW')
    suspicious_flag = models.BooleanField(default=False)
    suspicious_reasons = models.JSONField(default=list, blank=True, help_text="Array of warnings explaining why this row is suspicious")
    
    is_locked = models.BooleanField(default=False, help_text="Locked records cannot be edited or modified since they have been approved for audit")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.activity_type} - {self.normalized_quantity_co2e} tCO2e ({self.review_status})"


class ReviewAction(TenantScopedModel):
    """
    Audit log record capturing review queues, edits, overrides, approvals, and lock actions.
    """
    ACTION_CHOICES = (
        ('CREATE', 'Created Record'),
        ('EDIT', 'Edited Fields'),
        ('APPROVE', 'Approved & Locked Record'),
        ('REJECT', 'Rejected Record'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(NormalizedEmissionRecord, on_delete=models.CASCADE, related_name="audit_logs")
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.CharField(max_length=150, default="System Ingestion")
    performed_at = models.DateTimeField(auto_now_add=True)
    changes = models.JSONField(null=True, blank=True, help_text="Before and After audit map, e.g. {'normalized_quantity_co2e': {'before': 10, 'after': 8.5}}")
    comment = models.TextField(blank=True, null=True, help_text="Analyst explanation for why edits/overrides were executed")

    class Meta:
        ordering = ['-performed_at']

    def __str__(self):
        return f"{self.action_type} on {self.record.id} by {self.performed_by} at {self.performed_at}"
