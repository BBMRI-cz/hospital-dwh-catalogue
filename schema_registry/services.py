"""
Schema Registry Service Layer
==============================

Public API for callers that need schema registry data.  All access to the
in-memory schema dict goes through ``get_schema_dict()``.

The schema data is loaded lazily from the HealthDCAT-AP git submodule
(``health_dcat_ap/``) on the first call, then cached in memory for the
lifetime of the process.

Returned dict shape::

    {
        "dct:title": {
            "prefix":      "dct",
            "local_name":  "title",
            "uri":         "http://purl.org/dc/terms/title",
            "requirement": "mandatory",
            "label":       "Title",
            "description": "A name given to the Dataset.",
        },
        ...
    }
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from django.conf import settings

from schema_registry.registry import get_registry, get_namespace_prefixes

logger = logging.getLogger(__name__)


def get_schema_dict() -> dict[str, Any]:
    """
    Return the in-memory schema dict for the configured release version.

    The version is read from ``settings.HEALTH_DCAT_VERSION`` (env var
    ``HEALTH_DCAT_VERSION``, default ``"release-6"``).

    The release directory is resolved relative to ``settings.BASE_DIR``::

        {BASE_DIR}/health_dcat_ap/public/releases/{HEALTH_DCAT_VERSION}/

    Returns an empty dict if the submodule or release directory is missing,
    or if ``rdflib`` is not installed.
    """
    version: str = getattr(settings, 'HEALTH_DCAT_VERSION', 'release-6')
    base_dir: Path = settings.BASE_DIR
    release_dir = base_dir / 'health_dcat_ap' / 'public' / 'releases' / version
    return get_registry(release_dir)


def get_context_prefixes() -> dict[str, str]:
    """
    Return the namespace prefix map parsed from the HealthDCAT-AP SHACL TTL.

    Keys are canonical prefix names (e.g. ``"dct"``), values are namespace
    base URIs.  Derived from the ``@prefix`` declarations in the TTL so the
    mapping stays in sync with whatever version of the submodule is checked out.

    Returns an empty dict if the submodule or rdflib is unavailable.
    """
    version: str = getattr(settings, 'HEALTH_DCAT_VERSION', 'release-6')
    base_dir: Path = settings.BASE_DIR
    release_dir = base_dir / 'health_dcat_ap' / 'public' / 'releases' / version
    return get_namespace_prefixes(release_dir)