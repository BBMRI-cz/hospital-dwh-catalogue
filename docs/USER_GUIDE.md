# User Guide

Audience: catalogue users, staff users, and teammates demoing the app.

Use this page when the app is already running and you want to know what people can do in the browser. If you need to start or deploy the stack, use [OPERATIONS.md](OPERATIONS.md).

## Before you start

You need:

- a running app
- a user account that can sign in

Authentication depends on the environment:

- `dev` accepts any non-empty username and password because `MOCK_LDAP=True`
- `staging` usually keeps LDAP mocked, but can also use real LDAP
- `prod` uses real LDAP only

The username that matches `DJANGO_SUPERUSER_USERNAME` becomes the mock staff/superuser account in `dev`.

## Main pages

| URL | Purpose |
|---|---|
| `/` | Catalogue index with search, filters, and result cards |
| `/dataset/<app>/<name>/` | Dataset detail page |
| `/distribution/<app>/<name>/` | Distribution detail page |
| `/cart/` | Access-request cart and submission form |
| `/tickets/` | Request history |
| `/api/jsonld` | Aggregate JSON-LD export for logged-in users |
| `/api/rdf` | Aggregate RDF export for logged-in users |
| `/admin/` | Django admin for staff and superusers |
| `/grafana/` | Observability UI for logged-in staff users |

## Browse the catalogue

Users sign in and land on `/`.

From there they can:

- search datasets by text
- filter by keyword, custodian, health category, source, theme, and distribution column
- open dataset and distribution detail pages
- add datasets to the request cart

## Dataset detail pages

Dataset detail pages show:

- HealthDCAT-style metadata rows
- the distributions that belong to the dataset
- dataset-level export buttons when the dataset has distributions

## Distribution detail pages

Distribution detail pages show:

- HealthDCAT-style distribution metadata
- physical warehouse tables and columns when available
- FAIR Genomes charts when stat results exist

## Export metadata

Logged-in users can download:

- `/api/jsonld`
- `/api/rdf`

These are aggregate exports built from all configured source applications.

Some dataset detail pages also expose dataset-specific export buttons.

## Request access

The request workflow is:

1. add datasets to the cart
2. open `/cart/`
3. submit a request description
4. the app stores a local `TicketRequest`
5. the app sends the request to the configured ticketing service

Request history is available at `/tickets/`.

The cart is stored in the session and holds up to 50 items.

Items are sent through the configured ticketing backend:

- mocked locally in development and isolated testing
- sent to Alvao in live-like environments

## Staff features

Staff and superusers can use `/admin/` to:

- manage users and permissions
- manage catalogue filter definitions
- manage FAIR Genomes stat definitions
- trigger FAIR Genomes synchronisation and selected-stat refresh actions
- inspect ticket requests

Staff users can also open `/grafana/`. Grafana has no separate password; access is gated by Django login plus the staff check.

## Troubleshooting

### I cannot sign in locally

Check:

- the stack was started with the `dev` environment
- `MOCK_LDAP=True` in `.env`
- you are using a non-empty username and password
- the `web` container is running

### Warehouse datasets do not appear

Check:

- `metadata_db` is reachable
- the `warehouse` tables exist in the metadata schema
- startup logs do not report `metadata_db unavailable`

### FAIR Genomes charts are empty

Check:

- `MOCK_FAIR_GENOMES` is set correctly
- FAIR Genomes synchronisation completed
- there are active `StatDefinition` rows for the distribution
- newly added statistic definitions were saved successfully, including the save-time aggregation synchronisation message
- the FAIR Genomes freshness panel in admin shows a recent successful statistics synchronisation

### Grafana is blocked

Check:

- the user is authenticated
- the user has `is_staff=True`
- the request is going through nginx

## Related guides

- [FAIR_GENOMES.md](FAIR_GENOMES.md)
- [OPERATIONS.md](OPERATIONS.md)
