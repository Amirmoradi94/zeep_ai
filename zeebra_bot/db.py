import os
import logging
import asyncpg
from dotenv import load_dotenv
from datetime import datetime
import sentry_sdk
import asyncio
# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("zeebra.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Database connection parameters
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Connection pool
pool = None

#---------------------------------- INIT DATABASE POOL ----------------------------------
async def init_db_pool():
    global pool
    try:
        pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            min_size=5,
            max_size=20,
            command_timeout=20.0,       # Increased timeout for commands
            max_inactive_connection_lifetime=300.0,  # Close inactive connections
            max_queries=50000,          # Limit queries per connection to avoid leaks
            timeout=5.0,                # Reduced connection acquisition timeout
            statement_cache_size=0      # Disable statement cache to avoid memory leaks
        )
        logger.info("Database connection pool initialized successfully")
        return pool
    except Exception as e:
        await error_handler(
            f"Error initializing database pool: {str(e)}",
            "error",
            "high",
            logger
        )
        return None

#---------------------------------- EXECUTE DATABASE OPERATION ----------------------------------
async def execute_db_operation(operation_func):
    if pool is None:
        await init_db_pool()
        if pool is None:
            logger.error("Failed to initialize database pool")
            return None
    
    conn = None        
    try:
        conn = await pool.acquire()
        return await asyncio.wait_for(operation_func(conn), timeout=15.0)  # 15 second timeout for operations
    except asyncio.TimeoutError:
        logger.error("Database operation timed out")
        await error_handler(
            "Database operation timed out",
            "error",
            "high",
            logger
        )
        return None
    except asyncpg.exceptions.QueryCanceledError:
        logger.error("Query was canceled by the database server")
        await error_handler(
            "Query was canceled by the database server",
            "error",
            "high",
            logger
        )
        return None
    except Exception as e:
        logger.error(f"Error in database operation: {str(e)}")
        await error_handler(
            f"Error in database operation: {str(e)}",
            "error",
            "high",
            logger
        )
        return None
    finally:
        if conn:
            await pool.release(conn)

#---------------------------------- GET DATABASE CONNECTION ----------------------------------
async def get_db_connection():
    if pool is None:
        await init_db_pool()
    try:
        return await pool.acquire()
    except Exception as e:
        await error_handler(
            f"Error getting database connection: {str(e)}",
            "error",
            "high",
            logger
        )
        return None

#---------------------------------- CLOSE DATABASE POOL ----------------------------------
async def close_db_pool():
    global pool
    if pool:
        await pool.close()
        logger.info("Database connection pool closed")

#------------------------------------* ERROR HANDLER *------------------------------------
async def error_handler(error_message, error_type, error_severity, logger=None):
    try:
        await log_errors_event(
            error_type,
            error_severity,
            f"{error_message}"
        )
        # Create a proper Exception object
        error = Exception(error_message)
        sentry_sdk.capture_exception(error)
        if logger:
            logger.error(f"Error: {error_message}")
    except Exception as e:
        if logger:
            logger.error(f"Error in error_handler: {str(e)}")

#---------------------------------- SYSTEM MONITORING ----------------------------------
async def log_errors_event(event_type, severity, message, details=None):
    try:
        async def operation(conn):
            query = """
                INSERT INTO error_logs (log_type, severity, message, details)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """
            try:
                log_id = await conn.fetchval(query, event_type, severity, message, details)
                return log_id is not None
            except asyncpg.exceptions.QueryCanceledError:
                # We don't log errors from error logging to avoid recursion
                return False

        return await execute_db_operation(operation)
    except Exception as e:
        # We don't use error_handler here to avoid infinite recursion
        logger.error(f"Error logging event: {str(e)}")
        return False

