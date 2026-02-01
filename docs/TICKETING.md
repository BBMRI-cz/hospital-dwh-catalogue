# Alvao Ticketing Integration

This document describes the Alvao Service Desk integration for requesting data access through the catalogue.

## Overview

The ticketing system allows users to:
1. Browse the data catalogue
2. Add datasets, data classes, and tables to a "cart"
3. Submit a data access request (ticket) to Alvao Service Desk
4. View their submitted tickets

## Architecture

### Components

- **ticketing app**: Django application handling cart and ticket management
- **AlvaoService**: Real Alvao API client (production/test)
- **MockAlvaoService**: Local mock service (development)

### Environment Configuration

The ticketing system uses environment variables for all configuration:

```bash
# Development (mock service - no real Alvao needed)
ALVAO_USE_MOCK=True

# Production/Test (real Alvao server)
ALVAO_USE_MOCK=False
ALVAO_API_URL=https://alvao.yourcompany.com/api/v1
ALVAO_API_TOKEN=your-api-token
```

See `.env.dev.example`, `.env.test.example`, and `.env.prod.example` for full configuration.

## Environment Setup

### Development Environment

For development, the mock service is used:

```env
ALVAO_USE_MOCK=True
```

The mock service:
- Stores tickets in memory and local database
- Generates mock ticket IDs (MOCK-XXXXXXXX)
- Simulates all Alvao API responses locally
- Simulates network delays for realistic testing

### Test Environment

For testing against a real Alvao test instance:

```env
ALVAO_USE_MOCK=False
ALVAO_API_URL=https://test-alvao.yourcompany.com/api/v1
ALVAO_API_TOKEN=your-test-api-token
```

### Production Environment

For production with the real Alvao server:

```env
ALVAO_USE_MOCK=False
ALVAO_API_URL=https://alvao.yourcompany.com/api/v1
ALVAO_API_TOKEN=your-production-api-token
ALVAO_DEFAULT_SERVICE_ID=123  # Optional: default service for tickets
```

## Authentication

The integration supports two authentication methods:

### Bearer Token (Recommended)

```env
ALVAO_API_TOKEN=your-bearer-token
```

### Basic Authentication (Alternative)

```env
ALVAO_SERVICE_ACCOUNT_USERNAME=service_user
ALVAO_SERVICE_ACCOUNT_PASSWORD=password
```

One service account creates tickets for all users. The requester's email is included in the ticket data.

## Database

Ticketing data is stored in the `default` database (same as auth_db in most setups):

- `ticketing_ticket_request`: Stores ticket requests with status and Alvao response
- `ticketing_ticket_request_item`: Stores individual items in each request

Run migrations:

```bash
python manage.py migrate ticketing
```

## API Endpoints

### Cart Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ticketing/cart/` | GET | View cart contents |
| `/ticketing/cart/add/` | POST | Add item to cart |
| `/ticketing/cart/remove/<id>/` | POST | Remove item from cart |
| `/ticketing/cart/clear/` | POST | Clear all cart items |
| `/ticketing/cart/submit/` | POST | Submit cart as ticket |
| `/ticketing/cart/count/` | GET | Get current cart count |

### Ticket Views

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ticketing/submitted/` | GET | Success page after submission |
| `/ticketing/my-tickets/` | GET | List user's tickets |
| `/ticketing/tickets/<id>/` | GET | Ticket detail view |

## Usage Flow

1. User browses catalogue at `/warehouse/`
2. User clicks "Add to cart" button on datasets/tables
3. User views cart at `/ticketing/cart/`
4. User fills in email and submits request
5. System creates ticket in Alvao
6. User sees confirmation with ticket ID
7. User can view tickets at `/ticketing/my-tickets/`

## Alvao API Integration

The service expects Alvao REST API endpoints:

### Create Ticket
```
POST /tickets
{
    "subject": "Data Access Request",
    "description": "...",
    "requesterEmail": "user@example.com",
    "requesterName": "John Doe",
    "serviceId": 123
}
```

### Get Ticket
```
GET /tickets/{ticketId}
```

### List Tickets by Requester
```
GET /tickets?requester=user@example.com
```

## Customization

### Custom Fields

To add custom fields to tickets, configure in your service:

```python
ticket_data = TicketData(
    subject="...",
    description="...",
    requester_email="...",
    custom_fields={
        "department": "Research",
        "project": "COVID-19 Study"
    }
)
```

### Default Service ID

Set `ALVAO_DEFAULT_SERVICE_ID` to automatically assign tickets to a specific Alvao service.

## Troubleshooting

### Mock Service Issues

Check mock storage:
```python
from ticketing.services.mock_service import MockAlvaoService
print(MockAlvaoService._memory_storage)
```

Clear mock storage:
```python
MockAlvaoService.clear_storage()
```

### Real API Issues

Enable debug logging:
```python
LOGGING['loggers']['ticketing'] = {
    'handlers': ['console'],
    'level': 'DEBUG',
}
```

### Connection Errors

Verify:
1. `ALVAO_API_URL` is correct
2. `ALVAO_API_TOKEN` is valid
3. Network connectivity to Alvao server
4. Firewall rules allow outbound HTTPS

## Testing

Run ticketing tests:

```bash
python manage.py test ticketing
```

The tests use the mock service and don't require a real Alvao connection.
