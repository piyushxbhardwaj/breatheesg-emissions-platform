import math
from datetime import datetime, timedelta, date
from decimal import Decimal
from esg_ingest.models import NormalizedEmissionRecord, EmissionFactorReference, RawRecord

# Common IATA airport coordinates for distance calculations (Latitude, Longitude)
IATA_COORDINATES = {
    'JFK': (40.6398, -73.7789),
    'LHR': (51.4700, -0.4543),
    'CDG': (49.0097, 2.5479),
    'DXB': (25.2532, 55.3657),
    'SFO': (37.6190, -122.3749),
    'SIN': (1.3644, 103.9915),
    'SYD': (-33.9461, 151.1772),
    'FRA': (50.0379, 8.5622),
    'BOM': (19.0896, 72.8656),
    'DEL': (28.5562, 77.1001),
}

def parse_date(date_str):
    """
    Parses date strings of various formats.
    Supported: YYYY-MM-DD, DD.MM.YYYY, DD-MM-YYYY.
    """
    if not date_str:
        return None
        
    date_str = str(date_str).strip()
    
    # Try common formats
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d-%m-%y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
            
    # Fallback to standard parsing
    try:
        return datetime.fromisoformat(date_str).date()
    except Exception:
        raise ValueError(f"Unable to parse date string: '{date_str}'")

def calculate_haversine_distance(origin, destination):
    """
    Calculates great-circle distance in miles between two IATA airport codes.
    """
    origin = str(origin).upper().strip()
    destination = str(destination).upper().strip()
    
    if origin not in IATA_COORDINATES or destination not in IATA_COORDINATES:
        return None
        
    lat1, lon1 = IATA_COORDINATES[origin]
    lat2, lon2 = IATA_COORDINATES[destination]
    
    # Haversine formula
    R = 3958.8  # Earth radius in miles
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
        
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def get_emission_factor(category, activity_type, target_date):
    """
    Finds the active EmissionFactorReference for a category and activity on a specific date.
    Returns the database model instance or None.
    """
    if isinstance(target_date, str):
        target_date = parse_date(target_date)
        
    # Search for an active factor in the database
    factor = EmissionFactorReference.objects.filter(
        category__iexact=category,
        activity_type__iexact=activity_type,
        valid_from__lte=target_date,
        valid_to__gte=target_date
    ).first()
    
    return factor

# Fallback default factors if db reference factors are missing (for safety/demo stability)
DEFAULT_FACTORS = {
    'Diesel': {'value': Decimal('2.68'), 'unit': 'kg CO2e/liter', 'scope': 1, 'category': 'Stationary Combustion'},
    'Natural Gas': {'value': Decimal('2.02'), 'unit': 'kg CO2e/m3', 'scope': 1, 'category': 'Stationary Combustion'},
    'Grid Electricity': {'value': Decimal('0.38'), 'unit': 'kg CO2e/kWh', 'scope': 2, 'category': 'Purchased Electricity'},
    'Flight - Short-haul': {'value': Decimal('0.24'), 'unit': 'kg CO2e/passenger-mile', 'scope': 3, 'category': 'Business Travel - Flights'},
    'Flight - Medium-haul': {'value': Decimal('0.19'), 'unit': 'kg CO2e/passenger-mile', 'scope': 3, 'category': 'Business Travel - Flights'},
    'Flight - Long-haul': {'value': Decimal('0.16'), 'unit': 'kg CO2e/passenger-mile', 'scope': 3, 'category': 'Business Travel - Flights'},
    'Hotel Stay': {'value': Decimal('28.4'), 'unit': 'kg CO2e/room-night', 'scope': 3, 'category': 'Business Travel - Hotel Stays'},
    'Ground Transport': {'value': Decimal('0.15'), 'unit': 'kg CO2e/USD spend', 'scope': 3, 'category': 'Business Travel - Ground Transport'},
}