#---------------------------------- API CALL LOGGING ----------------------------------
async def vision_api_call(endpoint, response_time, user_id=None, success=None, usage_tokens=None, usage_cost=None, frame_count=None, updated_at=None, logger=None):
    try:
        async def operation(conn):
            query = """
                INSERT INTO vision_api_logs (endpoint, response_time, user_id, success, usage_tokens, usage_cost, frame_count, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """
            try:
                log_id = await conn.fetchval(query, endpoint, response_time, user_id, success, usage_tokens, usage_cost, frame_count, updated_at)
                return log_id is not None
            except asyncpg.exceptions.QueryCanceledError:
                logger.error("Query timeout occurred while logging API call")
                await error_handler(
                    "Database query timeout while logging API call",
                    "error",
                    "medium",
                    logger
                )
                return False

        return await execute_db_operation(operation)
    except Exception as e:
        await error_handler(
            f"Error logging API call: {str(e)}",
            "error",
            "medium",
            logger
        )
        return False

#---------------------------------- GET USER INFO ----------------------------------
async def get_user_info(user_id, fields=None, logger=None):
    try:
        async def operation(conn):
            # Default fields if none provided
            selected_fields = fields if fields is not None else ['user_id']

            # Ensure selected_fields is a list
            if isinstance(selected_fields, str):
                selected_fields = [selected_fields]

            #logger.info(f"fields: {selected_fields}")

            # Build the query string safely
            query = f"SELECT {', '.join(selected_fields)} FROM users WHERE user_id = $1"
            row = await conn.fetchrow(query, user_id)

            #logger.info(f"row: {row}")

            if not row:
                return None  # Return None if user doesn't exist

            # Convert row to dict
            return {field: row.get(field, None) for field in selected_fields}

        return await execute_db_operation(operation)

    except Exception as e:
        await error_handler(
            f"Error getting user info: {str(e)}",
            "error",
            "high",
            logger
        )
        # Return dict with None values for each requested field
        fallback_fields = fields if fields is not None else ['user_id']
        if isinstance(fallback_fields, str):
            fallback_fields = [fallback_fields]
        return {field: None for field in fallback_fields}

#---------------------------------- UPDATE QUERY ----------------------------------
async def update_query(query_id, user_id, product_brand, logger):
    try:
        async def operation(conn):
            query = """
                UPDATE queries
                SET product_brand = $1
                WHERE query_id = $2
                RETURNING query_id
            """
            try:
                updated_query_id = await conn.fetchval(query, product_brand, query_id)
                return updated_query_id is not None
            except asyncpg.exceptions.QueryCanceledError:
                logger.error("Query timeout occurred while updating query")
                await error_handler(
                    "Database query timeout while updating query",
                    "error",
                    "high",
                    logger
                )
                return False

        return await execute_db_operation(operation)
    except Exception as e:
        await error_handler(
            f"Error updating query with product brand {product_brand}: {str(e)}",
            "error",
            "high",
            logger
        )
        return False

#---------------------------------- UPDATE USER INFO ----------------------------------
async def update_user_info(user_id, logger, **kwargs):
    try:
        async def operation(conn):
            # Build the update query dynamically based on provided fields
            set_parts = []
            values = []
            for i, (key, value) in enumerate(kwargs.items(), start=2):
                set_parts.append(f"{key} = ${i}")
                values.append(value)

            query = f"""
                UPDATE users 
                SET {', '.join(set_parts)}, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = $1
                RETURNING user_id
            """
            values.insert(0, user_id)
            
            try:
                updated_id = await conn.fetchval(query, *values)
                return updated_id is not None
            except asyncpg.exceptions.QueryCanceledError:
                logger.error("Query timeout occurred while updating user info")
                await error_handler(
                    "Database query timeout while updating user info",
                    "error",
                    "high",
                    logger
                )
                return False

        return await execute_db_operation(operation)
    except Exception as e:
        await error_handler(
            f"Error updating user info: {str(e)}",
            "error",
            "high",
            logger
        )
        return False

