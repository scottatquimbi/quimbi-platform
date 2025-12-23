#!/usr/bin/env python3
"""
Setup API Key Management System

This script sets up the database-backed API key system:
1. Creates api_keys table
2. Generates initial admin key
3. Optionally migrates from ADMIN_KEY

Usage:
    python scripts/setup_api_key_system.py --create-table
    python scripts/setup_api_key_system.py --generate-admin-key
    python scripts/setup_api_key_system.py --migrate-from-env

Author: Quimbi Platform
Date: November 13, 2025
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from backend.core.database import get_db_session
from backend.api.auth import APIKeyManager


async def create_api_keys_table():
    """Create api_keys table in database."""
    print("🔧 Creating api_keys table...")

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS api_keys (
        id SERIAL PRIMARY KEY,
        key_hash VARCHAR(255) NOT NULL UNIQUE,
        name VARCHAR(255) NOT NULL,
        scopes JSONB NOT NULL DEFAULT '["read", "write"]',
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMP NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        last_used_at TIMESTAMP,
        usage_count INTEGER DEFAULT 0,
        rate_limit_remaining INTEGER DEFAULT 1000,
        rate_limit_per_hour INTEGER DEFAULT 1000,
        rate_limit_reset_at TIMESTAMP DEFAULT NOW(),
        revoked_at TIMESTAMP,
        revocation_reason VARCHAR(255),
        created_by VARCHAR(255),
        created_for VARCHAR(255),
        notes TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active);
    CREATE INDEX IF NOT EXISTS idx_api_keys_expires_at ON api_keys(expires_at);
    CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);

    COMMENT ON TABLE api_keys IS 'API keys for authentication and authorization';
    COMMENT ON COLUMN api_keys.key_hash IS 'Bcrypt hash of API key (never store plaintext)';
    COMMENT ON COLUMN api_keys.scopes IS 'JSON array of permission scopes';
    COMMENT ON COLUMN api_keys.rate_limit_per_hour IS 'Maximum requests per hour';
    """

    async with get_db_session() as session:
        try:
            await session.execute(text(create_table_sql))
            await session.commit()
            print("✅ api_keys table created successfully")
            return True
        except Exception as e:
            print(f"❌ Error creating table: {e}")
            return False


async def generate_admin_key():
    """Generate initial admin API key."""
    print("\n🔑 Generating admin API key...")

    async with get_db_session() as session:
        try:
            plain_key, key_info = await APIKeyManager.create_api_key(
                session=session,
                name="Admin Key",
                scopes=["read", "write", "admin"],
                expires_days=365
            )

            await session.commit()

            print("\n" + "="*80)
            print("✅ ADMIN API KEY GENERATED")
            print("="*80)
            print(f"\nAPI Key: {plain_key}")
            print(f"\nKey ID: {key_info['id']}")
            print(f"Name: {key_info['name']}")
            print(f"Scopes: {', '.join(key_info['scopes'])}")
            print(f"Expires: {key_info['expires_at']}")
            print("\n⚠️  IMPORTANT: Save this key securely! It cannot be retrieved again.")
            print("="*80)

            # Save to .env.local for convenience
            env_file = Path(__file__).parent.parent / ".env.local"
            with open(env_file, "a") as f:
                f.write(f"\n# Generated {key_info['created_at']}\n")
                f.write(f"ADMIN_KEY={plain_key}\n")
            print(f"\n✅ Key also saved to {env_file}")

            return True

        except Exception as e:
            print(f"❌ Error generating key: {e}")
            return False


