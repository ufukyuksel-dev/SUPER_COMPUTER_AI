"""Practical bulk-collection tool for training-data-engineering.

Credentials are read from environment variables named in sources.yaml
(`auth_env`); they are never written to config, logs, or provenance.
"""

from .run import collect
from .dedup import cross_split_check

__all__ = ["collect", "cross_split_check"]
