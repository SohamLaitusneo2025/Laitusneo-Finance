"""
Add new columns to monthly_expenses table
Run this script to add expense_type, payment_date (DATE), and payment_day (INT) columns as needed
"""

import mysql.connector
from mysql.connector import Error

def add_columns():
    connection = None
    cursor = None
    try:
        # Connect to database (matches local config used elsewhere)
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',  # Update with your MySQL password
            database='expense_tracker'
        )

        if not connection or not connection.is_connected():
            print("Failed to connect to database. Please verify network access and DB credentials.")
            return

        cursor = connection.cursor()

        # Check if columns already exist
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = 'expense_tracker'
              AND TABLE_NAME = 'monthly_expenses'
              AND COLUMN_NAME IN ('expense_type', 'payment_date', 'payment_day')
            """
        )
        existing_columns = [row[0] for row in cursor.fetchall()]

        if 'expense_type' in existing_columns and 'payment_date' in existing_columns and 'payment_day' in existing_columns:
            print("✓ Columns already exist!")
            return

        # Add expense_type column if it doesn't exist
        if 'expense_type' not in existing_columns:
            cursor.execute(
                """
                ALTER TABLE monthly_expenses
                ADD COLUMN expense_type VARCHAR(50) DEFAULT 'Fixed' AFTER user_id
                """
            )
            print("✓ Added expense_type column")

        # Add payment_date column if it doesn't exist
        if 'payment_date' not in existing_columns:
            cursor.execute(
                """
                ALTER TABLE monthly_expenses
                ADD COLUMN payment_date DATE AFTER month
                """
            )
            print("✓ Added payment_date column")

        # Add payment_day column if it doesn't exist
        if 'payment_day' not in existing_columns:
            # Prefer to add after payment_date if it exists, otherwise after month
            after_col = 'payment_date' if 'payment_date' in existing_columns else 'month'
            cursor.execute(
                f"""
                ALTER TABLE monthly_expenses
                ADD COLUMN payment_day INT AFTER {after_col}
                """
            )
            print("✓ Added payment_day column")

        connection.commit()
        print("\n✓ Successfully updated monthly_expenses table!")

    except Error as e:
        print(f"Error: {e}")
    finally:
        try:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
        except Exception:
            pass

if __name__ == "__main__":
    add_columns()
