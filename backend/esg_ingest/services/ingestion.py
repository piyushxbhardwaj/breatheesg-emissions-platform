from django.db import transaction
from esg_ingest.models import DataSource, RawRecord, NormalizedEmissionRecord, ReviewAction
from esg_ingest.services.parser import parse_csv_file, calculate_file_hash
from esg_ingest.services.validator import validate_raw_record, run_anomaly_checks
from esg_ingest.services.normalizer import normalize_and_save_record

def process_file_upload(tenant, file_name, file_bytes, source_type, uploaded_by=None):
    """
    Ingests a CSV file. Implements idempotency via file SHA-256 hash.
    Orchestrates parsing, validation, normalization, and anomaly detection.
    """
    # Calculate SHA-256 hash
    file_hash = calculate_file_hash(file_bytes)

    # Check for duplicate file upload (Idempotency check)
    existing_source = DataSource.objects.filter(tenant=tenant, file_hash=file_hash).first()
    if existing_source:
        raise ValueError(
            f"Idempotency Guard: A file with the exact same content ('{existing_source.file_name}') "
            f"was already uploaded for this tenant on {existing_source.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')}."
        )

    # Create DataSource in transaction
    with transaction.atomic():
        data_source = DataSource.objects.create(
            tenant=tenant,
            source_type=source_type,
            file_name=file_name,
            file_hash=file_hash,
            uploaded_by=uploaded_by or "Analyst",
            status='PENDING'
        )

    try:
        # Step 1: Parse CSV into RawRecords (bulk created inside parser)
        data_source.status = 'PARSING'
        data_source.save()
        
        raw_records = parse_csv_file(data_source, file_bytes)

        # Step 2: Validate, Normalize, and Run Anomaly Checks on each row
        failures_count = 0
        success_count = 0

        for raw_rec in raw_records:
            # Skip if it already has headers/columns configuration errors from the parser stage
            if raw_rec.import_status == 'FAILED_VALIDATION':
                failures_count += 1
                continue

            # Run raw formatting validations (missing columns, blank entries)
            is_valid = validate_raw_record(raw_rec)
            if not is_valid:
                failures_count += 1
                continue

            # Process record to normalized table (converts units, splits dates, looks up factors)
            normalized_records = normalize_and_save_record(raw_rec)
            
            if not normalized_records:
                failures_count += 1
                continue

            # Run statistical/logical anomaly detection on the newly created records
            for norm_rec in normalized_records:
                run_anomaly_checks(norm_rec)
                
                # Write an initial audit log for trace history
                ReviewAction.objects.create(
                    tenant=tenant,
                    record=norm_rec,
                    action_type='CREATE',
                    performed_by=uploaded_by or "System Ingestion",
                    comment="Initial system ingestion and normalization"
                )

            success_count += 1

        # Determine overall completion state
        if failures_count == len(raw_records) and len(raw_records) > 0:
            data_source.status = 'FAILED'
            data_source.error_message = "All rows failed validation during processing."
        else:
            data_source.status = 'COMPLETED'
            if failures_count > 0:
                data_source.error_message = f"Ingestion completed with {failures_count} row validation failures."
        
        data_source.save()
        return data_source

    except Exception as e:
        data_source.status = 'FAILED'
        data_source.error_message = f"Critical Pipeline Exception: {str(e)}"
        data_source.save()
        raise e
