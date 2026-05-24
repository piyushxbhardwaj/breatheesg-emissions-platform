from esg_ingest.tenant_context import get_current_tenant_id

def tenant_context_processor(request):
    """
    Exposes the current tenant ID to templates.
    """
    return {
        'current_tenant_id': get_current_tenant_id()
    }
