"""
Script to create the monthly_expenses table in the database (for Main Users)
Run this script to set up the database table for the monthly expenses feature
"""

import mysql.connector

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # Update with your MySQL password
    'database': 'expense_tracker'
}

def create_monthly_expenses_table():
    """Create monthly_expenses table for main users"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        # Create table
        create_table_query = """
        CREATE TABLE IF NOT EXISTS monthly_expenses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            expense_name VARCHAR(255) NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            month INT NOT NULL,
            year INT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_month_year (user_id, month, year)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        
        cursor.execute(create_table_query)
        connection.commit()
        
        print("✓ Successfully created monthly_expenses table for main users!")
        
        cursor.close()
        connection.close()
        
    except mysql.connector.Error as e:
        print(f"✗ Error creating table: {e}")
        if 'connection' in locals():
            connection.close()

if __name__ == "__main__":
    print("Creating monthly_expenses table for main users...")
    create_monthly_expenses_table()
