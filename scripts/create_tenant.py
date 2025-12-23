#!/usr/bin/env python3
"""
Create a new tenant in the multi-tenant system.

This script creates a tenant with encrypted CRM credentials and generates
a unique API key for tenant-specific API access.

Usage:
    # Gorgias tenant
    python scripts/create_tenant.py \
        --slug quiltco1 \
        --name "Quilt Company 1" \
        --crm-provider gorgias \
        --gorgias-domain quiltco \
        --gorgias-username support@quiltco.com \
        --gorgias-api-key "your-gorgias-api-key"

    # Zendesk tenant
    python scripts/create_tenant.py \
        --slug fabricshop \
        --name "Fabric Shop" \
        --crm-provider zendesk \
        --zendesk-subdomain fabricshop \
        --zendesk-email support@fabricshop.com \
        --zendesk-token "your-zendesk-token"

    # From JSON config file
    python scripts/create_tenant.py \
        --slug quiltco1 \
        --name "Quilt Company 1" \
        --crm-provider gorgias \
        --config-file tenant_config.json

    # With store_id for data migration
    python scripts/create_tenant.py \
        --slug quiltco1 \
        --name "Quilt Company 1" \
        --store-id "store_123" \
        --crm-provider gorgias \
        --gorgias-domain quiltco \
        --gorgias-username support@quiltco.com \
        --gorgias-api-key "key"
"""
import asyncio
import json
import sys
import os
import secrets
import hashlib
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.database import get_db_session
from backend.models.tenant import Tenant
from backend.core.encryption import encrypt_config, is_encryption_configured, generate_encryption_key
from sqlalchemy import insert


async def create_tenant(
    slug: str,
    name: str,
    crm_provider: str,
    crm_config: dict,
    webhook_identifiers: dict = None,
    store_id: str = None,
    environment: str = "production"
):
    """
    Create a new tenant with encrypted CRM configuration.

    Args:
        slug: URL-safe tenant identifier (e.g., "quiltco1")
        name: Human-readable tenant name
        crm_provider: CRM provider name (gorgias, zendesk, salesforce, etc.)
        crm_config: CRM-specific configuration (will be encrypted)
        webhook_identifiers: Identifiers for webhook routing (auto-generated if None)
        store_id: Legacy store ID for data migration (optional)
        environment: production, staging, or development

    Returns:
        Tuple of (tenant_id, api_key)
    """
    # Validate encryption is configured
    if not is_encryption_configured():
        print("❌ Error: ENCRYPTION_KEY environment variable not set")
        print("\nGenerate a new key with:")
        print(f"  export ENCRYPTION_KEY={generate_encryption_key()}")
        sys.exit(1)

    # VALIDATE CRM CREDENTIALS before storing
    print(f"\n🔍 Validating {crm_provider.upper()} credentials...")
    try:
        from integrations.ticketing.factory import TicketingSystemFactory

        # Create CRM integration instance
        integration = TicketingSystemFactory.create(crm_provider, crm_config)

        # Test connection
        is_valid = await integration.test_connection()

        if not is_valid:
            print(f"\n❌ Error: Invalid {crm_provider.upper()} credentials")
            print("   Connection test failed. Please verify:")
            if crm_provider == "gorgias":
                print("   - Domain is correct (e.g., 'quiltco' not 'quiltco.gorgias.com')")
                print("   - Username (email) is correct")
                print("   - API key is valid and has proper permissions")
            elif crm_provider == "zendesk":
                print("   - Subdomain is correct (e.g., 'fabricshop' not 'fabricshop.zendesk.com')")
                print("   - Email is correct")
                print("   - API token is valid and active")
            sys.exit(1)

        print(f"✅ {crm_provider.upper()} credentials validated successfully")

    except ImportError as e:
        print(f"\n⚠️  Warning: Could not import CRM integration module: {e}")
        print("   Skipping credential validation. Ensure CRM integration is working before use.")
    except Exception as e:
        print(f"\n❌ Error validating {crm_provider.upper()} credentials: {e}")
        print("   Please check your configuration and try again.")
        sys.exit(1)

    # Generate API key for tenant
    api_key = secrets.token_urlsafe(32)
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Encrypt CRM config
    try:
        crm_config_encrypted = encrypt_config(crm_config)
    except Exception as e:
        print(f"❌ Error encrypting CRM config: {e}")
        sys.exit(1)

    # Auto-generate webhook identifiers if not provided
    if not webhook_identifiers:
        webhook_identifiers = _auto_generate_webhook_identifiers(crm_provider, crm_config)

    async with get_db_session() as db:
        # Check if slug already exists
        existing = await Tenant.get_by_slug(db, slug)
        if existing:
            print(f"❌ Error: Tenant with slug '{slug}' already exists")
            sys.exit(1)

        # Create tenant
        stmt = insert(Tenant).values(
            slug=slug,
            name=name,
            store_id=store_id,
            crm_provider=crm_provider,
            crm_config=crm_config_encrypted,
            webhook_identifiers=webhook_identifiers or {},
            api_key_hash=api_key_hash,
            environment=environment,
            is_active=True
        ).returning(Tenant.id)

        result = await db.execute(stmt)
        tenant_id = result.scalar_one()
        await db.commit()

        # Print success message
        print("\n" + "="*70)
        print("✅ Tenant created successfully!")
        print("="*70)
        print(f"\n📋 Tenant Details:")
        print(f"   ID:           {tenant_id}")
        print(f"   Slug:         {slug}")
        print(f"   Name:         {name}")
        print(f"   CRM Provider: {crm_provider}")
        print(f"   Environment:  {environment}")
        if store_id:
            print(f"   Store ID:     {store_id}")

        print(f"\n🔑 API Key (save this - it won't be shown again!):")
        print(f"   {api_key}")

        print(f"\n🔗 Access URLs:")
        print(f"   Subdomain:    https://{slug}.quimbi.app")
        print(f"   API Endpoint: https://quimbi.app/api (with X-API-Key header)")

        if crm_provider == "gorgias":
            print(f"\n📡 Gorgias Webhook URL:")
            print(f"   https://quimbi.app/api/webhooks/gorgias")
            print(f"   or: https://quimbi.app/api/gorgias/webhook")
        elif crm_provider == "zendesk":
            print(f"\n📡 Zendesk Webhook URL:")
            print(f"   https://quimbi.app/api/webhooks/zendesk")
        elif crm_provider == "salesforce":
            print(f"\n📡 Salesforce Webhook URL:")
            print(f"   https://quimbi.app/api/webhooks/salesforce")

        print(f"\n💾 Save these to your password manager:")
        print(f"   Tenant Slug: {slug}")
        print(f"   API Key: {api_key}")

        print("\n" + "="*70)

        return tenant_id, api_key


