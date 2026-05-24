import contextvars
import uuid
import contextlib

# Use contextvars for thread-safe and async-safe tenant ID context tracking
_current_tenant_id = contextvars.ContextVar('current_tenant_id', default=None)

def get_current_tenant_id():
    """
    Get the UUID string or UUID object of the current active tenant, if set.
    """
    return _current_tenant_id.get()

def set_current_tenant_id(tenant_id):
    """
    Set the active tenant ID in the current execution context.
    Accepts string, UUID, or None.
    """
    if tenant_id is not None and not isinstance(tenant_id, uuid.UUID):
        try:
            tenant_id = uuid.UUID(str(tenant_id))
        except ValueError:
            pass  # Keep as string or invalid if it can't parse, though it should be UUID
    return _current_tenant_id.set(tenant_id)

@contextlib.contextmanager
def tenant_context(tenant_id):
    """
    Context manager to temporarily override or set the current tenant context.
    Usage:
        with tenant_context(tenant_uuid):
            # operations here are restricted to tenant_uuid
            qs = NormalizedEmissionRecord.objects.all()
    """
    token = set_current_tenant_id(tenant_id)
    try:
        yield
    finally:
        _current_tenant_id.reset(token)
