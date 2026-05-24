from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from esg_ingest.models import (
    Tenant, DataSource, RawRecord, 
    EmissionFactorReference, NormalizedEmissionRecord, ReviewAction
)
from esg_ingest.serializers import (
    TenantSerializer, DataSourceSerializer, RawRecordSerializer,
    EmissionFactorReferenceSerializer, NormalizedEmissionRecordSerializer, ReviewActionSerializer
)
from esg_ingest.services.ingestion import process_file_upload
from esg_ingest.services.validator import run_anomaly_checks
from esg_ingest.tenant_context import get_current_tenant_id


class TenantViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows tenants to be listed.
    """
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer


class DataSourceViewSet(viewsets.ModelViewSet):
    """
    Handles file upload configurations and history.
    """
    serializer_class = DataSourceSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_queryset(self):
        # Implicitly filtered by TenantScopedManager in models
        return DataSource.objects.all().order_by('-uploaded_at')

    def create(self, request, *args, **kwargs):
        """
        Receives an uploaded CSV file, checks for uniqueness/idempotency,
        and processes it through the ingestion pipeline.
        """
        tenant_id = request.data.get('tenant_id') or get_current_tenant_id()
        source_type = request.data.get('source_type')
        uploaded_by = request.data.get('uploaded_by', 'Analyst')
        
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)
            
        if not source_type:
            return Response({"error": "No source type selected."}, status=status.HTTP_400_BAD_REQUEST)

        # Get tenant object
        if not tenant_id:
            return Response({"error": "Tenant context (header or parameter) is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        tenant = get_object_or_404(Tenant, id=tenant_id)

        try:
            # Read file bytes in memory
            file_bytes = file_obj.read()
            file_name = file_obj.name

            # Process upload (will raise ValueError on duplicate hash check)
            data_source = process_file_upload(
                tenant=tenant,
                file_name=file_name,
                file_bytes=file_bytes,
                source_type=source_type,
                uploaded_by=uploaded_by
            )
            
            serializer = self.get_serializer(data_source)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except ValueError as val_err:
            # Catch idempotency block and other formatting validation exceptions
            return Response({"error": str(val_err)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Internal Ingestion Failure: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmissionFactorReferenceViewSet(viewsets.ModelViewSet):
    """
    Houses globally administered emission factors.
    """
    queryset = EmissionFactorReference.objects.all()
    serializer_class = EmissionFactorReferenceSerializer


class NormalizedEmissionRecordViewSet(viewsets.ModelViewSet):
    """
    Lists and updates normalized ESG emission metrics.
    """
    serializer_class = NormalizedEmissionRecordSerializer

    def get_queryset(self):
        # TenantScopedManager automatically restricts query scope
        queryset = NormalizedEmissionRecord.objects.all().order_by('-start_date')
        
        # Filtering parameters
        review_status = self.request.query_params.get('review_status')
        suspicious_flag = self.request.query_params.get('suspicious_flag')
        scope = self.request.query_params.get('scope')
        category = self.request.query_params.get('category')
        facility = self.request.query_params.get('facility')

        if review_status:
            queryset = queryset.filter(review_status=review_status)
        if suspicious_flag is not None:
            # Handle standard string mappings ('true' / 'false')
            flag_bool = suspicious_flag.lower() == 'true'
            queryset = queryset.filter(suspicious_flag=flag_bool)
        if scope:
            queryset = queryset.filter(scope=int(scope))
        if category:
            queryset = queryset.filter(category__icontains=category)
        if facility:
            queryset = queryset.filter(facility_or_plant__icontains=facility)

        return queryset

    def update(self, request, *args, **kwargs):
        """
        Overrides the standard update to capture detailed audit logs.
        Re-validates updated values.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        if instance.is_locked:
            return Response({"error": "Locked record cannot be updated."}, status=status.HTTP_400_BAD_REQUEST)

        # Snapshot before changes
        before_state = {
            'facility_or_plant': instance.facility_or_plant,
            'original_quantity': str(instance.original_quantity),
            'original_unit': instance.original_unit,
            'start_date': str(instance.start_date),
            'end_date': str(instance.end_date),
            'normalized_quantity_co2e': str(instance.normalized_quantity_co2e),
            'review_status': instance.review_status
        }

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # Save updates in atomic transaction
        with transaction.atomic():
            updated_instance = serializer.save()
            
            # Recalculate if values changed and factor is available
            # For this prototype: if the analyst updates the original_quantity, recompute co2e
            qty_changed = Decimal(str(updated_instance.original_quantity)) != Decimal(before_state['original_quantity'])
            if qty_changed and updated_instance.factor_reference:
                # Re-calculate co2e
                factor_val = updated_instance.factor_reference.factor_value
                co2e_kg = updated_instance.original_quantity * factor_val
                updated_instance.normalized_quantity_co2e = co2e_kg / Decimal('1000')
                updated_instance.save()

            # Re-run validation anomaly checks
            run_anomaly_checks(updated_instance)

            # Detect differences
            changes = {}
            after_state = {
                'facility_or_plant': updated_instance.facility_or_plant,
                'original_quantity': str(updated_instance.original_quantity),
                'original_unit': updated_instance.original_unit,
                'start_date': str(updated_instance.start_date),
                'end_date': str(updated_instance.end_date),
                'normalized_quantity_co2e': str(updated_instance.normalized_quantity_co2e),
                'review_status': updated_instance.review_status
            }
            
            for key, val in after_state.items():
                if val != before_state[key]:
                    changes[key] = {
                        'before': before_state[key],
                        'after': val
                    }

            # Create Audit Log
            comment = request.data.get('comment', 'Manual record adjustments')
            performed_by = request.data.get('performed_by', 'Analyst')
            
            if changes:
                ReviewAction.objects.create(
                    tenant=updated_instance.tenant,
                    record=updated_instance,
                    action_type='EDIT',
                    performed_by=performed_by,
                    changes=changes,
                    comment=comment
                )

        return Response(self.get_serializer(updated_instance).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approves and locks the specified emission record.
        """
        record = self.get_object()
        if record.is_locked:
            return Response({"error": "Record is already approved and locked."}, status=status.HTTP_400_BAD_REQUEST)
            
        comment = request.data.get('comment', 'Analyst approved record')
        performed_by = request.data.get('performed_by', 'Analyst')

        with transaction.atomic():
            record.review_status = 'APPROVED'
            record.is_locked = True
            record.save()

            ReviewAction.objects.create(
                tenant=record.tenant,
                record=record,
                action_type='APPROVE',
                performed_by=performed_by,
                comment=comment
            )

        return Response({"status": "approved", "record_id": record.id})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Rejects the specified emission record.
        """
        record = self.get_object()
        if record.is_locked:
            return Response({"error": "Approved and locked records cannot be rejected."}, status=status.HTTP_400_BAD_REQUEST)
            
        comment = request.data.get('comment', '')
        if not comment:
            return Response({"error": "Rejection requires a brief explanatory comment."}, status=status.HTTP_400_BAD_REQUEST)
            
        performed_by = request.data.get('performed_by', 'Analyst')

        with transaction.atomic():
            record.review_status = 'REJECTED'
            record.save()

            ReviewAction.objects.create(
                tenant=record.tenant,
                record=record,
                action_type='REJECT',
                performed_by=performed_by,
                comment=comment
            )

        return Response({"status": "rejected", "record_id": record.id})

    @action(detail=False, methods=['post'], url_path='bulk-approve')
    def bulk_approve(self, request):
        """
        Approves and locks multiple records in a single transaction.
        """
        record_ids = request.data.get('record_ids', [])
        comment = request.data.get('comment', 'Bulk approval by analyst')
        performed_by = request.data.get('performed_by', 'Analyst')

        if not record_ids:
            return Response({"error": "No record IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

        # Retrieve records that belong to current tenant
        records = self.get_queryset().filter(id__in=record_ids, is_locked=False)
        count = records.count()

        if count == 0:
            return Response({"error": "No unlockable records found matching the input IDs."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            for rec in records:
                rec.review_status = 'APPROVED'
                rec.is_locked = True
                rec.save()

                ReviewAction.objects.create(
                    tenant=rec.tenant,
                    record=rec,
                    action_type='APPROVE',
                    performed_by=performed_by,
                    comment=comment
                )

        return Response({"status": "success", "approved_count": count})

    @action(detail=True, methods=['get'], url_path='audit-log')
    def audit_log(self, request, pk=None):
        """
        Returns the entire change and status audit history for a single record.
        """
        record = self.get_object()
        logs = ReviewAction.objects.filter(record=record).order_by('-performed_at')
        serializer = ReviewActionSerializer(logs, many=True)
        return Response(serializer.data)
