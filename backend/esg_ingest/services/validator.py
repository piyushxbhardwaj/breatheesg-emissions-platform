from decimal import Decimal
from django.db.models import Avg, StdDev
from esg_ingest.models import RawRecord, NormalizedEmissionRecord

def validate_raw_record(raw_record):
    """
    Validates a RawRecord's dictionary data before and during processing.
    Updates import_status and errors list. Returns True if valid, False otherwise.
    """
    errors = []
    data = raw_record.raw_data
    source_type = raw_record.data_source.source_type

    # 1. Check for blank or null values in primary fields
    if source_type == 'SAP_FUEL':
        quantity = data.get('quantity')
        unit = data.get('unit')
        posting_date = data.get('posting_date')
        plant = data.get('plant_code')

        if not quantity:
            errors.append("SAP Fuel Row: Missing quantity value.")
        if not unit:
            errors.append("SAP Fuel Row: Missing unit of measure (UOM).")
        if not posting_date:
            errors.append("SAP Fuel Row: Missing posting date.")
        if not plant:
            errors.append("SAP Fuel Row: Missing plant/facility code.")

    elif source_type == 'UTILITY_ELECTRICITY':
        meter_id = data.get('meter_id')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        qty = data.get('quantity_kwh')
        cost = data.get('cost')

        if not meter_id:
            errors.append("Utility Invoice Row: Missing Meter ID.")
        if not start_date or not end_date:
            errors.append("Utility Invoice Row: Missing billing dates.")
        if not qty:
            errors.append("Utility Invoice Row: Missing kWh consumption quantity.")
        if not cost:
            errors.append("Utility Invoice Row: Missing invoice cost.")

    elif source_type == 'CORPORATE_TRAVEL':
        employee = data.get('employee_id')
        travel_date = data.get('travel_date')
        category = data.get('category')
        spend = data.get('spend')

        if not employee:
            errors.append("Corporate Travel Row: Missing employee identifier.")
        if not travel_date:
            errors.append("Corporate Travel Row: Missing booking date.")
        if not category:
            errors.append("Corporate Travel Row: Missing travel category classification.")
        if not spend:
            errors.append("Corporate Travel Row: Missing travel cost/spend.")

    if errors:
        raw_record.import_status = 'FAILED_VALIDATION'
        # Append errors avoiding duplicates
        existing = raw_record.errors or []
        for e in errors:
            if e not in existing:
                existing.append(e)
        raw_record.errors = existing
        raw_record.save()
        return False
        
    return True


def run_anomaly_checks(norm_record):
    """
    Analyzes a NormalizedEmissionRecord for suspicious patterns, outliers,
    exorbitant rates, and duplicate submissions.
    Flags suspicious = True and populates suspicious_reasons.
    """
    reasons = []
    
    # 1. Sanity: Negative quantities or negative emissions
    if norm_record.original_quantity < 0:
        reasons.append(f"Negative activity quantity: {norm_record.original_quantity}")
    if norm_record.normalized_quantity_co2e < 0:
        reasons.append(f"Negative calculated emissions: {norm_record.normalized_quantity_co2e} tCO2e")

    # 2. Duplicate Detection
    # Look for other records with the same scope, plant, dates, and identical raw quantities
    duplicates = NormalizedEmissionRecord.objects.filter(
        tenant=norm_record.tenant,
        scope=norm_record.scope,
        facility_or_plant=norm_record.facility_or_plant,
        start_date=norm_record.start_date,
        end_date=norm_record.end_date,
        original_quantity=norm_record.original_quantity,
        original_unit=norm_record.original_unit
    ).exclude(id=norm_record.id)

    if duplicates.exists():
        reasons.append("Identical record exists in the system (potential duplicate upload).")

    # 3. Cost or Rate Anomalies
    raw_data = norm_record.raw_record.raw_data if norm_record.raw_record else {}
    
    # Electricity billing cost anomalies ($/kWh)
    if norm_record.category == "Purchased Electricity":
        cost_str = raw_data.get('cost', '0')
        try:
            cost = Decimal(cost_str.replace(',', ''))
            kwh = norm_record.original_quantity
            if kwh > 0:
                cost_per_kwh = cost / kwh
                # Normal rates are between $0.03 and $0.80. Let's flag outside $0.02 - $1.50
                if cost_per_kwh < Decimal('0.02') or cost_per_kwh > Decimal('1.50'):
                    reasons.append(f"Unusual grid tariff rate: ${cost_per_kwh:.4f} per kWh (normal average: $0.10-$0.30)")
        except Exception:
            pass

    # Travel: flight distance anomalies
    if norm_record.category == "Business Travel - Flights":
        origin = raw_data.get('origin', '')
        dest = raw_data.get('destination', '')
        dist_str = raw_data.get('distance_miles', '0')
        
        try:
            dist = Decimal(dist_str.replace(',', ''))
            if dist == 0 and norm_record.original_quantity == 0:
                reasons.append(f"Flight origin/destination coordinates not found for mapping '{origin}' -> '{dest}'")
        except Exception:
            pass

    # 4. Outlier Detection: Quantity vs historical average
    # Fetch historical records in the same category and facility
    history = NormalizedEmissionRecord.objects.filter(
        tenant=norm_record.tenant,
        category=norm_record.category,
        facility_or_plant=norm_record.facility_or_plant,
        review_status='APPROVED'
    )
    
    if history.count() >= 5:
        # Calculate standard deviation and average
        stats = history.aggregate(avg_qty=Avg('original_quantity'), std_qty=StdDev('original_quantity'))
        avg = stats['avg_qty']
        std = stats['std_qty']
        
        if avg and std:
            # Flag if quantity is more than 3 standard deviations away from the mean
            threshold = avg + (3 * std)
            if norm_record.original_quantity > threshold:
                reasons.append(f"Statistical outlier: Quantity {norm_record.original_quantity} is >3x std-dev from historical average ({avg:.2f})")
    else:
        # Simple heuristic threshold check for safety
        if norm_record.original_quantity > Decimal('1000000'):
            reasons.append("Activity quantity exceeds high-scale threshold (> 1,000,000 units)")

    if reasons:
        norm_record.suspicious_flag = True
        norm_record.suspicious_reasons = reasons
        norm_record.save()
        
    return norm_record.suspicious_flag, reasons
