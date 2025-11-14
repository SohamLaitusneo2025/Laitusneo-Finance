"""
Script to create debt management tables for the banking system
Run this script to set up the debt management system database tables
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

def create_debt_management_tables():
    """Create all debt management tables"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        print("Creating debt management tables...")
        
        # Read and execute SQL file
        with open('create_debt_management_tables.sql', 'r', encoding='utf-8') as sql_file:
            sql_script = sql_file.read()
            
            # Split by semicolon and execute each statement
            statements = sql_script.split(';')
            for statement in statements:
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    try:
                        cursor.execute(statement)
                        print(f"✓ Executed: {statement[:50]}...")
                    except Error as e:
                        if "already exists" not in str(e).lower():
                            print(f"⚠ Warning: {e}")
        
        connection.commit()
        print("\n✓ Successfully created debt management tables!")
        
        cursor.close()
        connection.close()
        
    except FileNotFoundError:
        print("✗ Error: create_debt_management_tables.sql file not found!")
        print("Please make sure the SQL file is in the same directory as this script.")
    except Error as e:
        print(f"✗ Error creating tables: {e}")
        if 'connection' in locals():
            connection.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Debt Management System - Database Setup")
    print("=" * 60)
    create_debt_management_tables()
    print("=" * 60)