def _auto_generate_webhook_identifiers(provider: str, config: dict) -> dict:
    """
    Auto-generate webhook identifiers based on CRM config.

    Args:
        provider: CRM provider name
        config: CRM configuration

    Returns:
        Dictionary of webhook identifiers
    """
    if provider == "gorgias":
        return {"gorgias_domain": config.get("domain")}

    elif provider == "zendesk":
        return {"zendesk_subdomain": config.get("subdomain")}

    elif provider == "salesforce":
        # Salesforce org ID usually needs to be added manually
        return {}

    elif provider == "helpshift":
        return {"helpshift_app_id": config.get("app_id")}

    elif provider == "intercom":
        return {"intercom_workspace_id": config.get("workspace_id")}

    elif provider == "freshdesk":
        return {"freshdesk_domain": config.get("domain")}

    return {}


def _parse_gorgias_args(args) -> dict:
    """Parse Gorgias-specific arguments into config dict."""
    config = {}

    if args.gorgias_domain:
        config["domain"] = args.gorgias_domain
    if args.gorgias_username:
        config["username"] = args.gorgias_username
    if args.gorgias_api_key:
        config["api_key"] = args.gorgias_api_key

    # Generate or use provided webhook secret
    if args.webhook_secret:
        config["webhook_secret"] = args.webhook_secret
    else:
        # Auto-generate webhook secret
        webhook_secret = secrets.token_urlsafe(32)
        config["webhook_secret"] = webhook_secret
        print(f"\n🔐 Generated webhook secret for Gorgias:")
        print(f"   {webhook_secret}")
        print(f"\n⚠️  Configure this in your Gorgias webhook settings:")
        print(f"   1. Go to Gorgias Settings → HTTP Integrations")
        print(f"   2. Create/Edit webhook")
        print(f"   3. Set Secret: {webhook_secret}")

    # Validate required fields
    required = ["domain", "username", "api_key", "webhook_secret"]
    missing = [f for f in required if f not in config]
    if missing:
        print(f"❌ Error: Missing required Gorgias fields: {', '.join(missing)}")
        print("\nRequired arguments:")
        print("  --gorgias-domain <domain>")
        print("  --gorgias-username <email>")
        print("  --gorgias-api-key <key>")
        print("  --webhook-secret <secret> (optional, auto-generated if not provided)")
        sys.exit(1)

    return config


