"""Multi-platform school providers (Pronote, ÉcoleDirecte, Skolengo)."""

from edu_mcp.providers.base import SchoolProvider
from edu_mcp.providers.ecoledirecte_provider import EcoleDirecteProvider
from edu_mcp.providers.skolengo_provider import SkolengoProvider

__all__ = ["SchoolProvider", "EcoleDirecteProvider", "SkolengoProvider"]
