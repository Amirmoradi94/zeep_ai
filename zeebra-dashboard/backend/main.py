from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncpg
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging
from config import DB_CONFIG, API_CONFIG
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Zeebra Dashboard API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connection pool
pool = None

async def init_db_pool():
    """Initialize database connection pool"""
    global pool
    try:
        pool = await asyncpg.create_pool(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            min_size=5,
            max_size=20,
            command_timeout=20.0,
            max_inactive_connection_lifetime=300.0,
            max_queries=50000,
            timeout=5.0,
        )
        logger.info("Database connection pool initialized successfully")
        return pool
    except Exception as e:
        logger.error(f"Error initializing database pool: {str(e)}")
        return None

async def execute_db_operation(operation_func):
    """Execute database operation with connection pool"""
    if pool is None:
        await init_db_pool()
        if pool is None:
            logger.error("Failed to initialize database pool")
            return None
    
    conn = None        
    try:
        conn = await pool.acquire()
        return await operation_func(conn)
    except Exception as e:
        logger.error(f"Error in database operation: {str(e)}")
        return None
    finally:
        if conn:
            await pool.release(conn)

@app.on_event("startup")
async def startup_event():
    """Initialize database pool on startup"""
    await init_db_pool()

@app.on_event("shutdown")
async def shutdown_event():
    """Close database pool on shutdown"""
    global pool
    if pool:
        await pool.close()
        logger.info("Database connection pool closed")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "BeeBlue Dashboard API is running"}

