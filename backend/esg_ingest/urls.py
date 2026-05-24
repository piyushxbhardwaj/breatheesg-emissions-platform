from django.urls import path, include
from rest_framework.routers import DefaultRouter
from esg_ingest.views import (
    TenantViewSet, DataSourceViewSet, 
    EmissionFactorReferenceViewSet, NormalizedEmissionRecordViewSet
)

router = DefaultRouter()
router.register(r'tenants', TenantViewSet, basename='tenant')
router.register(r'uploads', DataSourceViewSet, basename='upload')
router.register(r'factors', EmissionFactorReferenceViewSet, basename='factor')
router.register(r'records', NormalizedEmissionRecordViewSet, basename='record')

urlpatterns = [
    path('', include(router.urls)),
]
