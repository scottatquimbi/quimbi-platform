"""
Ticketing System Factory

Factory pattern for creating ticketing system instances based on configuration.
Supports multiple ticketing providers (Zendesk, Gorgias, etc.)
"""
import os
import logging
from typing import Optional, Dict, Any
from enum import Enum

from .base_ticketing import TicketingSystem
from .zendesk import ZendeskIntegration
from .gorgias import GorgiasIntegration

logger = logging.getLogger(__name__)


class TicketingProvider(str, Enum):
    """Supported ticketing providers"""
    ZENDESK = "zendesk"
    GORGIAS = "gorgias"


class TicketingSystemFactory:
    """
    Factory for creating ticketing system instances.

    Usage:
        # From environment variables
        ticketing = TicketingSystemFactory.create_from_env()

        # From explicit config
        ticketing = TicketingSystemFactory.create(
            provider="zendesk",
            config={
                "subdomain": "yourcompany",
                "email": "agent@company.com",
                "token": "your-api-token"
            }
        )
    """

    @staticmethod
    def create(
        provider: str,
        config: Dict[str, Any]
    ) -> TicketingSystem:
        """
        Create a ticketing system instance.

        Args:
            provider: Provider name ("zendesk" or "gorgias")
            config: Provider-specific configuration

        Returns:
            TicketingSystem instance

        Raises:
            ValueError: If provider is unknown or config is invalid
        """
        provider = provider.lower()

        if provider == TicketingProvider.ZENDESK:
            return TicketingSystemFactory._create_zendesk(config)
        elif provider == TicketingProvider.GORGIAS:
            return TicketingSystemFactory._create_gorgias(config)
        else:
            raise ValueError(
                f"Unknown ticketing provider: {provider}. "
                f"Supported providers: {[p.value for p in TicketingProvider]}"
            )

    @staticmethod
    def create_from_env() -> Optional[TicketingSystem]:
        """
        Create ticketing system from environment variables.

        Environment Variables:
            TICKETING_PROVIDER: "zendesk" or "gorgias"

            For Zendesk:
                ZENDESK_SUBDOMAIN: Zendesk subdomain
                ZENDESK_EMAIL: Agent email
                ZENDESK_TOKEN: API token

            For Gorgias:
                GORGIAS_DOMAIN: Gorgias domain
                GORGIAS_USERNAME: Account email
                GORGIAS_API_KEY: API key

        Returns:
            TicketingSystem instance or None if not configured

        Example:
            export TICKETING_PROVIDER=zendesk
            export ZENDESK_SUBDOMAIN=yourcompany
            export ZENDESK_EMAIL=agent@company.com
            export ZENDESK_TOKEN=your-token
        """
        provider = os.getenv("TICKETING_PROVIDER", "").lower()

        if not provider:
            logger.warning("TICKETING_PROVIDER not set, ticketing features disabled")
            return None

        try:
            if provider == TicketingProvider.ZENDESK:
                config = {
                    "subdomain": os.getenv("ZENDESK_SUBDOMAIN"),
                    "email": os.getenv("ZENDESK_EMAIL"),
                    "token": os.getenv("ZENDESK_TOKEN")
                }
                return TicketingSystemFactory._create_zendesk(config)

            elif provider == TicketingProvider.GORGIAS:
                config = {
                    "domain": os.getenv("GORGIAS_DOMAIN"),
                    "username": os.getenv("GORGIAS_USERNAME"),
                    "api_key": os.getenv("GORGIAS_API_KEY")
                }
                return TicketingSystemFactory._create_gorgias(config)

            else:
                logger.error(f"Unknown ticketing provider: {provider}")
                return None

        except ValueError as e:
            logger.error(f"Failed to create ticketing system: {e}")
            return None

    @staticmethod
    def _create_zendesk(config: Dict[str, Any]) -> ZendeskIntegration:
        """
        Create Zendesk integration instance.

        Args:
            config: Configuration with subdomain, email, token

        Returns:
            ZendeskIntegration instance

        Raises:
            ValueError: If required config is missing
        """
        required_fields = ["subdomain", "email", "token"]
        missing = [f for f in required_fields if not config.get(f)]

        if missing:
            raise ValueError(
                f"Missing required Zendesk configuration: {', '.join(missing)}"
            )

        logger.info(f"Creating Zendesk integration for {config['subdomain']}")

        return ZendeskIntegration(
            subdomain=config["subdomain"],
            email=config["email"],
            token=config["token"]
        )

    @staticmethod
    def _create_gorgias(config: Dict[str, Any]) -> GorgiasIntegration:
        """
        Create Gorgias integration instance.

        Args:
            config: Configuration with domain, username, api_key

        Returns:
            GorgiasIntegration instance

        Raises:
            ValueError: If required config is missing
        """
        required_fields = ["domain", "username", "api_key"]
        missing = [f for f in required_fields if not config.get(f)]

        if missing:
            raise ValueError(
                f"Missing required Gorgias configuration: {', '.join(missing)}"
            )

        logger.info(f"Creating Gorgias integration for {config['domain']}")

        return GorgiasIntegration(
            domain=config["domain"],
            username=config["username"],
            api_key=config["api_key"]
        )


# Convenience function
def create_ticketing_system(
    provider: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Optional[TicketingSystem]:
    """
    Convenience function to create ticketing system.

    Args:
        provider: Provider name (optional, reads from env if not provided)
        config: Configuration dict (optional, reads from env if not provided)

    Returns:
        TicketingSystem instance or None

    Usage:
        # From environment
        ticketing = create_ticketing_system()

        # Explicit provider and config
        ticketing = create_ticketing_system(
            provider="zendesk",
            config={"subdomain": "...", "email": "...", "token": "..."}
        )
    """
    if provider and config:
        return TicketingSystemFactory.create(provider, config)
    else:
        return TicketingSystemFactory.create_from_env()