@app.get("/api/overview")
async def get_overview():
    """Get overview statistics for the dashboard"""
    try:
        async def operation(conn):
            # Get user stats
            total_users = await conn.fetchval(
                "SELECT COUNT(*) FROM users"
            )
            
            users_this_month = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE created_at >= $1",
                datetime.now().replace(day=1)
            )
            
            users_last_month = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE created_at >= $1 AND created_at < $2",
                (datetime.now().replace(day=1) - timedelta(days=32)).replace(day=1),
                datetime.now().replace(day=1)
            )
            
            user_growth = 0
            if users_last_month > 0:
                user_growth = ((users_this_month - users_last_month) / users_last_month) * 100
            
            # Get cost stats (from vision API logs)
            total_cost = await conn.fetchval(
                "SELECT COALESCE(SUM(usage_cost), 0) FROM vision_api_logs"
            ) or 0
            
            cost_this_month = await conn.fetchval(
                "SELECT COALESCE(SUM(usage_cost), 0) FROM vision_api_logs WHERE created_at >= $1",
                datetime.now().replace(day=1)
            ) or 0
            
            cost_last_month = await conn.fetchval(
                "SELECT COALESCE(SUM(usage_cost), 0) FROM vision_api_logs WHERE created_at >= $1 AND created_at < $2",
                (datetime.now().replace(day=1) - timedelta(days=32)).replace(day=1),
                datetime.now().replace(day=1)
            ) or 0
            
            cost_growth = 0
            if cost_last_month > 0:
                cost_growth = ((cost_this_month - cost_last_month) / cost_last_month) * 100
            
            # Get API request stats
            total_requests = await conn.fetchval(
                "SELECT COUNT(*) FROM scraping_api_logs"
            )
            
            requests_this_week = await conn.fetchval(
                "SELECT COUNT(*) FROM scraping_api_logs WHERE created_at >= $1",
                datetime.now() - timedelta(days=7)
            )
            
            requests_last_week = await conn.fetchval(
                "SELECT COUNT(*) FROM scraping_api_logs WHERE created_at >= $1 AND created_at < $2",
                datetime.now() - timedelta(days=14),
                datetime.now() - timedelta(days=7)
            )
            
            request_growth = 0
            if requests_last_week > 0:
                request_growth = ((requests_this_week - requests_last_week) / requests_last_week) * 100
            
            # Get average response time
            avg_response_time = await conn.fetchval(
                "SELECT AVG(response_time) FROM scraping_api_logs WHERE created_at >= $1",
                datetime.now() - timedelta(days=7)
            ) or 0
            
            avg_response_time_last_week = await conn.fetchval(
                "SELECT AVG(response_time) FROM scraping_api_logs WHERE created_at >= $1 AND created_at < $2",
                datetime.now() - timedelta(days=14),
                datetime.now() - timedelta(days=7)
            ) or 0
            
            response_time_change = 0
            if avg_response_time_last_week > 0:
                response_time_change = ((avg_response_time - avg_response_time_last_week) / avg_response_time_last_week) * 100
            
            # Get success rate
            total_requests_week = await conn.fetchval(
                "SELECT COUNT(*) FROM scraping_api_logs WHERE created_at >= $1",
                datetime.now() - timedelta(days=7)
            )
            
            successful_requests_week = await conn.fetchval(
                "SELECT COUNT(*) FROM scraping_api_logs WHERE success = true AND created_at >= $1",
                datetime.now() - timedelta(days=7)
            )
            
            success_rate = 0
            if total_requests_week > 0:
                success_rate = (successful_requests_week / total_requests_week) * 100
            
            # Get feedback stats
            feedback_stats = await conn.fetch(
                "SELECT feedback, COUNT(*) as count FROM queries WHERE feedback IS NOT NULL GROUP BY feedback"
            )
            
            feedback_counts = {"good": 0, "bad": 0, "neutral": 0}
            total_feedback = 0
            
            for row in feedback_stats:
                feedback_counts[row['feedback'].lower()] = row['count']
                total_feedback += row['count']
            
            positive_feedback_pct = 0
            if total_feedback > 0:
                positive_feedback_pct = (feedback_counts['good'] / total_feedback) * 100
            
            # Get daily API usage for the last 7 days
            daily_usage = await conn.fetch("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as requests
                FROM scraping_api_logs 
                WHERE created_at >= $1
                GROUP BY DATE(created_at)
                ORDER BY date
            """, datetime.now() - timedelta(days=7))
            
            daily_usage_data = []
            for i in range(7):
                date = (datetime.now() - timedelta(days=6-i)).date()
                requests = 0
                for row in daily_usage:
                    if row['date'] == date:
                        requests = row['requests']
                        break
                daily_usage_data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "requests": requests
                })
            
            return {
                "totalUsers": total_users,
                "userGrowth": round(user_growth, 1),
                "totalCost": float(total_cost),
                "costGrowth": round(cost_growth, 1),
                "totalRequests": total_requests,
                "requestGrowth": round(request_growth, 1),
                "avgResponseTime": round(avg_response_time),
                "responseTimeChange": round(response_time_change, 1),
                "successRate": round(success_rate, 1),
                "totalFeedback": total_feedback,
                "positiveFeedbackPct": round(positive_feedback_pct, 1),
                "dailyUsage": daily_usage_data
            }
        
        result = await execute_db_operation(operation)
        if result is None:
            raise HTTPException(status_code=500, detail="Database operation failed")
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting overview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user-stats")
async def get_user_stats():
    """Get detailed user statistics"""
    try:
        async def operation(conn):
            # Total users
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            
            # Users by region
            users_by_region = await conn.fetch(
                "SELECT region, COUNT(*) as count FROM users GROUP BY region"
            )
            
            # Following users
            following_users = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE is_following = true"
            )
            
            # Monthly new users (last 12 months)
            monthly_users = await conn.fetch("""
                SELECT 
                    DATE_TRUNC('month', created_at) as month,
                    COUNT(*) as count
                FROM users 
                WHERE created_at >= $1
                GROUP BY DATE_TRUNC('month', created_at)
                ORDER BY month
            """, datetime.now() - timedelta(days=365))
            
            # Search activity
            total_searches = await conn.fetchval("SELECT COUNT(*) FROM queries")
            avg_searches_per_user = total_searches / total_users if total_users > 0 else 0
            
            return {
                "totalUsers": total_users,
                "followingUsers": following_users,
                "followingRate": round((following_users / total_users) * 100, 1) if total_users > 0 else 0,
                "usersByRegion": [{"region": row["region"], "count": row["count"]} for row in users_by_region],
                "monthlyNewUsers": [{"month": row["month"].strftime("%Y-%m"), "count": row["count"]} for row in monthly_users],
                "totalSearches": total_searches,
                "avgSearchesPerUser": round(avg_searches_per_user, 1)
            }
        
        result = await execute_db_operation(operation)
        if result is None:
            raise HTTPException(status_code=500, detail="Database operation failed")
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

#----------------------------------* AI MODEL STATS *----------------------------------
@app.get("/api/ai-model-stats")
async def get_ai_model_stats():
    """Get AI model usage statistics"""
    try:
        async def operation(conn):
            # Daily stats for the last 7 days
            daily_stats = await conn.fetch("""
                SELECT 
                    DATE(created_at) as date,
                    endpoint,
                    COUNT(*) as requests,
                    SUM(usage_tokens) as tokens,
                    SUM(usage_cost) as cost,
                    SUM(frame_count) as frames,
                    AVG(response_time) as avg_response_time,
                    COUNT(CASE WHEN success = true THEN 1 END) * 100.0 / COUNT(*) as success_rate
                FROM vision_api_logs 
                WHERE created_at >= $1
                GROUP BY DATE(created_at), endpoint
                ORDER BY date, endpoint
            """, datetime.now() - timedelta(days=7))
            
            # Total stats (all time)
            total_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(usage_tokens) as total_tokens,
                    SUM(usage_cost) as total_cost,
                    SUM(frame_count) as total_frames,
                    AVG(response_time) as avg_response_time
                FROM vision_api_logs
            """)

            # All-time frames for OpenAI and Gemini
            openai_frames = await conn.fetchval(
                "SELECT COALESCE(SUM(frame_count), 0) FROM vision_api_logs WHERE LOWER(endpoint) LIKE '%openai_vision%'"
            ) or 0
            gemini_frames = await conn.fetchval(
                "SELECT COALESCE(SUM(frame_count), 0) FROM vision_api_logs WHERE LOWER(endpoint) LIKE '%gemini_vision%'"
            ) or 0
            
            # All-time tokens for OpenAI and Gemini
            openai_tokens = await conn.fetchval(
                "SELECT COALESCE(SUM(usage_tokens), 0) FROM vision_api_logs WHERE LOWER(endpoint) LIKE '%openai_vision%'"
            ) or 0
            gemini_tokens = await conn.fetchval(
                "SELECT COALESCE(SUM(usage_tokens), 0) FROM vision_api_logs WHERE LOWER(endpoint) LIKE '%gemini_vision%'"
            ) or 0
            
            # Group by model (daily)
            openai_data = []
            gemini_data = []
            
            for i in range(7):
                date = (datetime.now() - timedelta(days=6-i)).date()
                date_str = date.strftime("%Y-%m-%d")
                
                openai_stats = {"date": date_str, "requests": 0, "tokens": 0, "cost": 0, "frames": 0}
                gemini_stats = {"date": date_str, "requests": 0, "tokens": 0, "cost": 0, "frames": 0}
                
                for row in daily_stats:
                    if row['date'] == date:
                        stats = {
                            "requests": row['requests'],
                            "tokens": row['tokens'] or 0,
                            "cost": float(row['cost']) if row['cost'] else 0,
                            "frames": row['frames'] or 0
                        }
                        
                        if 'openai_vision' in row['endpoint'].lower():
                            openai_stats.update(stats)
                        elif 'gemini_vision' in row['endpoint'].lower():
                            gemini_stats.update(stats)
                
                openai_data.append(openai_stats)
                gemini_data.append(gemini_stats)
            
            return {
                "openai": openai_data,
                "gemini": gemini_data,
                "totals": {
                    "requests": total_stats['total_requests'] or 0,
                    "tokens": total_stats['total_tokens'] or 0,
                    "cost": float(total_stats['total_cost']) if total_stats['total_cost'] else 0,
                    "frames": total_stats['total_frames'] or 0,
                    "avgResponseTime": round(total_stats['avg_response_time']) if total_stats['avg_response_time'] else 0,
                    "openaiFrames": openai_frames,
                    "geminiFrames": gemini_frames,
                    "openaiTokens": openai_tokens,
                    "geminiTokens": gemini_tokens
                }
            }
        
        result = await execute_db_operation(operation)
        if result is None:
            raise HTTPException(status_code=500, detail="Database operation failed")
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting AI model stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

