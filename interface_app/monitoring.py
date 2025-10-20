import os
import psycopg2
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Create and return a database connection"""
    try:
        # You'll need to set these environment variables with your cloud PostgreSQL credentials
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'survival_app'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'password'),
            port=os.getenv('DB_PORT', '5432')
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise

def init_tables():
    """Initialize the required tables if they don't exist"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create Sentiment Distribution table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS "Sentiment Distribution" (
                feedback_id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                senti_text VARCHAR(50) NOT NULL
            )
        """)
        
        # Create Positive Negative table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS "Positive Negative" (
                feedback_id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pos_neg VARCHAR(10) NOT NULL CHECK (pos_neg IN ('Positive', 'Negative'))
            )
        """)
        
        # Create Satisfaction Level table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS "Satisfaction Level" (
                feedback_id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                satis_levl INTEGER NOT NULL CHECK (satis_levl BETWEEN 1 AND 5)
            )
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info("Database tables initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing tables: {e}")
        raise

def insert_feedback(senti_text, pos_neg, satis_levl):
    """Insert feedback into all three tables - ONLY INSERT, NO UPDATE"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insert into Sentiment Distribution table (feedback_id and timestamp are auto-generated)
        cur.execute("""
            INSERT INTO "Sentiment Distribution" (senti_text) 
            VALUES (%s)
        """, (senti_text,))
        
        # Insert into Positive Negative table (feedback_id and timestamp are auto-generated)
        cur.execute("""
            INSERT INTO "Positive Negative" (pos_neg) 
            VALUES (%s)
        """, (pos_neg,))
        
        # Insert into Satisfaction Level table (feedback_id and timestamp are auto-generated)
        cur.execute("""
            INSERT INTO "Satisfaction Level" (satis_levl) 
            VALUES (%s)
        """, (satis_levl,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info("Feedback inserted successfully into all three tables")
        
    except Exception as e:
        logger.error(f"Error inserting feedback: {e}")
        raise

# Test function (optional)
def test_connection():
    """Test database connection and table creation"""
    try:
        init_tables()
        print("Database setup completed successfully")
        return True
    except Exception as e:
        print(f"Database setup failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()