async def generate_client_keys():
    """Generate keys for different use cases."""
    print("\n🔑 Generating client API keys...")

    keys_to_create = [
        {
            "name": "Frontend Production",
            "scopes": ["read", "write"],
            "expires_days": 365,
            "tier": 1000
        },
        {
            "name": "Analytics Dashboard",
            "scopes": ["read"],
            "expires_days": 365,
            "tier": 100
        },
        {
            "name": "Admin Scripts",
            "scopes": ["read", "write", "admin"],
            "expires_days": 90,
            "tier": 10000
        },
        {
            "name": "Mobile App",
            "scopes": ["read", "write"],
            "expires_days": 365,
            "tier": 1000
        }
    ]

    async with get_db_session() as session:
        generated_keys = []

        for key_config in keys_to_create:
            try:
                plain_key, key_info = await APIKeyManager.create_api_key(
                    session=session,
                    name=key_config["name"],
                    scopes=key_config["scopes"],
                    expires_days=key_config["expires_days"]
                )

                # Update rate limit tier
                await session.execute(
                    text("""
                        UPDATE api_keys
                        SET
                            rate_limit_per_hour = :tier,
                            rate_limit_remaining = :tier
                        WHERE id = :key_id
                    """),
                    {"key_id": key_info["id"], "tier": key_config["tier"]}
                )

                generated_keys.append({
                    "name": key_config["name"],
                    "key": plain_key,
                    "scopes": key_config["scopes"],
                    "tier": key_config["tier"]
                })

                print(f"✅ Generated: {key_config['name']}")

            except Exception as e:
                print(f"❌ Error generating {key_config['name']}: {e}")

        await session.commit()

        # Print summary
        print("\n" + "="*80)
        print("✅ CLIENT API KEYS GENERATED")
        print("="*80)

        for key in generated_keys:
            print(f"\n{key['name']}:")
            print(f"  Key: {key['key']}")
            print(f"  Scopes: {', '.join(key['scopes'])}")
            print(f"  Rate Limit: {key['tier']} req/hour")

        print("\n⚠️  IMPORTANT: Save these keys securely! They cannot be retrieved again.")
        print("="*80)

        # Save to file
        keys_file = Path(__file__).parent.parent / "api_keys_generated.txt"
        with open(keys_file, "w") as f:
            f.write("QUIMBI API KEYS - CONFIDENTIAL\n")
            f.write("="*80 + "\n")
            f.write(f"Generated: {key_info['created_at']}\n\n")

            for key in generated_keys:
                f.write(f"{key['name']}:\n")
                f.write(f"  Key: {key['key']}\n")
                f.write(f"  Scopes: {', '.join(key['scopes'])}\n")
                f.write(f"  Rate Limit: {key['tier']} req/hour\n\n")

        print(f"\n✅ Keys saved to {keys_file}")
        print("⚠️  Remember to delete this file after distributing keys!")

        return True


async def list_api_keys():
    """List all API keys (for verification)."""
    print("\n📋 Current API Keys:")

    async with get_db_session() as session:
        result = await session.execute(
            text("""
                SELECT id, name, scopes, created_at, expires_at, is_active, usage_count, last_used_at
                FROM api_keys
                ORDER BY created_at DESC
            """)
        )

        rows = result.fetchall()

        if not rows:
            print("  (No keys found)")
            return

        print("\n" + "="*80)
        for row in rows:
            status = "✅ Active" if row[5] else "❌ Revoked"
            print(f"\nID: {row[0]} | {status}")
            print(f"Name: {row[1]}")
            print(f"Scopes: {row[2]}")
            print(f"Created: {row[3]}")
            print(f"Expires: {row[4]}")
            print(f"Usage: {row[6]} requests")
            print(f"Last Used: {row[7] or 'Never'}")
        print("="*80)


async def verify_table_exists():
    """Check if api_keys table exists."""
    async with get_db_session() as session:
        try:
            result = await session.execute(
                text("SELECT COUNT(*) FROM api_keys")
            )
            count = result.scalar()
            print(f"✅ api_keys table exists ({count} keys)")
            return True
        except Exception:
            print("❌ api_keys table does not exist")
            return False


async def main():
    """Main setup workflow."""
    import argparse

    parser = argparse.ArgumentParser(description="Setup API Key Management System")
    parser.add_argument("--create-table", action="store_true", help="Create api_keys table")
    parser.add_argument("--generate-admin", action="store_true", help="Generate admin key")
    parser.add_argument("--generate-clients", action="store_true", help="Generate client keys")
    parser.add_argument("--list", action="store_true", help="List all keys")
    parser.add_argument("--full-setup", action="store_true", help="Complete setup (table + keys)")

    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        return

    print("\n🚀 Quimbi API Key Management Setup")
    print("="*80)

    # Check current state
    table_exists = await verify_table_exists()

    if args.create_table or args.full_setup:
        if table_exists:
            print("\n⚠️  Table already exists. Skipping creation.")
        else:
            success = await create_api_keys_table()
            if not success:
                print("\n❌ Setup failed. Exiting.")
                return

    if args.generate_admin or args.full_setup:
        if not table_exists and not (args.create_table or args.full_setup):
            print("\n❌ Table doesn't exist. Run with --create-table first.")
            return
        await generate_admin_key()

    if args.generate_clients:
        if not table_exists:
            print("\n❌ Table doesn't exist. Run with --create-table first.")
            return
        await generate_client_keys()

    if args.list:
        await list_api_keys()

    print("\n✅ Setup complete!")


if __name__ == "__main__":
    asyncio.run(main())
