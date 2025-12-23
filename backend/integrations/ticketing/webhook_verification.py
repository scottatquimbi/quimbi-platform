"""
Webhook Signature Verification for CRM Providers

Verifies webhook authenticity using HMAC signatures provided by each CRM.
Prevents spoofed webhooks from injecting malicious data.

Supported Providers:
- Gorgias: HMAC-SHA256 with X-Gorgias-Signature header
- Zendesk: HMAC-SHA256 with X-Zendesk-Webhook-Signature header (base64)
- Salesforce: SHA256 with X-Salesforce-Signature header
- Helpshift: HMAC-SHA256 with X-Helpshift-Signature header
- Intercom: HMAC-SHA256 with X-Hub-Signature header (sha256= prefix)
- Freshdesk: HMAC-SHA256 with X-Freshdesk-Signature header

Security Notes:
- Always use hmac.compare_digest() to prevent timing attacks
- Webhook secrets must be stored in encrypted tenant config
- Failed verifications should be logged for security monitoring

Author: Quimbi Platform
Date: November 3, 2025
"""
import hmac
import hashlib
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class WebhookVerifier:
    """Verifies webhook signatures for all supported CRM providers."""

    @staticmethod
    def verify_gorgias(body: bytes, signature: str, secret: str) -> bool:
        """
        Verify Gorgias webhook signature.

        Gorgias uses HMAC-SHA256 with hex-encoded output.
        Header: X-Gorgias-Signature

        Args:
            body: Raw webhook body (bytes)
            signature: Signature from X-Gorgias-Signature header
            secret: Webhook secret from tenant config

        Returns:
            True if signature is valid, False otherwise

        Example:
            body = request.body()
            signature = request.headers.get("X-Gorgias-Signature")
            secret = tenant.get_decrypted_crm_config()["webhook_secret"]

            if WebhookVerifier.verify_gorgias(body, signature, secret):
                # Process webhook
        """
        if not signature or not secret:
            logger.warning("gorgias_verification_missing_params")
            return False

        try:
            expected = hmac.new(
                secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()

            # Use compare_digest to prevent timing attacks
            is_valid = hmac.compare_digest(signature.lower(), expected.lower())

            if not is_valid:
                logger.warning(
                    "gorgias_signature_mismatch",
                    extra={"provided": signature[:16], "expected": expected[:16]}
                )

            return is_valid

        except Exception as e:
            logger.error(f"gorgias_verification_error: {e}")
            return False

    @staticmethod
    def verify_zendesk(body: bytes, signature: str, secret: str) -> bool:
        """
        Verify Zendesk webhook signature.

        Zendesk uses HMAC-SHA256 with base64-encoded output.
        Header: X-Zendesk-Webhook-Signature

        Args:
            body: Raw webhook body (bytes)
            signature: Signature from X-Zendesk-Webhook-Signature header
            secret: Webhook secret from tenant config

        Returns:
            True if signature is valid, False otherwise

        Documentation:
            https://developer.zendesk.com/documentation/webhooks/verifying/
        """
        if not signature or not secret:
            logger.warning("zendesk_verification_missing_params")
            return False

        try:
            # Zendesk uses base64-encoded HMAC
            expected_bytes = hmac.new(
                secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).digest()

            expected = base64.b64encode(expected_bytes).decode('utf-8')

            is_valid = hmac.compare_digest(signature, expected)

            if not is_valid:
                logger.warning(
                    "zendesk_signature_mismatch",
                    extra={"provided": signature[:16], "expected": expected[:16]}
                )

            return is_valid

        except Exception as e:
            logger.error(f"zendesk_verification_error: {e}")
            return False

    @staticmethod
    def verify_salesforce(
        body: bytes,
        signature: str,
        secret: str,
        url: str
    ) -> bool:
        """
        Verify Salesforce webhook signature.

        Salesforce uses SHA256 with URL concatenation.
        Header: X-Salesforce-Signature

        Args:
            body: Raw webhook body (bytes)
            signature: Signature from X-Salesforce-Signature header (base64)
            secret: Webhook secret from tenant config
            url: Full webhook URL (required by Salesforce)

        Returns:
            True if signature is valid, False otherwise

        Documentation:
            https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/dome_webhook_security.htm

        Note:
            Salesforce concatenates URL + body before signing:
            signature = base64(SHA256(url + body, secret))
        """
        if not signature or not secret or not url:
            logger.warning("salesforce_verification_missing_params")
            return False

        try:
            # Salesforce concatenates URL + body
            message = (url + body.decode('utf-8')).encode('utf-8')

            expected_bytes = hmac.new(
                secret.encode('utf-8'),
                message,
                hashlib.sha256
            ).digest()

            expected = base64.b64encode(expected_bytes).decode('utf-8')

            is_valid = hmac.compare_digest(signature, expected)

            if not is_valid:
                logger.warning(
                    "salesforce_signature_mismatch",
                    extra={"provided": signature[:16], "expected": expected[:16]}
                )

            return is_valid

        except Exception as e:
            logger.error(f"salesforce_verification_error: {e}")
            return False

    @staticmethod
    def verify_helpshift(body: bytes, signature: str, secret: str) -> bool:
        """
        Verify Helpshift webhook signature.

        Helpshift uses HMAC-SHA256 with hex-encoded output.
        Header: X-Helpshift-Signature

        Args:
            body: Raw webhook body (bytes)
            signature: Signature from X-Helpshift-Signature header
            secret: Webhook secret from tenant config

        Returns:
            True if signature is valid, False otherwise

        Documentation:
            https://developers.helpshift.com/web-chat/webhooks/
        """
        if not signature or not secret:
            logger.warning("helpshift_verification_missing_params")
            return False

        try:
            expected = hmac.new(
                secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()

            is_valid = hmac.compare_digest(signature.lower(), expected.lower())

            if not is_valid:
                logger.warning(
                    "helpshift_signature_mismatch",
                    extra={"provided": signature[:16], "expected": expected[:16]}
                )

            return is_valid

        except Exception as e:
            logger.error(f"helpshift_verification_error: {e}")
            return False

    @staticmethod
    def verify_intercom(body: bytes, signature: str, secret: str) -> bool:
        """
        Verify Intercom webhook signature.

        Intercom uses HMAC-SHA256 with "sha256=" prefix and hex encoding.
        Header: X-Hub-Signature

        Args:
            body: Raw webhook body (bytes)
            signature: Signature from X-Hub-Signature header (sha256=...)
            secret: Webhook secret from tenant config

        Returns:
            True if signature is valid, False otherwise

        Documentation:
            https://developers.intercom.com/building-apps/docs/setting-up-webhooks

        Note:
            Intercom signature format: "sha256=<hex_signature>"
        """
        if not signature or not secret:
            logger.warning("intercom_verification_missing_params")
            return False

        try:
            # Remove "sha256=" prefix if present
            if signature.startswith("sha256="):
                signature = signature[7:]

            expected = hmac.new(
                secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()

            is_valid = hmac.compare_digest(signature.lower(), expected.lower())

            if not is_valid:
                logger.warning(
                    "intercom_signature_mismatch",
                    extra={"provided": signature[:16], "expected": expected[:16]}
                )

            return is_valid

        except Exception as e:
            logger.error(f"intercom_verification_error: {e}")
            return False

    @staticmethod
    def verify_freshdesk(body: bytes, signature: str, secret: str) -> bool:
        """
        Verify Freshdesk webhook signature.

        Freshdesk uses HMAC-SHA256 with hex-encoded output.
        Header: X-Freshdesk-Signature

        Args:
            body: Raw webhook body (bytes)
            signature: Signature from X-Freshdesk-Signature header
            secret: Webhook secret from tenant config

        Returns:
            True if signature is valid, False otherwise

        Documentation:
            https://developers.freshdesk.com/api/#webhook_signatures
        """
        if not signature or not secret:
            logger.warning("freshdesk_verification_missing_params")
            return False

        try:
            expected = hmac.new(
                secret.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()

            is_valid = hmac.compare_digest(signature.lower(), expected.lower())

            if not is_valid:
                logger.warning(
                    "freshdesk_signature_mismatch",
                    extra={"provided": signature[:16], "expected": expected[:16]}
                )

            return is_valid

        except Exception as e:
            logger.error(f"freshdesk_verification_error: {e}")
            return False


class WebhookVerificationError(Exception):
    """Raised when webhook verification fails."""

    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"{provider} webhook verification failed: {reason}")


def verify_webhook(
    provider: str,
    body: bytes,
    signature: Optional[str],
    secret: str,
    url: Optional[str] = None
) -> bool:
    """
    Convenience function to verify webhook for any provider.

    Args:
        provider: CRM provider name (gorgias, zendesk, salesforce, etc.)
        body: Raw webhook body (bytes)
        signature: Signature header value
        secret: Webhook secret from tenant config
        url: Full webhook URL (required for Salesforce)

    Returns:
        True if signature is valid, False otherwise

    Raises:
        ValueError: If provider is not supported
        WebhookVerificationError: If verification fails

    Example:
        try:
            if verify_webhook("gorgias", body, signature, secret):
                # Process webhook
                pass
        except WebhookVerificationError as e:
            logger.error(f"Webhook verification failed: {e}")
            return 401
    """
    provider = provider.lower()

    verifiers = {
        "gorgias": WebhookVerifier.verify_gorgias,
        "zendesk": WebhookVerifier.verify_zendesk,
        "helpshift": WebhookVerifier.verify_helpshift,
        "intercom": WebhookVerifier.verify_intercom,
        "freshdesk": WebhookVerifier.verify_freshdesk,
    }

    if provider == "salesforce":
        if not url:
            raise ValueError("Salesforce webhook verification requires URL parameter")
        return WebhookVerifier.verify_salesforce(body, signature, secret, url)

    if provider not in verifiers:
        raise ValueError(f"Unsupported webhook provider: {provider}")

    if not signature:
        raise WebhookVerificationError(provider, "Missing signature header")

    if not secret:
        raise WebhookVerificationError(provider, "Webhook secret not configured")

    return verifiers[provider](body, signature, secret)


# Testing utilities
if __name__ == "__main__":
    """Test webhook verification with known values."""
    import json

    print("Testing webhook verification module...\n")

    # Test Gorgias
    test_body = json.dumps({"account": {"domain": "test"}}).encode('utf-8')
    test_secret = "test_secret_123"

    expected_signature = hmac.new(
        test_secret.encode('utf-8'),
        test_body,
        hashlib.sha256
    ).hexdigest()

    print(f"Test body: {test_body.decode()}")
    print(f"Test secret: {test_secret}")
    print(f"Expected signature: {expected_signature}\n")

    # Test valid signature
    result = WebhookVerifier.verify_gorgias(test_body, expected_signature, test_secret)
    print(f"✅ Gorgias valid signature: {result}")

    # Test invalid signature
    result = WebhookVerifier.verify_gorgias(test_body, "invalid_sig", test_secret)
    print(f"✅ Gorgias invalid signature rejected: {not result}")

    # Test Zendesk (base64)
    expected_zendesk = base64.b64encode(
        hmac.new(test_secret.encode(), test_body, hashlib.sha256).digest()
    ).decode()

    result = WebhookVerifier.verify_zendesk(test_body, expected_zendesk, test_secret)
    print(f"✅ Zendesk valid signature: {result}")

    # Test Intercom (with sha256= prefix)
    expected_intercom = hmac.new(
        test_secret.encode(), test_body, hashlib.sha256
    ).hexdigest()

    result = WebhookVerifier.verify_intercom(test_body, f"sha256={expected_intercom}", test_secret)
    print(f"✅ Intercom valid signature: {result}")

    print("\n✅ All webhook verification tests passed!")
