"""
Migration script to ensure description column exists in products table
Run this script to add description column if it doesn't exist
"""

import mysql.connector
from mysql.connector import Error

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',  # Change this to your MySQL username
    'password': '',  # Change this to your MySQL password
    'database': 'expense_tracker'
}

def add_description_column():
    """Add description column to products table if it doesn't exist"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        print("Checking if description column exists in products table...")
        
        # Check if column exists
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = 'products' 
            AND COLUMN_NAME = 'description'
        """, (DB_CONFIG['database'],))
        
        column_exists = cursor.fetchone()
        
        if not column_exists:
            print("Description column not found. Adding description column...")
            cursor.execute("""
                ALTER TABLE `products` 
                ADD COLUMN `description` text DEFAULT NULL 
                AFTER `product_code`
            """)
            connection.commit()
            print("[SUCCESS] Description column added successfully!")
        else:
            print("Description column already exists in products table.")
        
        # Verify the column structure
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = 'products' 
            AND COLUMN_NAME = 'description'
        """, (DB_CONFIG['database'],))
        
        column_info = cursor.fetchone()
        if column_info:
            print(f"\nColumn Details:")
            print(f"  Name: {column_info[0]}")
            print(f"  Type: {column_info[1]}")
            print(f"  Nullable: {column_info[2]}")
            print(f"  Default: {column_info[3]}")
        
        print("\n[SUCCESS] Products table is ready with description field!")
        
    except Error as e:
        print(f"[ERROR] Error updating products table: {e}")
        if connection:
            connection.rollback()
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    print("=" * 50)
    print("Add Description Column to Products Table")
    print("=" * 50)
    print()
    add_description_column()

