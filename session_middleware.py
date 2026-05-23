from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

PROTECTED_PATHS = ["/admin", "/employees", "/attendance-admin"]
PUBLIC_PATHS    = ["/login", "/static", "/api", "/favicon.ico"]  # Fixed: .icon → .ico


class AuthMiddleware(BaseHTTPMiddleware):   #This runs before every request hits your route 
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Always allow public paths through
        if any(path.startswith(p) for p in PUBLIC_PATHS):
            return await call_next(request)

        # Protect admin paths — redirect to login if no session
        if any(path.startswith(p) for p in PROTECTED_PATHS):
            admin_id = request.session.get("admin_id") if hasattr(request, "session") else None
            if not admin_id:
                return RedirectResponse(url="/login", status_code=302)

        return await call_next(request)
    
    