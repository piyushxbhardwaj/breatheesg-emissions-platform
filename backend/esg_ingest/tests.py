import uuid
from decimal import Decimal
from datetime import date
from django.test import TestCase

from esg_ingest.models import Tenant, DataSource, RawRecord, NormalizedEmissionRecord, ReviewAction, EmissionFactorReference
from esg_ingest.tenant_context import set_current_tenant_id, tenant_context
from esg_ingest.services.ingestion import process_file_upload
from esg_ingest.services.normalizer import calculate_haversine_distance, get_emission_factor


class MultiTenancyIsolationTestCase(TestCase):
    def setUp(self):
        # Create Tenants
        self.tenant_a = Tenant.objects.create(name="Company A")
        self.tenant_b = Tenant.objects.create(name="Company B")

        # Create Emission Factor
        self.factor = EmissionFactorReference.objects.create(
            category="Stationary Combustion",
            activity_type="Diesel",
            source_name="EPA 2023",
            factor_value=Decimal("2.68"),
            unit="kg CO2e/liter",
            valid_from=date(2023, 1, 1),
            valid_to=date(2025, 12, 31)
        )

        # Create DataSources for A and B
        # Bypass thread-local context restriction by explicitly assigning tenant
        self.source_a = DataSource.objects.create(
            tenant=self.tenant_a,
            source_type="SAP_FUEL",
            file_name="sap_a.csv",
            file_hash="hash_a",
            status="COMPLETED"
        )
        self.source_b = DataSource.objects.create(
            tenant=self.tenant_b,
            source_type="SAP_FUEL",
            file_name="sap_b.csv",
            file_hash="hash_b",
            status="COMPLETED"
        )

        # Create Normalized Records
        self.record_a = NormalizedEmissionRecord.objects.create(
            tenant=self.tenant_a,
            data_source=self.source_a,
            scope=1,
            category="Stationary Combustion",
            activity_type="Diesel",
            original_quantity=Decimal("1000"),
            original_unit="Liters",
            normalized_quantity_co2e=Decimal("2.68"),
            start_date=date(2023, 6, 1),
            end_date=date(2023, 6, 1),
            facility_or_plant="Plant A"
        )
        self.record_b = NormalizedEmissionRecord.objects.create(
            tenant=self.tenant_b,
            data_source=self.source_b,
            scope=1,
            category="Stationary Combustion",
            activity_type="Diesel",
            original_quantity=Decimal("500"),
            original_unit="Liters",
            normalized_quantity_co2e=Decimal("1.34"),
            start_date=date(2023, 6, 1),
            end_date=date(2023, 6, 1),
            facility_or_plant="Plant B"
        )

    def test_tenant_context_filtering(self):
        """
        Verify that setting the active tenant restricts queries via TenantScopedManager.
        """
        # Set tenant A context
        set_current_tenant_id(self.tenant_a.id)
        
        # Verify query only fetches A
        sources = DataSource.objects.all()
        self.assertEqual(sources.count(), 1)
        self.assertEqual(sources.first().file_name, "sap_a.csv")

        records = NormalizedEmissionRecord.objects.all()
        self.assertEqual(records.count(), 1)
        self.assertEqual(records.first().facility_or_plant, "Plant A")

        # Set tenant B context
        set_current_tenant_id(self.tenant_b.id)
        
        # Verify query only fetches B
        sources = DataSource.objects.all()
        self.assertEqual(sources.count(), 1)
        self.assertEqual(sources.first().file_name, "sap_b.csv")

        # Reset context and verify global_objects manager can see all
        set_current_tenant_id(None)
        all_records = NormalizedEmissionRecord.global_objects.all()
        self.assertEqual(all_records.count(), 2)

    def test_context_manager_override(self):
        """
        Verify that the tenant_context context manager operates correctly.
        """
        with tenant_context(self.tenant_a.id):
            self.assertEqual(NormalizedEmissionRecord.objects.count(), 1)
            self.assertEqual(NormalizedEmissionRecord.objects.first().facility_or_plant, "Plant A")

        with tenant_context(self.tenant_b.id):
            self.assertEqual(NormalizedEmissionRecord.objects.count(), 1)
            self.assertEqual(NormalizedEmissionRecord.objects.first().facility_or_plant, "Plant B")