#---------------------------------- CREATE NEW USER ----------------------------------
async def create_new_user(user_id, logger, is_following=False, location='iran', gender='female', reels_search_count=0, images_search_count=0, created_at=None, updated_at=None):
    try:
        async def operation(conn):
            query = """
                INSERT INTO users (user_id, is_following, location, gender, reels_search_count, images_search_count, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING user_id
            """
            try:
                created_user_id = await conn.fetchval(
                    query, 
                    user_id, 
                    is_following, 
                    location, 
                    gender, 
                    reels_search_count, 
                    images_search_count, 
                    created_at or datetime.now(), 
                    updated_at or datetime.now()
                )
                
                if created_user_id:
                    return created_user_id
                
                return None
            except asyncpg.exceptions.QueryCanceledError:
                logger.error("Query timeout occurred while creating new user")
                await error_handler(
                    "Database query timeout while creating new user",
                    "error",
                    "high",
                    logger
                )
                return None

        return await execute_db_operation(operation)
    except Exception as e:
        await error_handler(
            f"Error creating new user: {str(e)}",
            "error",
            "medium",
            logger
        )
        return None
    
#---------------------------------- GET GENERATED QUERY ----------------------------------
async def get_generated_query(user_id, query_id, logger):
    try:
        async def operation(conn):
            # Query to get the most recent generated query for the given product
            query = """
                SELECT generated_query 
                FROM queries 
                WHERE user_id = $1 
                AND query_id = $2 
                ORDER BY created_at DESC
                LIMIT 1
            """
            try:
                result = await conn.fetchval(query, user_id, query_id)
                if result:
                    #logger.info(f"Found existing query for product: {query_id}")
                    return result
                logger.info(f"No existing query found for product: {query_id}")
                return None
            except asyncpg.exceptions.QueryCanceledError:
                logger.error("Query timeout occurred while getting generated query")
                await error_handler(
                    "Database query timeout while getting generated query",
                    "error",
                    "high",
                    logger
                )
                return None

        return await execute_db_operation(operation)
    except Exception as e:
        await error_handler(
            f"Error getting generated query for query {query_id}: {str(e)}",
            "error",
            "medium",
            logger
        )
        return None
        
#---------------------------------- SAVE QUERY ----------------------------------
async def save_query(user_id, product_name, product_brand, product_title, feedback, logger):
    try:
        async def operation(conn):
            # First check if a query with this product_name already exists for this user
            check_query = """
                SELECT query_id FROM queries 
                WHERE user_id = $1 AND product_name = $2
            """
            existing_query_id = await conn.fetchval(check_query, user_id, product_name)
            
            if existing_query_id:
                return existing_query_id
                
            created_at = datetime.now()

            query = """
                INSERT INTO queries (user_id, created_at, product_name, product_brand, product_title, feedback)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING query_id
            """
            try:
                query_id = await conn.fetchval(query, user_id, created_at, product_name, product_brand, product_title, feedback)
                return query_id
            except asyncpg.exceptions.QueryCanceledError:
                logger.error("Query timeout occurred while saving query")
                await error_handler(
                    "Database query timeout while saving query",
                    "error",
                    "medium",
                    logger
                )
                return None

        return await execute_db_operation(operation)
    except Exception as e:
        await error_handler(
            f"Error saving query: {str(e)}",
            "error",
            "medium",
            logger
        )
        return None
    
#---------------------------------- UPDATE QUERY ----------------------------------
async def update_feedback_query(query_id, feedback, logger):
    try:
        async def operation(conn):
            query = """
                UPDATE queries
                SET feedback = $1
                WHERE query_id = $2
                RETURNING query_id
            """
            try:
                updated_query_id = await conn.fetchval(query, feedback, query_id)
                return updated_query_id is not None
            except asyncpg.exceptions.QueryCanceledError:
                logger.error("Query timeout occurred while updating query")
                await error_handler(
                    "Database query timeout while updating query",
                    "error",
                    "medium",
                    logger
                )
                return False

        return await execute_db_operation(operation)
    except Exception as e:
        await error_handler(
            f"Error updating query: {str(e)}",
            "error",
            "medium",
            logger
        )
        return False

#---------------------------------- CLEAN TEMP VARIABLES ----------------------------------
async def clean_temp_variables(user_id, logger):
    try:
        async def operation(conn):
            query = """
                DELETE FROM temp_variables WHERE user_id = $1
            """
            try:
                await conn.execute(query, user_id)
                return True
            except asyncpg.exceptions.QueryCanceledError:
                logger.error("Query timeout occurred while cleaning temp variables")
                await error_handler(
                    "Database query timeout while cleaning temp variables",
                    "error",
                    "medium",
                    logger
                )
                return False

        return await execute_db_operation(operation)
    except Exception as e:
        await error_handler(
            f"Error cleaning temp variables: {str(e)}",
            "error",
            "medium",
            logger
        )
        return False
    
