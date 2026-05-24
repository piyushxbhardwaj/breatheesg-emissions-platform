import uuid
from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from esg_ingest.models import Tenant, EmissionFactorReference

class Command(BaseCommand):
    help = "Seeds database with default Tenants and standard EmissionFactorReferences (EPA, DEFRA)."

    def handle(self, *args, **options):
        self.stdout.write("Seeding Tenants...")
        
        # Consistent UUIDs for prototype switching stability
        tenants_data = [
            {"id": uuid.UUID("11111111-1111-1111-1111-111111111111"), "name": "Acme Industrial Group"},
            {"id": uuid.UUID("22222222-2222-2222-2222-222222222222"), "name": "Apex Global Logistics"},
        ]

        tenants = []
        for t_info in tenants_data:
            t, created = Tenant.objects.get_or_create(id=t_info["id"], defaults={"name": t_info["name"]})
            if created:
                self.stdout.write(f"  Created tenant: {t_info['name']}")
            else:
                self.stdout.write(f"  Tenant exists: {t_info['name']}")
            tenants.append(t)

        self.stdout.write("Seeding Emission Factor References...")
        
        factors_data = [
            # Scope 1: Fuel combustion (Liquids in Liters, Gases in cubic meters)
            {
                "category": "Stationary Combustion",
                "activity_type": "Diesel",
                "source_name": "EPA 2023",
                "factor_value": Decimal("2.68"),
                "unit": "kg CO2e/liter",
                "valid_from": date(2023, 1, 1),
                "valid_to": date(2026, 12, 31)
            },
            {
                "category": "Stationary Combustion",
                "activity_type": "Natural Gas",
                "source_name": "EPA 2023",
                "factor_value": Decimal("2.02"),
                "unit": "kg CO2e/m3",
                "valid_from": date(2023, 1, 1),
                "valid_to": date(2026, 12, 31)
            },
            # Scope 2: Grid Purchased Electricity (kWh)
            {
                "category": "Purchased Electricity",
                "activity_type": "Grid Electricity",
                "source_name": "DEFRA 2023",
                "factor_value": Decimal("0.385"),
                "unit": "kg CO2e/kWh",
                "valid_from": date(2023, 1, 1),
                "valid_to": date(2026, 12, 31)
            },
            # Scope 3: Air Travel passenger-miles
            {
                "category": "Business Travel - Flights",
                "activity_type": "Flight - Short-haul",
                "source_name": "DEFRA 2023",
                "factor_value": Decimal("0.244"),
                "unit": "kg CO2e/passenger-mile",
                "valid_from": date(2023, 1, 1),
                "valid_to": date(2026, 12, 31)
            },
            {
                "category": "Business Travel - Flights",
                "activity_type": "Flight - Medium-haul",
                "source_name": "DEFRA 2023",
                "factor_value": Decimal("0.192"),
                "unit": "kg CO2e/passenger-mile",
                "valid_from": date(2023, 1, 1),
                "valid_to": date(2026, 12, 31)
            },
            {
                "category": "Business Travel - Flights",
                "activity_type": "Flight - Long-haul",
                "source_name": "DEFRA 2023",
                "factor_value": Decimal("0.165"),
                "unit": "kg CO2e/passenger-mile",
                "valid_from": date(2023, 1, 1),
                "valid_to": date(2026, 12, 31)
            },
            # Scope 3: Hotels room-nights
            {
                "category": "Business Travel - Hotel Stays",
                "activity_type": "Hotel Stay",
                "source_name": "DEFRA 2023",
                "factor_value": Decimal("28.42"),
                "unit": "kg CO2e/room-night",
                "valid_from": date(2023, 1, 1),
                "valid_to": date(2026, 12, 31)
            },
            # Scope 3: Ground transport (taxi/train spend-based conversions)
            {
                "category": "Business Travel - Ground Transport",
                "activity_type": "Ground Transport",
                "source_name": "DEFRA 2023",
                "factor_value": Decimal("0.155"),
                "unit": "kg CO2e/USD spend",
                "valid_from": date(2023, 1, 1),
                "valid_to": date(2026, 12, 31)
            }
        ]

        for f_info in factors_data:
            f, created = EmissionFactorReference.objects.get_or_create(
                category=f_info["category"],
                activity_type=f_info["activity_type"],
                source_name=f_info["source_name"],
                valid_from=f_info["valid_from"],
                valid_to=f_info["valid_to"],
                defaults={
                    "factor_value": f_info["factor_value"],
                    "unit": f_info["unit"]
                }
            )
            if created:
                self.stdout.write(f"  Created factor: {f_info['activity_type']} ({f_info['source_name']})")
            else:
                # Update factor value just in case
                f.factor_value = f_info["factor_value"]
                f.unit = f_info["unit"]
                f.save()
                self.stdout.write(f"  Updated factor: {f_info['activity_type']} ({f_info['source_name']})")

        self.stdout.write(self.style.SUCCESS("Database seeded successfully!"))
