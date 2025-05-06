import mysql.connector
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

logger = logging.getLogger("sound-api")

# Get database connection details from environment variables or use defaults
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "evaluations")

def init_database():
    """Initialize the database connection and create tables if they don't exist"""
    try:
        # Create a connection without database to check if it exists
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        # Create database if it doesn't exist
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        
        # Close connection
        cursor.close()
        conn.close()
        
        # Connect to the database
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()
        
        # Create evaluations table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id VARCHAR(255) NOT NULL,
            recording_date DATETIME NOT NULL,
            recording_name VARCHAR(255) NOT NULL,
            detection_class VARCHAR(100) NOT NULL,
            detection_confidence FLOAT NOT NULL,
            success BOOLEAN NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        logger.info("Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        return False
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_connection():
    """Get a connection to the database"""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return None

def add_evaluation(device_id, recording_date, recording_name, detection_class, detection_confidence, success):
    """Add a user evaluation to the database"""
    try:
        conn = get_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Insert the evaluation record
        query = """
        INSERT INTO evaluations
        (device_id, recording_date, recording_name, detection_class, detection_confidence, success)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            device_id,
            recording_date,
            recording_name,
            detection_class,
            detection_confidence,
            success
        ))
        
        # Commit the transaction
        conn.commit()
        
        logger.info(f"Added evaluation for {recording_name} with success={success}")
        return True
    except Exception as e:
        logger.error(f"Failed to add evaluation: {str(e)}")
        return False
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_evaluation_stats():
    """Get statistics about evaluations"""
    try:
        conn = get_connection()
        if not conn:
            return None
            
        cursor = conn.cursor(dictionary=True)
        
        # Get overall statistics
        cursor.execute("""
        SELECT 
            COUNT(*) as total_evaluations,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_evaluations,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as unsuccessful_evaluations,
            AVG(detection_confidence) as avg_confidence
        FROM evaluations
        """)
        
        overall_stats = cursor.fetchone()
        
        # Get stats by detection class
        cursor.execute("""
        SELECT 
            detection_class,
            COUNT(*) as total,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as unsuccessful,
            AVG(detection_confidence) as avg_confidence
        FROM evaluations
        GROUP BY detection_class
        ORDER BY total DESC
        """)
        
        class_stats = cursor.fetchall()
        
        return {
            "overall": overall_stats,
            "by_class": class_stats
        }
    except Exception as e:
        logger.error(f"Failed to get evaluation stats: {str(e)}")
        return None
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()