def _parse_zendesk_args(args) -> dict:
    """Parse Zendesk-specific arguments into config dict."""
    config = {}

    if args.zendesk_subdomain:
        config["subdomain"] = args.zendesk_subdomain
    if args.zendesk_email:
        config["email"] = args.zendesk_email
    if args.zendesk_token:
        config["token"] = args.zendesk_token

    # Generate or use provided webhook secret
    if args.webhook_secret:
        config["webhook_secret"] = args.webhook_secret
    else:
        # Auto-generate webhook secret
        webhook_secret = secrets.token_urlsafe(32)
        config["webhook_secret"] = webhook_secret
        print(f"\n🔐 Generated webhook secret for Zendesk:")
        print(f"   {webhook_secret}")
        print(f"\n⚠️  Configure this in your Zendesk webhook settings:")
        print(f"   1. Go to Admin → Extensions → Webhooks")
        print(f"   2. Create/Edit webhook")
        print(f"   3. Set Signing Secret: {webhook_secret}")

    # Validate required fields
    required = ["subdomain", "email", "token", "webhook_secret"]
    missing = [f for f in required if f not in config]
    if missing:
        print(f"❌ Error: Missing required Zendesk fields: {', '.join(missing)}")
        print("\nRequired arguments:")
        print("  --zendesk-subdomain <subdomain>")
        print("  --zendesk-email <email>")
        print("  --zendesk-token <token>")
        print("  --webhook-secret <secret> (optional, auto-generated if not provided)")
        sys.exit(1)

    return config


def main():
    parser = argparse.ArgumentParser(
        description="Create a new tenant with CRM configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Required arguments
    parser.add_argument("--slug", required=True,
                       help="URL-safe tenant identifier (e.g., quiltco1)")
    parser.add_argument("--name", required=True,
                       help="Human-readable tenant name")
    parser.add_argument("--crm-provider", required=True,
                       choices=["gorgias", "zendesk", "salesforce", "helpshift", "intercom", "freshdesk"],
                       help="CRM provider")

    # Optional arguments
    parser.add_argument("--store-id",
                       help="Legacy store ID for data migration")
    parser.add_argument("--environment", default="production",
                       choices=["production", "staging", "development"],
                       help="Environment (default: production)")
    parser.add_argument("--config-file",
                       help="JSON file with CRM configuration")
    parser.add_argument("--webhook-secret",
                       help="Webhook secret for signature verification (auto-generated if not provided)")

    # Gorgias-specific arguments
    parser.add_argument("--gorgias-domain",
                       help="Gorgias domain (e.g., quiltco)")
    parser.add_argument("--gorgias-username",
                       help="Gorgias username (email)")
    parser.add_argument("--gorgias-api-key",
                       help="Gorgias API key")

    # Zendesk-specific arguments
    parser.add_argument("--zendesk-subdomain",
                       help="Zendesk subdomain")
    parser.add_argument("--zendesk-email",
                       help="Zendesk agent email")
    parser.add_argument("--zendesk-token",
                       help="Zendesk API token")

    args = parser.parse_args()

    # Parse CRM config
    if args.config_file:
        # Load from JSON file
        try:
            with open(args.config_file, 'r') as f:
                crm_config = json.load(f)
        except Exception as e:
            print(f"❌ Error reading config file: {e}")
            sys.exit(1)

    else:
        # Parse from command-line arguments
        if args.crm_provider == "gorgias":
            crm_config = _parse_gorgias_args(args)

        elif args.crm_provider == "zendesk":
            crm_config = _parse_zendesk_args(args)

        else:
            print(f"❌ Error: --config-file required for {args.crm_provider}")
            print(f"\nCreate a JSON file with CRM configuration:")
            print(f"  {{")
            print(f"    \"domain\": \"...\",")
            print(f"    \"api_key\": \"...\"")
            print(f"  }}")
            sys.exit(1)

    # Create tenant
    asyncio.run(create_tenant(
        slug=args.slug,
        name=args.name,
        crm_provider=args.crm_provider,
        crm_config=crm_config,
        store_id=args.store_id,
        environment=args.environment
    ))


if __name__ == "__main__":
    main()
