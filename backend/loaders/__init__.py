"""Data loaders for populating MCP server data store."""
from .star_schema_loader import (
    load_customers_from_star_schema,
    load_archetypes_from_star_schema,
    load_all_data_from_star_schema
)

__all__ = [
    'load_customers_from_star_schema',
    'load_archetypes_from_star_schema',
    'load_all_data_from_star_schema'
]
