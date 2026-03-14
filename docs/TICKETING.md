# Alvao Ticketing Integration

This document describes the Alvao Service Desk integration for requesting data access through the catalogue.

## Overview

The ticketing system allows users to:
1. Browse the data catalogue
2. Add datasets, data classes, and tables to a "cart"
3. Submit a data access request (ticket) to Alvao Service Desk
4. View their submitted tickets

## Environment Setup

### Development Environment

For development, the mock service is used:

```env
MOCK_ALVAO=True
```

The mock service:
- Stores tickets in memory and local database
- Generates mock ticket IDs (MOCK-XXXXXXXX)
- Simulates all Alvao API responses locally
- Simulates network delays for realistic testing

### Test Environment

For testing against a real Alvao test instance:

```env
MOCK_ALVAO=False
ALVAO_API_URL=https://test-alvao.yourcompany.com/api/v1
ALVAO_API_TOKEN=your-test-api-token
```

### Production Environment

For production with the real Alvao server:

```env
MOCK_ALVAO=False
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