#---------------------------------- GET TEMP VARIABLES ----------------------------------
async def get_temp_variables(user_id, fields=None, logger=None):
    """
    Fetches the most recent temp_variables row for a user, returning a dict of the requested fields.
    If fields is None, defaults to ['post_url', 'post_type', 'reel_caption', 'initial_query'].
    Returns None if no row is found.
    """
    try:
        async def operation(conn):
            # Defensive: avoid mutable default argument
            selected_fields = fields if fields is not None else ['post_url', 'post_type', 'reel_caption', 'initial_query']

            # Build the SELECT query dynamically
            select_fields = ', '.join(selected_fields)
            query = f"""
                SELECT {select_fields}
                FROM temp_variables
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT 1
            """

            try:
                row = await conn.fetchrow(query, user_id)
                if not row:
                    return None

                # Convert row to dictionary
                # row is a Record, supports dict(row) or row.get(field)
                result = {}
                for field in selected_fields:
                    result[field] = row.get(field)
                return result
            except asyncpg.exceptions.QueryCanceledError:
                if logger:
                    logger.error("Query timeout occurred while getting temp variables")
                await error_handler(
                    "Database query timeout while getting temp variables",
                    "error",
                    "medium",
                    logger
                )
                return None

        return await execute_db_operation(operation)
    except Exception as e:
        await error_handler(
            f"Error getting temp variables: {str(e)}",
            "error",
            "medium",
            logger
        )
        return None
#---------------------------------- INSERT TEMP VARIABLES ----------------------------------
async def insert_temp_variables(user_id, logger, **kwargs):
    try:
        async def operation(conn):
            # Check if record exists
            check_query = """
                SELECT id FROM temp_variables WHERE user_id = $1
            """
            record_id = await conn.fetchval(check_query, user_id)

            if record_id:
                # Update existing record
                set_parts = []
                values = []
                for i, (key, value) in enumerate(kwargs.items(), start=2):
                    set_parts.append(f"{key} = ${i}")
                    values.append(value)

                query = f"""
                    UPDATE temp_variables 
                    SET {', '.join(set_parts)}, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                    RETURNING id
                """
                values.insert(0, user_id)
            else:
                # Insert new record
                columns = ['user_id'] + list(kwargs.keys())
                placeholders = ['$1'] + [f'${i+2}' for i in range(len(kwargs))]
                
                query = f"""
                    INSERT INTO temp_variables ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                    RETURNING id
                """
                values = [user_id] + list(kwargs.values())

            try:
                result = await conn.fetchval(query, *values)
                return result is not None
            except asyncpg.exceptions.QueryCanceledError:
                logger.error("Query timeout occurred while inserting temp variables")
                await error_handler(
                    "Database query timeout while inserting temp variables",
                    "error",
                    "medium",
                    logger
                )
                return False

        return await execute_db_operation(operation)
    except Exception as e:
        await error_handler(
            f"Error updating temp variables: {str(e)}",
            "error",
            "medium",
            logger
        )
        return False


