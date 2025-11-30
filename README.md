# Hospital Data Warehouse Catalogue

A Django-based web application for browsing and managing hospital data warehouse metadata.

## Prerequisites 

- **Docker Desktop** - [Docker Website](https://www.docker.com/products/docker-desktop)
- **Git** (optional)

## Running the application

```bash
docker-compose up -d
```

Open browser and head to:
```
http://localhost:8080/warehouse/katalog/
```

## Sample data

Generated mock data.

## Stopping the application

```bash
docker-compose down
```

To also delete the database volume (fresh start):

```bash
docker-compose down -v
```
