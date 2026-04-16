"""HTTP helpers for FAIR Genomes RDF and GraphQL integrations."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def build_graphql_headers(api_token: str | None) -> dict[str, str]:
    headers: dict[str, str] = {'Content-Type': 'application/json'}
    if api_token:
        headers['x-molgenis-token'] = api_token
    return headers


def detect_rdf_format(response: requests.Response) -> str:
    """Detect the RDF serialisation format from Content-Type or body sniffing."""
    content_type = response.headers.get('Content-Type', '')
    if 'turtle' in content_type or content_type.startswith('text/plain'):
        return 'turtle'
    if 'rdf+xml' in content_type or 'application/xml' in content_type:
        return 'xml'
    if 'n-triples' in content_type:
        return 'nt'
    if 'json' in content_type:
        return 'json-ld'

    snippet = response.text.strip()[:60]
    if snippet.startswith('@prefix') or snippet.startswith('@base'):
        return 'turtle'
    if snippet.startswith('<?xml') or '<rdf:RDF' in snippet:
        return 'xml'
    return 'turtle'


def fetch_rdf(url: str, timeout: tuple[int, int] | int) -> requests.Response:
    """Fetch RDF content with retry logic for transient failures."""
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=['GET'],
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=retry))
    session.mount('http://', HTTPAdapter(max_retries=retry))
    response = session.get(
        url,
        timeout=timeout,
        headers={'Accept': 'text/turtle, application/rdf+xml;q=0.9, */*;q=0.1'},
    )
    response.raise_for_status()
    return response


def post_graphql_json(
    url: str,
    *,
    payload: dict[str, object],
    api_token: str | None,
    timeout: tuple[int, int] | int,
) -> dict:
    response = requests.post(
        url,
        json=payload,
        headers=build_graphql_headers(api_token),
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()
