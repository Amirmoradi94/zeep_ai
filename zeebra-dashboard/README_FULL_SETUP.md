# BeeBlue Dashboard - Full Setup Guide

This guide will help you set up and run the complete BeeBlue Dashboard with the backend API.

## Prerequisites

- Node.js 18+ and npm/yarn
- Python 3.8+
- PostgreSQL database (running via Docker or locally)
- Database credentials from your BeeBlue project

## Setup Instructions

### 1. Backend Setup

#### Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

#### Environment Configuration
Create a `.env` file in the `backend/` directory with your database credentials:

```env
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database_name
DB_USER=your_username
DB_PASSWORD=your_password

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=["http://localhost:5173", "http://localhost:3000"]
```

#### Start the Backend Server
```bash
cd backend
python start.py
```

The API will be available at `http://localhost:8000`

### 2. Frontend Setup

#### Install Dependencies
```bash
npm install
# or
yarn install
```

#### Environment Configuration
Create a `.env` file in the root directory:

```env
VITE_API_URL=http://localhost:8000
VITE_APP_TITLE=BeeBlue Dashboard
```

#### Start the Development Server
```bash
npm run dev
# or
yarn dev
```

The dashboard will be available at `http://localhost:5173`

## API Endpoints

The backend provides the following endpoints:

- **GET /api/overview** - Dashboard overview statistics
- **GET /api/user-stats** - User analytics and growth metrics
- **GET /api/ai-model-stats** - OpenAI/Gemini usage and cost data
- **GET /api/scraping-api-stats** - API performance metrics
- **GET /api/feedback-stats** - User satisfaction data
- **GET /** - Health check endpoint

## Dashboard Features

### Overview Tab
- Total users, costs, requests, response times
- Daily usage trends
- Success rates and uptime metrics
- Frame and token usage comparison

### Users Tab
- Total user count and growth metrics
- Following users and rates
- User distribution by region
- Search statistics per user

### AI Models Tab
- OpenAI vs Gemini comparison
- Cost analysis and token usage
- Frame processing statistics
- Daily trends and totals

### Feedback Tab
- Satisfaction rates and sentiment analysis
- Positive, neutral, and negative feedback breakdown
- Daily feedback trends
- Distribution visualizations

### Scraping API Tab
- Request volumes and success rates
- Response time monitoring
- Performance trends
- Growth metrics

## Database Requirements

The dashboard expects the following database tables:

- `users` - User profiles and regions
- `vision_api_logs` - AI model usage logs
- `scraping_api_logs` - API performance logs
- `queries` - User search queries and feedback
- `products` - Product catalog
- `query_products` - Search results mapping

## Development

### Backend Development
- FastAPI with async PostgreSQL connections
- CORS enabled for local development
- Environment-based configuration
- Error handling and logging

### Frontend Development
- React + TypeScript + Vite
- Tailwind CSS for styling
- Real-time data fetching
- Error boundaries and loading states
- Responsive design

## Troubleshooting

### Backend Issues
1. **Database Connection Errors**: Verify database credentials in `.env`
2. **Port Already in Use**: Change `API_PORT` in backend `.env`
3. **Missing Dependencies**: Run `pip install -r requirements.txt`

### Frontend Issues
1. **API Connection Errors**: Verify `VITE_API_URL` matches backend port
2. **Build Errors**: Clear node_modules and reinstall dependencies
3. **Environment Variables**: Ensure `.env` file exists and variables are prefixed with `VITE_`

### Database Issues
1. **Missing Tables**: Ensure your BeeBlue database is properly initialized
2. **Permission Errors**: Verify database user has SELECT permissions
3. **Connection Timeouts**: Check database host and port settings

## Production Deployment

For production deployment:

1. **Backend**: Use a production WSGI server like Gunicorn
2. **Frontend**: Build with `npm run build` and serve static files
3. **Database**: Use connection pooling and proper security
4. **Environment**: Set proper CORS origins and API URLs

## Support

If you encounter issues:

1. Check the backend logs for API errors
2. Use browser developer tools to debug frontend issues
3. Verify database connectivity with a test query
4. Ensure all environment variables are correctly set 