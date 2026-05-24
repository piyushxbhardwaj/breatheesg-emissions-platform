from rest_framework import serializers
from esg_ingest.models import (
    Tenant, DataSource, RawRecord, 
    EmissionFactorReference, NormalizedEmissionRecord, ReviewAction
)

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = '__all__'


class DataSourceSerializer(serializers.ModelSerializer):
    uploaded_at_formatted = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)

    class Meta:
        model = DataSource
        fields = [
            'id', 'tenant', 'source_type', 'source_type_display', 'file_name', 
            'uploaded_at', 'uploaded_at_formatted', 'uploaded_by', 
            'status', 'status_display', 'error_message', 'row_count'
        ]
        read_only_fields = ['id', 'tenant', 'uploaded_at', 'status', 'error_message', 'row_count']

    def get_uploaded_at_formatted(self, obj):
        return obj.uploaded_at.strftime('%Y-%m-%d %H:%M:%S') if obj.uploaded_at else ""


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = '__all__'


class EmissionFactorReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactorReference
        fields = '__all__'


class NormalizedEmissionRecordSerializer(serializers.ModelSerializer):
    factor_reference_details = EmissionFactorReferenceSerializer(source='factor_reference', read_only=True)
    review_status_display = serializers.CharField(source='get_review_status_display', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    raw_data = serializers.SerializerMethodField()

    class Meta:
        model = NormalizedEmissionRecord
        fields = [
            'id', 'tenant', 'raw_record', 'raw_data', 'data_source', 'scope', 'scope_display',
            'category', 'activity_type', 'original_quantity', 'original_unit',
            'normalized_quantity_co2e', 'factor_reference', 'factor_reference_details',
            'start_date', 'end_date', 'facility_or_plant', 'review_status', 
            'review_status_display', 'suspicious_flag', 'suspicious_reasons', 
            'is_locked', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'raw_record', 'data_source', 'is_locked', 'created_at', 'updated_at']

    def get_raw_data(self, obj):
        """
        Exposes the raw record's row data so analysts can compare raw vs normalized cell-by-cell.
        """
        if obj.raw_record:
            return obj.raw_record.raw_data
        return {}

    def validate(self, data):
        """
        Prevents edits to locked/approved records.
        """
        if self.instance and self.instance.is_locked:
            raise serializers.ValidationError("This record has been approved and locked. It cannot be updated.")
        return data


class ReviewActionSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_type_display', read_only=True)
    performed_at_formatted = serializers.SerializerMethodField()

    class Meta:
        model = ReviewAction
        fields = [
            'id', 'tenant', 'record', 'action_type', 'action_display',
            'performed_by', 'performed_at', 'performed_at_formatted', 
            'changes', 'comment'
        ]
        read_only_fields = ['id', 'tenant', 'performed_at']

    def get_performed_at_formatted(self, obj):
        return obj.performed_at.strftime('%Y-%m-%d %H:%M:%S') if obj.performed_at else ""
