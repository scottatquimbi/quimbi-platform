"""
Tenant Routing Middleware

Identifies and sets the current tenant for each request based on:
1. Subdomain (e.g., quiltco1.quimbi.app)
2. API key header (X-API-Key)
3. Webhook source (Gorgias domain, Zendesk subdomain, etc.)

The tenant context is automatically cleared after each request.

Security features:
- Rate limiting: 100/minute, 1000/hour per IP
- Webhook signature verification for all CRM providers
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response, JSONResponse
from typing import Optional
import hashlib
import logging
import json
import time
from collections import defaultdict

from backend.middleware.tenant_context import set_current_tenant_id, clear_tenant_context
from backend.models.tenant import Tenant
from backend.core.database import get_db_session
from backend.integrations.ticketing.webhook_verification import WebhookVerifier

logger = logging.getLogger(__name__)


# Simple in-memory rate limiter for tenant identification attempts
class TenantIdentificationRateLimiter:
    """
    Rate limiter for tenant identification to prevent enumeration and DoS.

    Limits:
    - 100 requests per minute per IP address
    - 1000 requests per hour per IP address
    """

    def __init__(self):
        self.minute_buckets = defaultdict(list)  # IP -> [timestamps]
        self.hour_buckets = defaultdict(list)
        self.cleanup_interval = 60  # Cleanup every minute
        self.last_cleanup = time.time()

    def is_allowed(self, ip_address: str) -> tuple[bool, Optional[str]]:
        """
        Check if request from IP is allowed.

        Returns:
            (is_allowed, retry_after_message)
        """
        now = time.time()

        # Periodic cleanup
        if now - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries()

        # Get timestamps for this IP
        minute_timestamps = self.minute_buckets[ip_address]
        hour_timestamps = self.hour_buckets[ip_address]

        # Remove timestamps older than 1 minute and 1 hour
        one_minute_ago = now - 60
        one_hour_ago = now - 3600

        self.minute_buckets[ip_address] = [ts for ts in minute_timestamps if ts > one_minute_ago]
        self.hour_buckets[ip_address] = [ts for ts in hour_timestamps if ts > one_hour_ago]

        # Check limits
        minute_count = len(self.minute_buckets[ip_address])
        hour_count = len(self.hour_buckets[ip_address])

        if minute_count >= 100:
            return False, "Rate limit exceeded: 100 requests per minute. Try again in 60 seconds."

        if hour_count >= 1000:
            return False, "Rate limit exceeded: 1000 requests per hour. Try again later."

        # Record this request
        self.minute_buckets[ip_address].append(now)
        self.hour_buckets[ip_address].append(now)

        return True, None

    def _cleanup_old_entries(self):
        """Remove IPs with no recent requests."""
        now = time.time()
        one_hour_ago = now - 3600

        # Clean minute buckets
        ips_to_remove = [
            ip for ip, timestamps in self.minute_buckets.items()
            if not timestamps or all(ts < one_hour_ago for ts in timestamps)
        ]
        for ip in ips_to_remove:
            del self.minute_buckets[ip]
            if ip in self.hour_buckets:
                del self.hour_buckets[ip]

        self.last_cleanup = now

        logger.debug(f"Rate limiter cleanup: removed {len(ips_to_remove)} IPs")


# Global rate limiter instance
rate_limiter = TenantIdentificationRateLimiter()


class TenantRoutingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to identify and set current tenant from request.

    Tenant identification strategies (in order):
    1. Subdomain routing (quiltco1.quimbi.app)
    2. API key header (X-API-Key)
    3. Webhook routing (Gorgias domain, Zendesk subdomain, etc.)

    Public endpoints bypass tenant requirement:
    - /health, /metrics, /docs, /openapi.json
    """

    # Endpoints that don't require tenant identification
    PUBLIC_PATHS = {
        "/health",
        "/api/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        """
        Process request and identify tenant.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response from handler

        Raises:
            HTTPException: If tenant cannot be identified or rate limit exceeded
        """
        # Skip tenant routing for public endpoints
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # RATE LIMITING: Check if IP is allowed
        client_ip = request.client.host if request.client else "unknown"
        is_allowed, error_message = rate_limiter.is_allowed(client_ip)

        if not is_allowed:
            logger.warning(
                "tenant_routing_rate_limit_exceeded",
                extra={
                    "ip": client_ip,
                    "path": request.url.path,
                    "user_agent": request.headers.get("user-agent", "")
                }
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": error_message
                },
                headers={"Retry-After": "60"}
            )

        tenant_id = None

        try:
            async with get_db_session() as db:
                # Strategy 1: Subdomain routing
                tenant_id = await self._identify_by_subdomain(request, db)

                # Strategy 2: API key header
                if not tenant_id:
                    tenant_id = await self._identify_by_api_key(request, db)

                # Strategy 3: Webhook routing
                if not tenant_id:
                    tenant_id = await self._identify_by_webhook(request, db)

                # If no tenant found, allow request but log warning
                # This maintains backward compatibility with single-tenant mode
                if not tenant_id:
                    logger.info(
                        "tenant_not_identified_allowing_request",
                        extra={
                            "path": request.url.path,
                            "host": request.headers.get("host"),
                            "has_api_key": "X-API-Key" in request.headers,
                            "note": "Running in backward-compatible single-tenant mode"
                        }
                    )
                    # Don't set tenant context - routes will use default/global behavior
                    response = await call_next(request)
                    return response

                # Set tenant context for this request
                set_current_tenant_id(tenant_id)

                logger.info(
                    "tenant_identified",
                    extra={
                        "tenant_id": str(tenant_id),
                        "path": request.url.path
                    }
                )

            # Process request with tenant context
            response = await call_next(request)
            return response

        except HTTPException:
            # Re-raise HTTP exceptions
            raise

        except Exception as e:
            logger.error(
                "tenant_routing_error",
                extra={"error": str(e), "path": request.url.path},
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error during tenant routing"
            )

        finally:
            # Always clear tenant context after request
            clear_tenant_context()

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public and doesn't require tenant."""
        return path in self.PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc")

    async def _identify_by_subdomain(
        self,
        request: Request,
        db
    ) -> Optional[str]:
        """
        Identify tenant by subdomain.

        Examples:
            quiltco1.quimbi.app -> slug: quiltco1
            fabricshop.quimbi.app -> slug: fabricshop

        Args:
            request: Incoming request
            db: Database session

        Returns:
            Tenant UUID if found, None otherwise
        """
        host = request.headers.get("host", "")

        # Skip localhost and non-subdomain hosts
        if not host or "localhost" in host or host.startswith("127.0.0.1"):
            return None

        # Extract subdomain
        parts = host.split(".")
        if len(parts) < 3:  # Need at least subdomain.domain.tld
            return None

        subdomain = parts[0]

        # Skip reserved subdomains
        if subdomain in ["api", "www", "staging", "production", "admin"]:
            return None

        # Look up tenant by slug
        tenant = await Tenant.get_by_slug(db, subdomain)
        if tenant and tenant.is_active:
            logger.debug(f"Tenant identified by subdomain: {subdomain}")
            return tenant.id

        return None

    async def _identify_by_api_key(
        self,
        request: Request,
        db
    ) -> Optional[str]:
        """
        Identify tenant by API key header.

        Expects: X-API-Key: <tenant_api_key>

        Args:
            request: Incoming request
            db: Database session

        Returns:
            Tenant UUID if found, None otherwise
        """
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return None

        # Hash API key for lookup
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Look up tenant by API key hash
        tenant = await Tenant.get_by_api_key_hash(db, api_key_hash)
        if tenant and tenant.is_active:
            logger.debug(f"Tenant identified by API key: {tenant.slug}")
            return tenant.id

        return None

    async def _identify_by_webhook(
        self,
        request: Request,
        db
    ) -> Optional[str]:
        """
        Identify tenant by webhook source and verify signature.

        Different webhooks include different identifiers:
        - Gorgias: domain in webhook payload
        - Zendesk: subdomain in payload
        - Salesforce: organization ID
        - Helpshift: app ID
        - Intercom: workspace ID

        Args:
            request: Incoming request
            db: Database session

        Returns:
            Tenant UUID if found, None otherwise

        Raises:
            HTTPException: If webhook signature verification fails
        """
        path = request.url.path

        # Only process webhook endpoints
        if not path.startswith("/api/webhooks/") and path != "/api/gorgias/webhook":
            return None

        # Read webhook body
        try:
            body = await request.body()
            if not body:
                return None

            webhook_data = json.loads(body)

            # Restore body for downstream handlers
            # (FastAPI will read it again)
            async def receive():
                return {"type": "http.request", "body": body}
            request._receive = receive

        except json.JSONDecodeError:
            logger.warning("webhook_invalid_json", extra={"path": path})
            return None

        # Try to identify tenant based on webhook type
        # Now includes signature verification
        if "gorgias" in path or path == "/api/gorgias/webhook":
            return await self._identify_gorgias_webhook(webhook_data, db, request, body)

        elif "zendesk" in path:
            return await self._identify_zendesk_webhook(webhook_data, db, request, body)

        elif "salesforce" in path:
            return await self._identify_salesforce_webhook(webhook_data, db, request, body)

        elif "helpshift" in path:
            return await self._identify_helpshift_webhook(webhook_data, db, request, body)

        elif "intercom" in path:
            return await self._identify_intercom_webhook(webhook_data, db, request, body)

        return None

    async def _identify_gorgias_webhook(
        self,
        webhook_data: dict,
        db,
        request: Request,
        body: bytes
    ) -> Optional[str]:
        """
        Extract Gorgias domain from webhook payload and verify signature.

        Gorgias webhook format:
        {
            "account": {"domain": "quiltco"},
            ...
        }

        Args:
            webhook_data: Parsed webhook JSON
            db: Database session
            request: Request object (for headers)
            body: Raw webhook body for signature verification

        Returns:
            Tenant UUID if found and signature valid

        Raises:
            HTTPException: If signature verification fails
        """
        gorgias_domain = webhook_data.get("account", {}).get("domain")
        if not gorgias_domain:
            return None

        tenant = await Tenant.find_by_webhook_identifier(
            db,
            "gorgias_domain",
            gorgias_domain
        )

        if not tenant or not tenant.is_active:
            logger.warning(
                "gorgias_webhook_tenant_not_found",
                extra={"domain": gorgias_domain}
            )
            return None

        # VERIFY SIGNATURE
        signature = request.headers.get("X-Gorgias-Signature")
        if not signature:
            logger.warning(
                "gorgias_webhook_missing_signature",
                extra={"tenant_id": str(tenant.id), "domain": gorgias_domain}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Gorgias-Signature header"
            )

        # Get webhook secret from tenant config
        config = tenant.get_decrypted_crm_config()
        webhook_secret = config.get("webhook_secret")

        if not webhook_secret:
            logger.error(
                "gorgias_webhook_secret_not_configured",
                extra={"tenant_id": str(tenant.id), "domain": gorgias_domain}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook verification not configured for this tenant"
            )

        # Verify signature
        if not WebhookVerifier.verify_gorgias(body, signature, webhook_secret):
            logger.warning(
                "gorgias_webhook_invalid_signature",
                extra={"tenant_id": str(tenant.id), "domain": gorgias_domain}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )

        logger.info(
            "gorgias_webhook_verified",
            extra={"tenant_id": str(tenant.id), "domain": gorgias_domain}
        )
        return tenant.id

    async def _identify_zendesk_webhook(
        self,
        webhook_data: dict,
        db,
        request: Request,
        body: bytes
    ) -> Optional[str]:
        """
        Extract Zendesk subdomain from webhook payload and verify signature.

        Zendesk webhook format varies, but typically includes:
        {
            "account": {"subdomain": "fabricshop"},
            ...
        }
        """
        zendesk_subdomain = webhook_data.get("account", {}).get("subdomain")
        if not zendesk_subdomain:
            return None

        tenant = await Tenant.find_by_webhook_identifier(
            db,
            "zendesk_subdomain",
            zendesk_subdomain
        )

        if not tenant or not tenant.is_active:
            logger.warning(
                "zendesk_webhook_tenant_not_found",
                extra={"subdomain": zendesk_subdomain}
            )
            return None

        # VERIFY SIGNATURE
        signature = request.headers.get("X-Zendesk-Webhook-Signature")
        if not signature:
            logger.warning(
                "zendesk_webhook_missing_signature",
                extra={"tenant_id": str(tenant.id), "subdomain": zendesk_subdomain}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Zendesk-Webhook-Signature header"
            )

        config = tenant.get_decrypted_crm_config()
        webhook_secret = config.get("webhook_secret")

        if not webhook_secret:
            logger.error(
                "zendesk_webhook_secret_not_configured",
                extra={"tenant_id": str(tenant.id), "subdomain": zendesk_subdomain}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook verification not configured for this tenant"
            )

        if not WebhookVerifier.verify_zendesk(body, signature, webhook_secret):
            logger.warning(
                "zendesk_webhook_invalid_signature",
                extra={"tenant_id": str(tenant.id), "subdomain": zendesk_subdomain}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )

        logger.info(
            "zendesk_webhook_verified",
            extra={"tenant_id": str(tenant.id), "subdomain": zendesk_subdomain}
        )
        return tenant.id

    async def _identify_salesforce_webhook(
        self,
        webhook_data: dict,
        db,
        request: Request,
        body: bytes
    ) -> Optional[str]:
        """
        Extract Salesforce organization ID from webhook and verify signature.

        Salesforce outbound messages include:
        {
            "organizationId": "00D5e0000000abc",
            ...
        }
        """
        org_id = webhook_data.get("organizationId")
        if not org_id:
            return None

        tenant = await Tenant.find_by_webhook_identifier(
            db,
            "salesforce_org_id",
            org_id
        )

        if not tenant or not tenant.is_active:
            logger.warning(
                "salesforce_webhook_tenant_not_found",
                extra={"org_id": org_id}
            )
            return None

        # VERIFY SIGNATURE
        signature = request.headers.get("X-Salesforce-Signature")
        if not signature:
            logger.warning(
                "salesforce_webhook_missing_signature",
                extra={"tenant_id": str(tenant.id), "org_id": org_id}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Salesforce-Signature header"
            )

        config = tenant.get_decrypted_crm_config()
        webhook_secret = config.get("webhook_secret")

        if not webhook_secret:
            logger.error(
                "salesforce_webhook_secret_not_configured",
                extra={"tenant_id": str(tenant.id), "org_id": org_id}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook verification not configured for this tenant"
            )

        # Salesforce requires full webhook URL for verification
        webhook_url = str(request.url)

        if not WebhookVerifier.verify_salesforce(body, signature, webhook_secret, webhook_url):
            logger.warning(
                "salesforce_webhook_invalid_signature",
                extra={"tenant_id": str(tenant.id), "org_id": org_id}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )

        logger.info(
            "salesforce_webhook_verified",
            extra={"tenant_id": str(tenant.id), "org_id": org_id}
        )
        return tenant.id

    async def _identify_helpshift_webhook(
        self,
        webhook_data: dict,
        db,
        request: Request,
        body: bytes
    ) -> Optional[str]:
        """
        Extract Helpshift app ID from webhook and verify signature.

        Helpshift webhooks include:
        {
            "app_id": "quiltco_ios_123",
            ...
        }
        """
        app_id = webhook_data.get("app_id")
        if not app_id:
            return None

        tenant = await Tenant.find_by_webhook_identifier(
            db,
            "helpshift_app_id",
            app_id
        )

        if not tenant or not tenant.is_active:
            logger.warning(
                "helpshift_webhook_tenant_not_found",
                extra={"app_id": app_id}
            )
            return None

        # VERIFY SIGNATURE
        signature = request.headers.get("X-Helpshift-Signature")
        if not signature:
            logger.warning(
                "helpshift_webhook_missing_signature",
                extra={"tenant_id": str(tenant.id), "app_id": app_id}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Helpshift-Signature header"
            )

        config = tenant.get_decrypted_crm_config()
        webhook_secret = config.get("webhook_secret")

        if not webhook_secret:
            logger.error(
                "helpshift_webhook_secret_not_configured",
                extra={"tenant_id": str(tenant.id), "app_id": app_id}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook verification not configured for this tenant"
            )

        if not WebhookVerifier.verify_helpshift(body, signature, webhook_secret):
            logger.warning(
                "helpshift_webhook_invalid_signature",
                extra={"tenant_id": str(tenant.id), "app_id": app_id}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )

        logger.info(
            "helpshift_webhook_verified",
            extra={"tenant_id": str(tenant.id), "app_id": app_id}
        )
        return tenant.id

    async def _identify_intercom_webhook(
        self,
        webhook_data: dict,
        db,
        request: Request,
        body: bytes
    ) -> Optional[str]:
        """
        Extract Intercom workspace ID from webhook and verify signature.

        Intercom webhooks include:
        {
            "data": {
                "workspace_id": "abc123"
            },
            ...
        }
        """
        workspace_id = webhook_data.get("data", {}).get("workspace_id")
        if not workspace_id:
            return None

        tenant = await Tenant.find_by_webhook_identifier(
            db,
            "intercom_workspace_id",
            workspace_id
        )

        if not tenant or not tenant.is_active:
            logger.warning(
                "intercom_webhook_tenant_not_found",
                extra={"workspace_id": workspace_id}
            )
            return None

        # VERIFY SIGNATURE
        signature = request.headers.get("X-Hub-Signature")
        if not signature:
            logger.warning(
                "intercom_webhook_missing_signature",
                extra={"tenant_id": str(tenant.id), "workspace_id": workspace_id}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Hub-Signature header"
            )

        config = tenant.get_decrypted_crm_config()
        webhook_secret = config.get("webhook_secret")

        if not webhook_secret:
            logger.error(
                "intercom_webhook_secret_not_configured",
                extra={"tenant_id": str(tenant.id), "workspace_id": workspace_id}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook verification not configured for this tenant"
            )

        if not WebhookVerifier.verify_intercom(body, signature, webhook_secret):
            logger.warning(
                "intercom_webhook_invalid_signature",
                extra={"tenant_id": str(tenant.id), "workspace_id": workspace_id}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )

        logger.info(
            "intercom_webhook_verified",
            extra={"tenant_id": str(tenant.id), "workspace_id": workspace_id}
        )
        return tenant.id
