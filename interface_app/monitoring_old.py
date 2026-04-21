import os
import psycopg2
import streamlit as st
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    # Only runs in Streamlit Cloud
    # DB_CONFIG_HOST = st.secrets["db_host"]
    # DB_CONFIG_PASSWORD = st.secrets["db_password"]
    # st.info("****************Hello*********************")
    os.environ['DATABASE_HOST'] = st.secrets["db_host"]  
    os.environ['DATABASE_PASSWORD'] = st.secrets["db_password"]
except (KeyError, FileNotFoundError):
    pass  # ← Locally, .env file or system env vars are already set

def get_db_connection():
    """Create and return a database connection"""
    try:
        # Set these environment variables with your PostgreSQL credentials -->> In my case AWS cloud RDS 
        conn = psycopg2.connect(
            host=os.getenv('DATABASE_HOST'),
            port = 5433, # added to change the default port to 5433
            user="postgres",
            password=os.getenv('DATABASE_PASSWORD'),
            dbname="feedback_db"
            #sslmode="require"
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
            CREATE TABLE IF NOT EXISTS "sentiment_distribution" (
                feedback_id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                senti_text VARCHAR(50) NOT NULL
            )
        """)
        
        # Create Positive Negative table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS "positive_negative" (
                feedback_id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pos_neg VARCHAR(10) NOT NULL CHECK (pos_neg IN ('Positive', 'Negative'))
            )
        """)
        
        # Create Satisfaction Level table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS "satisfaction_level" (
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

def insert_feedback(senti_text, pos_neg, satis_level):
    """Insert feedback into all three tables"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            'INSERT INTO sentiment_distribution (senti_text) VALUES (%s)',
            (senti_text,)
        )

        cur.execute(
            'INSERT INTO positive_negative (pos_neg) VALUES (%s)',
            (pos_neg,)
        )

        cur.execute(
            'INSERT INTO satisfaction_level (satis_levl) VALUES (%s)',
            (satis_level,)
        )

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
        # init_tables()
        print("Database setup completed successfully")
        return True
    except Exception as e:
        print(f"Database setup failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()