def normalize_sap_record(raw_record):
    """
    Parses and normalizes a SAP Fuel raw record.
    """
    data = raw_record.raw_data
    
    qty_str = data.get('quantity', '0')
    try:
        original_qty = Decimal(qty_str.replace(',', ''))
    except Exception:
        original_qty = Decimal('0')

    original_unit = data.get('unit', '').strip()
    material = data.get('material_number', '').strip()
    posting_date_str = data.get('posting_date', '')
    plant = data.get('plant_code', '').strip()

    # Determine activity type based on material codes/descriptions
    # Simple prototype logic: Map material names containing 'diesel' or 'gas'
    material_lower = material.lower()
    if 'diesel' in material_lower or 'heizoel' in material_lower or '5001' in material_lower:
        activity_type = 'Diesel'
    elif 'gas' in material_lower or 'natural' in material_lower or '5002' in material_lower:
        activity_type = 'Natural Gas'
    else:
        activity_type = 'Diesel'  # Default fallback

    # Unit Normalization to standard (Liters for liquids, m3 for gases)
    unit_lower = original_unit.lower()
    normalized_qty = original_qty
    target_unit = original_unit
    
    if activity_type == 'Diesel':
        target_unit = 'Liters'
        if unit_lower in ('l', 'liter', 'liters', 'ltr', 'einheit'):
            normalized_qty = original_qty
        elif unit_lower in ('gal', 'gallon', 'gallons'):
            normalized_qty = original_qty * Decimal('3.78541')
        elif unit_lower in ('m3', 'cbm'):
            normalized_qty = original_qty * Decimal('1000')  # Convert cubic meters of diesel to liters
    elif activity_type == 'Natural Gas':
        target_unit = 'm3'
        if unit_lower in ('m3', 'cbm', 'cubic meters'):
            normalized_qty = original_qty
        elif unit_lower in ('cf', 'cubic feet', 'ft3'):
            normalized_qty = original_qty * Decimal('0.0283168')
        elif unit_lower in ('gj', 'gigajoules'):
            # Convert GJ to cubic meters of natural gas (~26.2 m3 per GJ)
            normalized_qty = original_qty * Decimal('26.2')

    post_date = parse_date(posting_date_str)
    
    # Look up factor
    factor_ref = get_emission_factor('Stationary Combustion', activity_type, post_date)
    factor_val = factor_ref.factor_value if factor_ref else DEFAULT_FACTORS[activity_type]['value']
    
    # Calculate emissions (kg CO2e = quantity * factor)
    # Then convert to metric tonnes (tCO2e = kg / 1000)
    co2e_kg = normalized_qty * factor_val
    co2e_tonnes = co2e_kg / Decimal('1000')

    # Return dictionary of attributes for the NormalizedEmissionRecord
    return [{
        'tenant': raw_record.tenant,
        'raw_record': raw_record,
        'data_source': raw_record.data_source,
        'scope': 1,
        'category': 'Stationary Combustion',
        'activity_type': f"{activity_type} Fuel Combustion",
        'original_quantity': original_qty,
        'original_unit': original_unit,
        'normalized_quantity_co2e': co2e_tonnes,
        'factor_reference': factor_ref,
        'start_date': post_date,
        'end_date': post_date,
        'facility_or_plant': plant,
    }]

