# Ticketing

The ticketing system lets users request access to data through the catalogue. Users add datasets, distributions, or tables to a cart and submit a request, which creates a ticket in Alvao Service Desk.

## How it works

1. A user browses the catalogue and adds items to their cart
2. They go to `/cart/`, fill out the request form, and submit
3. The application creates a `TicketRequest` record in the local database
4. It sends the request to the Alvao Service Desk API
5. The user can view their submitted tickets at `/tickets/`

The cart is stored in the user's session and holds up to 50 items.

## Configuration

### Development or staging

For local development or isolated staging validation, use the mock service:

```bash
MOCK_ALVAO=True
```

The mock stores tickets locally, generates fake ticket IDs (`MOCK-XXXXXXXX`), and simulates API responses with realistic delays. No external service needed.

### Staging with real Alvao

To test against a real Alvao instance:

```bash
MOCK_ALVAO=False
ALVAO_API_URL=https://test-alvao.yourcompany.com/AlvaoRestApi/v1
ALVAO_SERVICE_ACCOUNT_USERNAME=service-account
ALVAO_SERVICE_ACCOUNT_PASSWORD=password
```

### Production

```bash
MOCK_ALVAO=False
ALVAO_API_URL=https://alvao.yourcompany.com/AlvaoRestApi/v1
ALVAO_SERVICE_ACCOUNT_USERNAME=your-service-account
ALVAO_SERVICE_ACCOUNT_PASSWORD=your-password
ALVAO_DEFAULT_SERVICE_ID=109
```

## Authentication with Alvao

The application uses HTTP Basic Authentication with a single service account to create tickets on behalf of all users. The requester's email is included in the ticket data so Alvao knows who made the request.

Set the service account credentials in your `.env`:

```bash
ALVAO_SERVICE_ACCOUNT_USERNAME=service-account
ALVAO_SERVICE_ACCOUNT_PASSWORD=password
```

The Alvao client has built-in retry logic with exponential backoff for transient errors (HTTP 429 and 5xx status codes, up to 3 retries).

## URL routes

| URL | Purpose |
|---|---|
| `/cart/` | View cart and submit a request |
| `/cart/add/` | Add an item to the cart (POST) |
| `/cart/remove/` | Remove an item from the cart (POST) |
| `/tickets/` | View submitted ticket history |
