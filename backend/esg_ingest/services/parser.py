import csv
import io
import hashlib
from esg_ingest.models import RawRecord

# Header mapping dictionaries. Keys are standard names, values are list of acceptable aliases (case-insensitive).
HEADER_ALIASES = {
    'SAP_FUEL': {
        'material_number': ['material number', 'materialnummer', 'material', 'matnum', 'material_number'],
        'quantity': ['quantity', 'menge', 'qty', 'amount', 'menge_qty'],
        'unit': ['unit', 'einheit', 'uom', 'me', 'base unit'],
        'plant_code': ['plant', 'werk', 'plant code', 'plant_code', 'werkscode'],
        'posting_date': ['posting date', 'buchungsdatum', 'date', 'posting_date', 'datum'],
    },
    'UTILITY_ELECTRICITY': {
        'meter_id': ['meter id', 'meterid', 'meter', 'meter_id', 'zaehlernummer'],
        'start_date': ['billing start', 'start date', 'billing period start', 'period start', 'start_date', 'von'],
        'end_date': ['billing end', 'end date', 'billing period end', 'period end', 'end_date', 'bis'],
        'quantity_kwh': ['kwh consumption', 'consumption', 'kwh', 'usage', 'quantity_kwh', 'verbrauch'],
        'tariff_rate': ['tariff rate', 'tariff', 'rate', 'tariff_rate', 'tarif'],
        'cost': ['total cost', 'cost', 'spend', 'amount', 'cost_spend', 'kosten'],
    },
    'CORPORATE_TRAVEL': {
        'employee_id': ['employee id', 'employee', 'staff id', 'employee_id', 'personalnummer'],
        'travel_date': ['travel date', 'date', 'booking date', 'travel_date', 'reisedatum'],
        'category': ['category', 'travel type', 'type', 'travel_category', 'kategorie'],
        'origin': ['origin', 'origin airport', 'from', 'abflugort'],
        'destination': ['destination', 'destination airport', 'to', 'zielort'],
        'distance_miles': ['distance_miles', 'distance', 'miles', 'distance (miles)', 'entfernung'],
        'hotel_nights': ['hotel_nights', 'nights', 'hotel nights', 'duration', 'uebernachtungen'],
        'spend': ['spend', 'cost', 'amount', 'cost_spend', 'ausgaben'],
    }
}

def calculate_file_hash(file_bytes):
    """
    Computes the SHA-256 hash of a file's content to support upload idempotency.
    """
    hasher = hashlib.sha256()
    hasher.update(file_bytes)
    return hasher.hexdigest()

def normalize_row_headers(headers, source_type):
    """
    Maps CSV header columns to their normalized keys based on aliases.
    Returns a dictionary of {normalized_key: csv_index}.
    """
    normalized_mapping = {}
    aliases = HEADER_ALIASES.get(source_type, {})
    
    for idx, raw_h in enumerate(headers):
        clean_h = raw_h.strip().lower()
        matched = False
        for std_key, alias_list in aliases.items():
            if clean_h in [a.lower() for a in alias_list]:
                normalized_mapping[std_key] = idx
                matched = True
                break
        if not matched:
            # Keep unrecognized headers with their original names as keys
            normalized_mapping[clean_h] = idx
            
    return normalized_mapping

def parse_csv_file(data_source, file_content_bytes):
    """
    Reads CSV bytes, identifies headers using aliases, creates RawRecords,
    and returns list of created RawRecord instances.
    """
    # Convert bytes to string stream
    try:
        decoded_content = file_content_bytes.decode('utf-8')
    except UnicodeDecodeError:
        try:
            decoded_content = file_content_bytes.decode('latin-1')  # SAP files are sometimes latin-1
        except Exception as e:
            raise ValueError(f"Unable to decode file content: {str(e)}")

    stream = io.StringIO(decoded_content)
    # Detect dialect (delimiter) - fallback to comma if detection fails
    try:
        # Sniff delimiter
        sample = stream.read(2048)
        stream.seek(0)
        dialect = csv.Sniffer().sniff(sample)
        reader = csv.reader(stream, dialect)
    except Exception:
        # Default to standard CSV reader
        stream.seek(0)
        reader = csv.reader(stream)

    try:
        headers = next(reader)
    except StopIteration:
        raise ValueError("The uploaded CSV file is empty.")

    header_map = normalize_row_headers(headers, data_source.source_type)
    
    # Check if critical headers are missing
    required_fields = HEADER_ALIASES[data_source.source_type].keys()
    missing_required = []
    for req in required_fields:
        if req not in header_map:
            missing_required.append(req)
            
    # We proceed even if some are missing, but we will store parsing error on RawRecord level
    raw_records = []
    row_count = 0

    for row in reader:
        if not row or all(cell.strip() == '' for cell in row):
            continue  # Skip empty lines
            
        row_count += 1
        
        # Build raw dict mapping: standard header -> cell value, or raw header -> cell value
        raw_dict = {}
        for key, col_idx in header_map.items():
            if col_idx < len(row):
                raw_dict[key] = row[col_idx].strip()
            else:
                raw_dict[key] = ""

        # Create RawRecord
        errors = []
        if missing_required:
            errors.append(f"Missing required columns in CSV header: {', '.join(missing_required)}")

        raw_rec = RawRecord(
            tenant=data_source.tenant,
            data_source=data_source,
            row_number=row_count,
            raw_data=raw_dict,
            import_status='FAILED_VALIDATION' if errors else 'UNPROCESSED',
            errors=errors
        )
        raw_records.append(raw_rec)

    # Bulk create RawRecords to optimize DB performance
    RawRecord.objects.bulk_create(raw_records)
    
    # Update DataSource row count
    data_source.row_count = row_count
    data_source.save()
    
    # Return the records for validation
    return RawRecord.objects.filter(data_source=data_source)
