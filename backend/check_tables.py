import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_database_tables():
    """Connect to PostgreSQL and list all tables"""
    try:
        # Database connection parameters
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        database = os.getenv('DB_NAME', 'postgres')
        user = os.getenv('DB_USER', 'postgres')
        password = os.getenv('DB_PASSWORD')
        
        print(f"Connecting to PostgreSQL database:")
        print(f"  Host: {host}")
        print(f"  Port: {port}")
        print(f"  Database: {database}")
        print(f"  User: {user}")
        
        # Connect to the database
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        
        cursor = conn.cursor()
        
        # Query to get all tables
        cursor.execute("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_type = 'BASE TABLE' 
            AND table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name;
        """)
        
        tables = cursor.fetchall()
        
        if tables:
            print("\nTables in the database:")
            print("-" * 50)
            for schema, table in tables:
                print(f"{schema}.{table}")
                
                # Get column information for each table
                cursor.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position;
                """, (schema, table))
                
                columns = cursor.fetchall()
                if columns:
                    print("  Columns:")
                    for column, data_type in columns:
                        print(f"    - {column} ({data_type})")
                print()
        else:
            print("\nNo tables found in the database.")
            
        # Close connections
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error connecting to database: {e}")

if __name__ == "__main__":
    check_database_tables()