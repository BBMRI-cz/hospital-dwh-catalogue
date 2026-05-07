# User Guide

Use this page when the Catalogue is already running and you want to know what people can do in the browser. If you need to start or deploy the stack, use [OPERATIONS.md](OPERATIONS.md).

## Before you start

You need:

- a running Catalogue
- a user account that can sign in

Authentication depends on the environment:

- `dev` accepts any non-empty username and password because `MOCK_LDAP=True`
- `staging` usually keeps LDAP mocked, but can also use real LDAP
- `prod` uses real LDAP only

The account named by `DJANGO_SUPERUSER_USERNAME` is the env-managed staff/superuser
account in every environment, including `staging` and `prod`, as long as it does
not collide with an existing LDAP-only user.

## Main pages

| URL | Purpose |
|---|---|
| `/` | Catalogue index with search, filters, and result cards |
| `/cart/` | Access-request cart and submission form |
| `/tickets/` | Request history |
| `/api/jsonld` | Aggregate JSON-LD export for logged-in users |
| `/api/rdf` | Aggregate RDF export for logged-in users |
| `/admin/` | Django admin for staff and superusers |
| `/grafana/` | Observability UI for logged-in staff users |

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
4. the Catalogue stores a local `TicketRequest`
5. the Catalogue sends the request to the configured ticketing service

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
