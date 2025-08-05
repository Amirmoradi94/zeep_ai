# BeeBlue Dashboard Backend

This is the FastAPI backend for the BeeBlue Dashboard that provides real-time analytics data from the PostgreSQL database.

## Features

- **Overview Statistics**: Total users, costs, API requests, response times
- **User Analytics**: Regional distribution, growth metrics, search activity
- **AI Model Statistics**: OpenAI and Gemini usage, costs, token consumption
- **Scraping API Metrics**: Request success rates, response times
- **Feedback Analytics**: User satisfaction metrics

## Database Tables Used

The backend connects to the following database tables:

- `users` - User registration and profile data
- `vision_api_logs` - AI model usage and costs (OpenAI, Gemini)
- `scraping_api_logs` - API request metrics and response times
- `queries` - User search queries and feedback
- `products` - Product search results
- `query_products` - Links between queries and products

## Installation

1. **Install Python dependencies:**
   ```bash
   cd beeblue-dashboard/backend
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   Create a `.env` file with your database credentials:
   ```env
   DB_HOST=bb_db_prod
   DB_PORT=5432
   DB_NAME=beeblue_db
   DB_USER=postgres
   DB_PASSWORD=your_password
   NODE_ENV=development
   ```

3. **Make sure your PostgreSQL database is running and accessible.**

## Usage

### Start the backend server:

```bash
# Option 1: Using the startup script
python start.py

# Option 2: Using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Option 3: Using Python module
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

Once the server is running, you can access:
- **Interactive API docs**: http://localhost:8000/docs
- **ReDoc documentation**: http://localhost:8000/redoc

## API Endpoints

- `GET /` - Health check
- `GET /api/overview` - Dashboard overview statistics
- `GET /api/user-stats` - Detailed user analytics
- `GET /api/ai-model-stats` - AI model usage statistics
- `GET /api/scraping-api-stats` - Scraping API metrics
- `GET /api/feedback-stats` - User feedback analytics

## Configuration

The backend configuration is managed in `config.py`:

- **Database settings**: Host, port, database name, credentials
- **API settings**: Host, port, reload mode for development

## Development

For development mode, set `NODE_ENV=development` in your environment variables to enable auto-reload on code changes.

## CORS Configuration

The backend is configured to allow CORS from all origins for development. In production, update the `allow_origins` setting in `main.py` to specify your frontend domain.

## Error Handling

The backend includes comprehensive error handling and logging. Check the console output for any database connection issues or API errors.

## Database Connection

The backend uses asyncpg for PostgreSQL connections with a connection pool for optimal performance:
- **Pool size**: 5-20 connections
- **Command timeout**: 20 seconds
- **Connection timeout**: 5 seconds

Make sure your database container is running and accessible from the backend service. 