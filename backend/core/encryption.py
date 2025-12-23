"""
Encryption utilities for securing sensitive tenant data.

Uses Fernet (symmetric encryption) for encrypting CRM credentials,
API keys, and other sensitive configuration.

Environment Variables:
    ENCRYPTION_KEY: 32-byte Fernet key (base64 encoded)

Generate a key with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


def get_cipher() -> Fernet:
    """
    Get encryption cipher from environment.

    Returns:
        Fernet cipher instance

    Raises:
        ValueError: If ENCRYPTION_KEY is not set
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError(
            "ENCRYPTION_KEY environment variable not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    try:
        return Fernet(key.encode())
    except Exception as e:
        raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")


def encrypt_config(config: Dict[str, Any]) -> str:
    """
    Encrypt CRM configuration for database storage.

    Args:
        config: Plain configuration dictionary

    Returns:
        Encrypted JSON string (base64 encoded)

    Example:
        >>> config = {"domain": "example", "api_key": "secret123"}
        >>> encrypted = encrypt_config(config)
        >>> # Store encrypted in database
    """
    cipher = get_cipher()
    json_str = json.dumps(config)
    encrypted_bytes = cipher.encrypt(json_str.encode())
    return encrypted_bytes.decode()


def decrypt_config(encrypted_config: str) -> Dict[str, Any]:
    """
    Decrypt CRM configuration from database.

    Args:
        encrypted_config: Encrypted JSON string

    Returns:
        Decrypted configuration dictionary

    Raises:
        ValueError: If decryption fails (invalid key or corrupted data)

    Example:
        >>> encrypted = "gAAAAABh..."
        >>> config = decrypt_config(encrypted)
        >>> print(config["api_key"])
    """
    cipher = get_cipher()

    try:
        decrypted_bytes = cipher.decrypt(encrypted_config.encode())
        json_str = decrypted_bytes.decode()
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Failed to decrypt config: {e}")
        raise ValueError(f"Decryption failed: {e}")


def encrypt_field(value: str) -> str:
    """
    Encrypt a single string field.

    Args:
        value: Plain string value

    Returns:
        Encrypted string (base64 encoded)

    Example:
        >>> api_key = "sk_live_12345"
        >>> encrypted = encrypt_field(api_key)
    """
    cipher = get_cipher()
    encrypted_bytes = cipher.encrypt(value.encode())
    return encrypted_bytes.decode()


def decrypt_field(encrypted_value: str) -> str:
    """
    Decrypt a single string field.

    Args:
        encrypted_value: Encrypted string

    Returns:
        Decrypted string

    Raises:
        ValueError: If decryption fails
    """
    cipher = get_cipher()

    try:
        decrypted_bytes = cipher.decrypt(encrypted_value.encode())
        return decrypted_bytes.decode()
    except Exception as e:
        logger.error(f"Failed to decrypt field: {e}")
        raise ValueError(f"Decryption failed: {e}")


def is_encryption_configured() -> bool:
    """
    Check if encryption is properly configured.

    Returns:
        True if ENCRYPTION_KEY is set and valid, False otherwise
    """
    try:
        get_cipher()
        return True
    except ValueError:
        return False


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.

    Returns:
        Base64-encoded encryption key (44 characters)

    Example:
        >>> key = generate_encryption_key()
        >>> print(f"ENCRYPTION_KEY={key}")
    """
    return Fernet.generate_key().decode()


# Test encryption on module import (only in development)
if __name__ == "__main__":
    print("Testing encryption module...")

    if not is_encryption_configured():
        print("❌ ENCRYPTION_KEY not set")
        print("Generate key with:")
        print(f"  export ENCRYPTION_KEY={generate_encryption_key()}")
    else:
        print("✅ Encryption configured")

        # Test config encryption
        test_config = {
            "domain": "test",
            "api_key": "secret123",
            "username": "admin@test.com"
        }

        encrypted = encrypt_config(test_config)
        print(f"Encrypted: {encrypted[:50]}...")

        decrypted = decrypt_config(encrypted)
        assert decrypted == test_config
        print("✅ Config encryption/decryption works")

        # Test field encryption
        test_field = "my_secret_value"
        encrypted_field = encrypt_field(test_field)
        decrypted_field = decrypt_field(encrypted_field)
        assert decrypted_field == test_field
        print("✅ Field encryption/decryption works")
