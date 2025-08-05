# BeeBlue Shop Docker Setup

This directory contains all the Docker configuration files for the BeeBlue Shop application.

## Structure

- `bot/`: Docker files for the main Zeebra bot service
- `db/`: Docker files for the PostgreSQL database
- `nginx/`: Docker files for the Nginx web server

## Services

### BeeBlue Bot
- Main application service that handles Instagram product search
- Built with FastAPI and Python 3.10
- Processes media posts and finds relevant products

### PostgreSQL Database
- Stores all application data including user information, product details, and search history
- PostgreSQL 15 with persistent volume for data storage

### Nginx
- Acts as a reverse proxy for the application
- Handles SSL/TLS termination
- Routes traffic to the appropriate services

### Redis
- In-memory data store for caching and session management
- Used for temporary storage of user data

## Environment Variables

Each service has its own environment file:

- For bot production: `bot/.prod.env`
- For bot development: `bot/.dev.env`
- For database: `db/.prod.env`

Example environment files are provided with the `-example` suffix.

## Deployment

To deploy all services in dev:

```bash
./deploy.sh dev
```

To deploy all services in production:

```bash
./deploy.sh prod
```

To rebuild and deploy a specific service:

```bash
docker-compose up -d -f <dev_or_prod_yml_file> --build <service_name>
```

## Data Persistence

The following volumes are used for data persistence:

- `db_data`: PostgreSQL database data
- `redis_data`: Redis data

## SSL Certificate

The application uses Let's Encrypt for SSL certificates. The certificates are mounted from the host at `/etc/letsencrypt`. 