#---------------------------------- DATABASE INITIALIZATION ----------------------------------
async def initialize_database(logger):
    try:
        # First, connect to the default 'postgres' database to check/create our database
        default_conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            database='postgres',  # Always connect to the default postgres database first
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        # Check if our database exists
        db_exists = await default_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", 
            DB_NAME
        )
        
        # Create database if it doesn't exist
        if not db_exists:
            logger.info(f"Creating database {DB_NAME}")
            # Need to escape the database name to prevent SQL injection
            await default_conn.execute(f'CREATE DATABASE "{DB_NAME}"')
            logger.info(f"Database {DB_NAME} created successfully")
        
        # Close the connection to the default database
        await default_conn.close()
        
        # Now connect to our database to create tables
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        if not conn:
            await error_handler(
                "Failed to get database connection for initialization",
                "error",
                "high",
                logger
            )
            return False

        # Create users table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                is_following BOOLEAN DEFAULT FALSE,
                location TEXT,
                gender TEXT,
                reels_search_count INTEGER DEFAULT 0,
                images_search_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create queries table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                query_id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                product_title TEXT,
                product_brand TEXT,
                product_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                feedback TEXT
            )
        """)

        # Create temp_variables table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS temp_variables (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                post_url TEXT,
                post_type TEXT,
                reel_caption TEXT,
                query_id INTEGER REFERENCES queries(query_id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create api_logs table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS vision_api_logs (
                id SERIAL PRIMARY KEY,
                endpoint TEXT,
                response_time INTEGER,
                user_id BIGINT,
                usage_tokens INTEGER,
                usage_cost DECIMAL(10,6),
                success BOOLEAN,
                frame_count INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create system_logs table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS error_logs (
                id SERIAL PRIMARY KEY,
                log_type TEXT,
                severity TEXT,
                message TEXT,
                details JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create dashboard_settings table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_settings (
                active_model TEXT DEFAULT 'gemini',
                save_training_data BOOLEAN DEFAULT FALSE
            )
        """)

        # Create indexes for better performance
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_queries_user_id ON queries(user_id);
            CREATE INDEX IF NOT EXISTS idx_error_logs_created_at ON error_logs(created_at);
            CREATE INDEX IF NOT EXISTS idx_vision_api_logs_user_id ON vision_api_logs(user_id);
            CREATE INDEX IF NOT EXISTS idx_vision_api_logs_created_at ON vision_api_logs(created_at);
        """)

        # Close the connection
        await conn.close()
        
        logger.info("Database tables initialized successfully")
        return True

    except Exception as e:
        await error_handler(
            f"Error initializing database: {str(e)}",
            "error",
            "high",
            logger
        )
        return False

#---------------------------------- GET DATABASE POOL STATS ----------------------------------
async def get_pool_stats():
    """Get statistics about the database connection pool"""
    if pool is None:
        return {
            "pool_exists": False,
            "pool_status": "Not initialized",
            "connections_total": 0,
            "connections_acquired": 0,
            "connections_free": 0
        }
    
    try:
        return {
            "pool_exists": True,
            "pool_status": "Healthy" if not pool._closing else "Closing",
            "connections_total": len(pool._holders),
            "connections_acquired": sum(1 for h in pool._holders if h._con is not None and h._in_use),
            "connections_free": sum(1 for h in pool._holders if h._con is not None and not h._in_use)
        }
    except Exception as e:
        logger.error(f"Error getting pool stats: {str(e)}")
        return {
            "pool_exists": True,
            "pool_status": "Error",
            "connections_total": -1,
            "connections_acquired": -1,
            "connections_free": -1,
            "error": str(e)
        }

#---------------------------------- PERIODIC HEALTH CHECK ----------------------------------
async def periodic_db_health_check():
    """Run periodic health checks on the database connection pool
    
    This function should be scheduled to run periodically, e.g.:
    
    import asyncio
    asyncio.create_task(periodic_db_health_check())
    """
    while True:
        try:
            is_healthy = await check_db_health()
            
            if not is_healthy:
                await error_handler(
                    "Database health check failed, attempting recovery...",
                    "error",
                    "critical",
                    logger
                )
                # Try to close and reinitialize the pool
                await close_db_pool()
                await init_db_pool()
        except Exception as e:
            logger.error(f"Error during periodic health check: {str(e)}")
        
        # Wait for 60 seconds before next check
        await asyncio.sleep(60)


#---------------------------------- GET ACTIVE MODEL ----------------------------------
async def get_active_model():
    async def operation(conn):
        row = await conn.fetchrow('SELECT active_model FROM dashboard_settings LIMIT 1')
        if row and row['active_model']:
            return row['active_model']
        return 'gemini'  # default
    return await execute_db_operation(operation)

#---------------------------------- IS SAVING TRAINING DATA ----------------------------------
async def is_saving_training_data():
    async def operation(conn):
        row = await conn.fetchrow('SELECT save_training_data FROM dashboard_settings LIMIT 1')
        if row and row['save_training_data']:
            return row['save_training_data']
        return False
    return await execute_db_operation(operation)