#----------------------------------* SCRAPING API STATS *----------------------------------
@app.get("/api/scraping-api-stats")
async def get_scraping_api_stats():
    """
    Get scraping API statistics for the dashboard.

    Returns:
        dict: {
            "totalRequests": int,
            "totalAvgResponseTime": int,
            "totalSuccessRate": float,
            "daily": [
                {
                    "date": str,
                    "requests": int,
                    "responseTime": int,
                    "successRate": float
                },
                ...
            ]
        }
    """
    try:
        async def operation(conn):
            # Total requests (all time)
            total_requests = await conn.fetchval("SELECT COUNT(*) FROM scraping_api_logs")

            # All-time average response time
            total_avg_response_time = await conn.fetchval(
                "SELECT AVG(response_time) FROM scraping_api_logs"
            ) or 0

            # All-time success rate
            total_success_count = await conn.fetchval(
                "SELECT COUNT(*) FROM scraping_api_logs WHERE success = true"
            ) or 0
            total_success_rate = (total_success_count / total_requests) * 100 if total_requests > 0 else 0

            # Daily stats for the last 7 days (including today)
            daily_stats = await conn.fetch("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as requests,
                    AVG(response_time) as avg_response_time,
                    COUNT(CASE WHEN success = true THEN 1 END) * 100.0 / COUNT(*) as success_rate
                FROM scraping_api_logs 
                WHERE created_at >= $1
                GROUP BY DATE(created_at)
                ORDER BY date
            """, datetime.now() - timedelta(days=7))

            # Build a dict for quick lookup by date
            daily_stats_by_date = {row['date']: row for row in daily_stats}

            # Fill in missing dates with zero values for the last 7 days
            result_data = []
            for i in range(7):
                date = (datetime.now() - timedelta(days=6 - i)).date()
                date_str = date.strftime("%Y-%m-%d")
                row = daily_stats_by_date.get(date)
                if row:
                    result_data.append({
                        "date": date_str,
                        "requests": row['requests'],
                        "responseTime": round(row['avg_response_time']) if row['avg_response_time'] else 0,
                        "successRate": round(row['success_rate'], 1) if row['success_rate'] is not None else 0
                    })
                else:
                    result_data.append({
                        "date": date_str,
                        "requests": 0,
                        "responseTime": 0,
                        "successRate": 0
                    })
            return {
                "totalRequests": total_requests,
                "totalAvgResponseTime": round(total_avg_response_time) if total_avg_response_time else 0,
                "totalSuccessRate": round(total_success_rate, 1),
                "daily": result_data
            }
        result = await execute_db_operation(operation)
        if result is None:
            raise HTTPException(status_code=500, detail="Database operation failed")
        return result

    except Exception as e:
        logger.error(f"Error getting scraping API stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

#----------------------------------* FEEDBACK STATS *----------------------------------
@app.get("/api/feedback-stats")
async def get_feedback_stats():
    """Get user feedback statistics"""
    try:
        async def operation(conn):
            # Feedback counts
            feedback_stats = await conn.fetch(
                "SELECT feedback, COUNT(*) as count FROM queries WHERE feedback IS NOT NULL GROUP BY feedback"
            )
            
            feedback_counts = {"GOOD": 0, "BAD": 0, "NEUTRAL": 0}
            
            for row in feedback_stats:
                feedback_counts[row['feedback'].upper()] = row['count']
            
            # Daily feedback for the last 7 days
            daily_feedback = await conn.fetch("""
                SELECT 
                    DATE(created_at) as date,
                    feedback,
                    COUNT(*) as count
                FROM queries 
                WHERE feedback IS NOT NULL AND created_at >= $1
                GROUP BY DATE(created_at), feedback
                ORDER BY date
            """, datetime.now() - timedelta(days=7))
            
            # Process daily feedback data
            daily_data = []
            for i in range(7):
                date = (datetime.now() - timedelta(days=6-i)).date()
                date_str = date.strftime("%Y-%m-%d")
                
                daily_counts = {"date": date_str, "good": 0, "bad": 0, "neutral": 0}
                
                for row in daily_feedback:
                    if row['date'] == date:
                        daily_counts[row['feedback'].lower()] = row['count']
                
                daily_data.append(daily_counts)
            
            return {
                **feedback_counts,
                "daily": daily_data
            }
        
        result = await execute_db_operation(operation)
        if result is None:
            raise HTTPException(status_code=500, detail="Database operation failed")
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting feedback stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

#----------------------------------* DASHBOARD SETTINGS *----------------------------------
class DashboardSettingsUpdate(BaseModel):
    active_model: Optional[str] = None
    save_training_data: Optional[bool] = None

@app.put("/api/dashboard-settings")
async def update_dashboard_settings(settings: DashboardSettingsUpdate):
    """Update dashboard settings (active_model, save_training_data)"""
    try:
        async def operation(conn):
            # Check if a row exists
            exists = await conn.fetchval("SELECT COUNT(*) FROM dashboard_settings")
            if exists == 0:
                # Insert new row
                await conn.execute(
                    "INSERT INTO dashboard_settings (active_model, save_training_data) VALUES ($1, $2)",
                    settings.active_model, settings.save_training_data
                )
            else:
                # Update existing row
                if settings.active_model is not None and settings.save_training_data is not None:
                    await conn.execute(
                        "UPDATE dashboard_settings SET active_model = $1, save_training_data = $2",
                        settings.active_model, settings.save_training_data
                    )
                elif settings.active_model is not None:
                    await conn.execute(
                        "UPDATE dashboard_settings SET active_model = $1",
                        settings.active_model
                    )
                elif settings.save_training_data is not None:
                    await conn.execute(
                        "UPDATE dashboard_settings SET save_training_data = $1",
                        settings.save_training_data
                    )
            return {"success": True}
        result = await execute_db_operation(operation)
        if result is None:
            raise HTTPException(status_code=500, detail="Database operation failed")
        return result
    except Exception as e:
        logger.error(f"Error updating dashboard settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_CONFIG["host"], port=API_CONFIG["port"], reload=API_CONFIG["reload"]) 