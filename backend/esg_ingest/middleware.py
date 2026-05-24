import uuid
from esg_ingest.tenant_context import set_current_tenant_id

class TenantMiddleware:
    """
    Middleware that inspects request headers and parameters for tenant context.
    If 'X-Tenant-ID' is found in headers, or 'tenant_id' in GET query arguments,
    it binds this tenant to the request context.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Retrieve tenant ID from Header or query parameter
        tenant_id = request.headers.get('X-Tenant-ID') or request.GET.get('tenant_id')
        
        validated_tenant_id = None
        if tenant_id:
            try:
                # Ensure it is a valid UUID
                validated_tenant_id = uuid.UUID(str(tenant_id))
            except ValueError:
                pass  # Ignore invalid UUID values

        # Set the context variable
        set_current_tenant_id(validated_tenant_id)
        
        response = self.get_response(request)
        
        # Clean up the context to prevent leaking context to subsequent worker reuse
        set_current_tenant_id(None)
        
        return response
