import os
import psycopg2
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

def examine_extracted_data_table():
    """Connect to PostgreSQL and examine the extracted_data table"""
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
        
        # Get table information
        print("\n" + "="*60)
        print("TABLE: public.extracted_data")
        print("="*60)
        
        # Get column information
        cursor.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'extracted_data'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        print("\nColumns:")
        for column, data_type, nullable in columns:
            print(f"  - {column} ({data_type}) {'NULL' if nullable == 'YES' else 'NOT NULL'}")
        
        # Get row count
        cursor.execute("SELECT COUNT(*) FROM public.extracted_data;")
        row_count = cursor.fetchone()[0]
        print(f"\nTotal rows: {row_count}")
        
        # Get sample data if table is not empty
        if row_count > 0:
            print("\nSample data (first 5 rows):")
            cursor.execute("""
                SELECT id, document_id, company_name, file_name, index_name, result, created_at 
                FROM public.extracted_data 
                ORDER BY created_at DESC 
                LIMIT 5;
            """)
            
            rows = cursor.fetchall()
            for row in rows:
                print(f"\n  ID: {row[0]}")
                print(f"  Document ID: {row[1]}")
                print(f"  Company Name: {row[2]}")
                print(f"  File Name: {row[3]}")
                print(f"  Index Name: {row[4]}")
                print(f"  Result: {row[5]}")
                print(f"  Created At: {row[6]}")
                
            # Get distinct index names
            cursor.execute("SELECT DISTINCT index_name FROM public.extracted_data;")
            index_names = cursor.fetchall()
            print(f"\nDistinct index names ({len(index_names)}):")
            for (index_name,) in index_names:
                print(f"  - {index_name}")
                
            # Get count by index name
            cursor.execute("""
                SELECT index_name, COUNT(*) 
                FROM public.extracted_data 
                GROUP BY index_name 
                ORDER BY COUNT(*) DESC;
            """)
            index_counts = cursor.fetchall()
            print("\nCount by index name:")
            for index_name, count in index_counts:
                print(f"  - {index_name}: {count} records")
        
        # Close connections
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error connecting to database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    examine_extracted_data_table()