def normalize_utility_record(raw_record):
    """
    Parses a utility bill record and splits non-calendar periods.
    """
    data = raw_record.raw_data
    
    qty_str = data.get('quantity_kwh', '0')
    try:
        original_qty = Decimal(qty_str.replace(',', ''))
    except Exception:
        original_qty = Decimal('0')
        
    start_date = parse_date(data.get('start_date', ''))
    end_date = parse_date(data.get('end_date', ''))
    meter_id = data.get('meter_id', '').strip()
    original_unit = 'kWh'
    
    if not start_date or not end_date or start_date >= end_date:
        # Fallback if invalid dates - create single un-split record
        post_date = start_date or date.today()
        factor_ref = get_emission_factor('Purchased Electricity', 'Grid Electricity', post_date)
        factor_val = factor_ref.factor_value if factor_ref else DEFAULT_FACTORS['Grid Electricity']['value']
        co2e_tonnes = (original_qty * factor_val) / Decimal('1000')
        
        return [{
            'tenant': raw_record.tenant,
            'raw_record': raw_record,
            'data_source': raw_record.data_source,
            'scope': 2,
            'category': 'Purchased Electricity',
            'activity_type': 'Grid Purchased Electricity',
            'original_quantity': original_qty,
            'original_unit': original_unit,
            'normalized_quantity_co2e': co2e_tonnes,
            'factor_reference': factor_ref,
            'start_date': start_date or post_date,
            'end_date': end_date or post_date,
            'facility_or_plant': meter_id,
        }]

    # Calendar Splitting Calculation
    total_days = (end_date - start_date).days + 1
    if total_days <= 0:
        total_days = 1
        
    daily_usage = original_qty / Decimal(str(total_days))
    
    # Separate the dates into billing segments by calendar month
    segments = []
    current_segment_start = start_date
    
    while current_segment_start <= end_date:
        # Find the end of the current month or the billing period end, whichever is earlier
        year, month = current_segment_start.year, current_segment_start.month
        # Last day of month
        if month == 12:
            last_day_of_month = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day_of_month = date(year, month + 1, 1) - timedelta(days=1)
            
        segment_end = min(last_day_of_month, end_date)
        segment_days = (segment_end - current_segment_start).days + 1
        
        segments.append({
            'start': current_segment_start,
            'end': segment_end,
            'days': segment_days,
            'qty': daily_usage * Decimal(str(segment_days))
        })
        
        current_segment_start = segment_end + timedelta(days=1)

    normalized_records = []
    for seg in segments:
        midpoint_date = seg['start'] + timedelta(days=seg['days'] // 2)
        factor_ref = get_emission_factor('Purchased Electricity', 'Grid Electricity', midpoint_date)
        factor_val = factor_ref.factor_value if factor_ref else DEFAULT_FACTORS['Grid Electricity']['value']
        
        co2e_tonnes = (seg['qty'] * factor_val) / Decimal('1000')
        
        normalized_records.append({
            'tenant': raw_record.tenant,
            'raw_record': raw_record,
            'data_source': raw_record.data_source,
            'scope': 2,
            'category': 'Purchased Electricity',
            'activity_type': f"Grid Electricity ({seg['start'].strftime('%b %Y')})",
            'original_quantity': seg['qty'].quantize(Decimal('0.0001')),
            'original_unit': original_unit,
            'normalized_quantity_co2e': co2e_tonnes.quantize(Decimal('0.000001')),
            'factor_reference': factor_ref,
            'start_date': seg['start'],
            'end_date': seg['end'],
            'facility_or_plant': meter_id,
        })
        
    return normalized_records

def normalize_travel_record(raw_record):
    """
    Parses a Corporate Travel record and calculates emissions for Flights, Hotels, or Ground transport.
    """
    data = raw_record.raw_data
    
    category = data.get('category', '').strip().capitalize()
    travel_date = parse_date(data.get('travel_date', '')) or date.today()
    employee = data.get('employee_id', 'Unknown Employee')
    
    spend_str = data.get('spend', '0')
    try:
        spend = Decimal(spend_str.replace(',', ''))
    except Exception:
        spend = Decimal('0')

    # Default output structure
    norm_data = {
        'tenant': raw_record.tenant,
        'raw_record': raw_record,
        'data_source': raw_record.data_source,
        'scope': 3,
        'start_date': travel_date,
        'end_date': travel_date,
        'facility_or_plant': f"Employee: {employee}",
    }

    if 'flight' in category.lower() or 'air' in category.lower():
        # Flight Emission Logic
        origin = data.get('origin', '').strip().upper()
        destination = data.get('destination', '').strip().upper()
        
        dist_str = data.get('distance_miles', '0')
        try:
            distance = Decimal(dist_str.replace(',', ''))
        except Exception:
            distance = Decimal('0')
            
        if distance == 0 and origin and destination:
            # Fallback to IATA coordinate lookup
            dist_calc = calculate_haversine_distance(origin, destination)
            if dist_calc:
                distance = Decimal(str(dist_calc))

        # Classify flight distance for DEFRA factor
        if distance < 300:
            flight_tier = 'Flight - Short-haul'
        elif distance <= 2300:
            flight_tier = 'Flight - Medium-haul'
        else:
            flight_tier = 'Flight - Long-haul'
            
        factor_ref = get_emission_factor('Business Travel - Flights', flight_tier, travel_date)
        factor_val = factor_ref.factor_value if factor_ref else DEFAULT_FACTORS[flight_tier]['value']
        
        co2e_tonnes = (distance * factor_val) / Decimal('1000')
        
        norm_data.update({
            'category': 'Business Travel - Flights',
            'activity_type': f"Air Travel ({origin} -> {destination}) - {flight_tier}",
            'original_quantity': distance.quantize(Decimal('0.01')),
            'original_unit': 'Miles',
            'normalized_quantity_co2e': co2e_tonnes.quantize(Decimal('0.000001')),
            'factor_reference': factor_ref,
        })

    elif 'hotel' in category.lower() or 'stay' in category.lower() or 'lodging' in category.lower():
        # Hotel stay logic
        nights_str = data.get('hotel_nights', '0')
        try:
            nights = Decimal(nights_str.replace(',', ''))
        except Exception:
            nights = Decimal('0')
            
        factor_ref = get_emission_factor('Business Travel - Hotel Stays', 'Hotel Stay', travel_date)
        factor_val = factor_ref.factor_value if factor_ref else DEFAULT_FACTORS['Hotel Stay']['value']
        
        co2e_tonnes = (nights * factor_val) / Decimal('1000')
        
        norm_data.update({
            'category': 'Business Travel - Hotel Stays',
            'activity_type': f"Hotel Lodging ({nights} nights)",
            'original_quantity': nights,
            'original_unit': 'Nights',
            'normalized_quantity_co2e': co2e_tonnes.quantize(Decimal('0.000001')),
            'factor_reference': factor_ref,
        })
        # If there are nights, end_date = start_date + nights
        if nights > 0:
            norm_data['end_date'] = travel_date + timedelta(days=int(nights))

    else:
        # Ground Transport (Train, Taxi, Car Rental) or fallback spend-based emissions
        # Using spent-based conversion
        factor_ref = get_emission_factor('Business Travel - Ground Transport', 'Ground Transport', travel_date)
        factor_val = factor_ref.factor_value if factor_ref else DEFAULT_FACTORS['Ground Transport']['value']
        
        # Spend-based calculation (Spend * factor_val)
        co2e_tonnes = (spend * factor_val) / Decimal('1000')
        
        norm_data.update({
            'category': 'Business Travel - Ground Transport',
            'activity_type': f"Ground Transport ({category})",
            'original_quantity': spend.quantize(Decimal('0.02')),
            'original_unit': 'USD Spend',
            'normalized_quantity_co2e': co2e_tonnes.quantize(Decimal('0.000001')),
            'factor_reference': factor_ref,
        })

    return [norm_data]

def normalize_and_save_record(raw_record):
    """
    Takes a raw record, processes it through standard normalizer mapping,
    creates the NormalizedEmissionRecord object, and returns list of created record instances.
    """
    source_type = raw_record.data_source.source_type
    
    try:
        if source_type == 'SAP_FUEL':
            records_data = normalize_sap_record(raw_record)
        elif source_type == 'UTILITY_ELECTRICITY':
            records_data = normalize_utility_record(raw_record)
        elif source_type == 'CORPORATE_TRAVEL':
            records_data = normalize_travel_record(raw_record)
        else:
            raise ValueError(f"Unknown data source type: {source_type}")
            
        created_records = []
        for r_data in records_data:
            # Create Normalized Emission Record
            norm_rec = NormalizedEmissionRecord(**r_data)
            norm_rec.save()
            created_records.append(norm_rec)
            
        # Update raw record status
        raw_record.import_status = 'NORMALIZED'
        raw_record.save()
        
        return created_records

    except Exception as e:
        # If parsing or normalization fails, log the errors on the RawRecord
        raw_record.import_status = 'FAILED_VALIDATION'
        existing_errs = raw_record.errors or []
        existing_errs.append(f"Normalization Error: {str(e)}")
        raw_record.errors = existing_errs
        raw_record.save()
        return []