class IngestionPipelineTestCase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Corporate Tenant")
        
        # Seed factor references
        EmissionFactorReference.objects.create(
            category="Stationary Combustion",
            activity_type="Diesel",
            source_name="EPA 2023",
            factor_value=Decimal("2.68"),  # kg CO2e/liter
            unit="kg CO2e/liter",
            valid_from=date(2023, 1, 1),
            valid_to=date(2025, 12, 31)
        )
        
        EmissionFactorReference.objects.create(
            category="Purchased Electricity",
            activity_type="Grid Electricity",
            source_name="DEFRA 2023",
            factor_value=Decimal("0.38"),  # kg CO2e/kWh
            unit="kg CO2e/kWh",
            valid_from=date(2023, 1, 1),
            valid_to=date(2025, 12, 31)
        )

    def test_sap_fuel_procurement_parsing(self):
        """
        Verify SAP fuel files with German column headers parse, map, and normalize.
        """
        sap_csv = (
            "Materialnummer,Menge,Einheit,Werk,Buchungsdatum\n"
            "Mat-Diesel-100,2000,Liters,Plant-81,2023-05-15\n"
        ).encode('utf-8')

        with tenant_context(self.tenant.id):
            source = process_file_upload(
                tenant=self.tenant,
                file_name="sap_export.csv",
                file_bytes=sap_csv,
                source_type="SAP_FUEL",
                uploaded_by="Analyst A"
            )

            # Check status
            self.assertEqual(source.status, "COMPLETED")
            self.assertEqual(source.row_count, 1)

            # Check RawRecord created
            raw_records = RawRecord.objects.filter(data_source=source)
            self.assertEqual(raw_records.count(), 1)
            self.assertEqual(raw_records.first().raw_data['material_number'], "Mat-Diesel-100")

            # Check Normalized Record
            norm_records = NormalizedEmissionRecord.objects.filter(data_source=source)
            self.assertEqual(norm_records.count(), 1)
            
            rec = norm_records.first()
            self.assertEqual(rec.scope, 1)
            self.assertEqual(rec.original_quantity, Decimal("2000"))
            # 2000 liters * 2.68 kg CO2e/l = 5360 kg = 5.36 tonnes CO2e
            self.assertEqual(rec.normalized_quantity_co2e, Decimal("5.360000"))

    def test_utility_calendar_split(self):
        """
        Verify utility billing periods spanning calendar months split into monthly records.
        """
        # Nov 15 to Dec 14 billing cycle (30 days total)
        # Nov: 16 days (15th to 30th)
        # Dec: 14 days (1st to 14th)
        # 3000 kWh total consumption
        utility_csv = (
            "Meter ID,Billing Start,Billing End,kWh Consumption,Tariff Rate,Total Cost\n"
            "Meter-402,2023-11-15,2023-12-14,3000,0.12,360\n"
        ).encode('utf-8')

        with tenant_context(self.tenant.id):
            source = process_file_upload(
                tenant=self.tenant,
                file_name="utility_bill.csv",
                file_bytes=utility_csv,
                source_type="UTILITY_ELECTRICITY",
                uploaded_by="Analyst A"
            )

            self.assertEqual(source.status, "COMPLETED")

            # Verify that two split records are created
            norm_records = NormalizedEmissionRecord.objects.filter(data_source=source).order_by('start_date')
            self.assertEqual(norm_records.count(), 2)

            # Segment 1 (November)
            nov_rec = norm_records[0]
            self.assertEqual(nov_rec.start_date, date(2023, 11, 15))
            self.assertEqual(nov_rec.end_date, date(2023, 11, 30))
            # 3000 kWh * (16 / 30) = 1600 kWh
            self.assertEqual(nov_rec.original_quantity, Decimal("1600.0000"))
            # 1600 kWh * 0.38 kg = 608 kg = 0.608 tonnes CO2e
            self.assertEqual(nov_rec.normalized_quantity_co2e, Decimal("0.608000"))

            # Segment 2 (December)
            dec_rec = norm_records[1]
            self.assertEqual(dec_rec.start_date, date(2023, 12, 1))
            self.assertEqual(dec_rec.end_date, date(2023, 12, 14))
            # 3000 kWh * (14 / 30) = 1400 kWh
            self.assertEqual(dec_rec.original_quantity, Decimal("1400.0000"))
            # 1400 kWh * 0.38 kg = 532 kg = 0.532 tonnes CO2e
            self.assertEqual(dec_rec.normalized_quantity_co2e, Decimal("0.532000"))

    def test_haversine_distance_lookup(self):
        """
        Verify distance calculations between JFK and LHR using Haversine formula.
        """
        dist = calculate_haversine_distance('JFK', 'LHR')
        self.assertIsNotNone(dist)
        self.assertTrue(3400 < dist < 3500)


class AuditTrailTestCase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Audit Test Co")
        self.source = DataSource.objects.create(
            tenant=self.tenant,
            source_type="SAP_FUEL",
            file_name="test.csv",
            file_hash="test_hash"
        )
        self.record = NormalizedEmissionRecord.objects.create(
            tenant=self.tenant,
            data_source=self.source,
            scope=1,
            category="Stationary Combustion",
            activity_type="Diesel",
            original_quantity=Decimal("100"),
            original_unit="Liters",
            normalized_quantity_co2e=Decimal("0.268"),
            start_date=date(2023, 6, 1),
            end_date=date(2023, 6, 1),
            facility_or_plant="Plant A"
        )

    def test_approval_locks_record(self):
        """
        Verify that approving locks the record from editing.
        """
        self.assertFalse(self.record.is_locked)
        self.record.review_status = 'APPROVED'
        self.record.is_locked = True
        self.record.save()

        # Check serializer constraint
        from esg_ingest.serializers import NormalizedEmissionRecordSerializer
        serializer = NormalizedEmissionRecordSerializer(self.record, data={'original_quantity': 200}, partial=True)
        # Validation error must be raised since record is locked
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)
