"""
Script to create products table and related tables for inventory management
Run this script to set up the inventory management system
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

def create_products_table():
    """Create products table and related tables"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        print("Creating products table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `products` (
              `id` int(11) NOT NULL AUTO_INCREMENT,
              `user_id` int(11) NOT NULL,
              `product_name` varchar(255) NOT NULL,
              `product_code` varchar(100) DEFAULT NULL,
              `description` text DEFAULT NULL,
              `quantity` decimal(10,2) NOT NULL DEFAULT 0.00,
              `unit_price` decimal(10,2) NOT NULL DEFAULT 0.00,
              `sac_code` varchar(20) DEFAULT '998313',
              `cost_price` decimal(10,2) DEFAULT 0.00,
              `category` varchar(100) DEFAULT NULL,
              `sku` varchar(100) DEFAULT NULL,
              `unit` varchar(50) DEFAULT 'pcs',
              `status` enum('active','inactive') DEFAULT 'active',
              `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
              `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
              PRIMARY KEY (`id`),
              KEY `idx_user_id` (`user_id`),
              KEY `idx_product_code` (`product_code`),
              KEY `idx_status` (`status`),
              CONSTRAINT `fk_products_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
        """)
        
        print("Creating user_settings table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `user_settings` (
              `id` int(11) NOT NULL AUTO_INCREMENT,
              `user_id` int(11) NOT NULL,
              `low_stock_threshold` int(11) DEFAULT 5,
              `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
              `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
              PRIMARY KEY (`id`),
              UNIQUE KEY `unique_user_settings` (`user_id`),
              CONSTRAINT `fk_user_settings_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
        """)
        
        print("Adding product_id column to invoice_items table...")
        try:
            cursor.execute("ALTER TABLE `invoice_items` ADD COLUMN `product_id` int(11) DEFAULT NULL")
            print("Added product_id column to invoice_items")
        except Error as e:
            if "Duplicate column name" in str(e):
                print("product_id column already exists in invoice_items")
            else:
                raise
        
        try:
            cursor.execute("ALTER TABLE `invoice_items` ADD KEY `idx_product_id` (`product_id`)")
            print("Added index for product_id")
        except Error as e:
            if "Duplicate key name" in str(e):
                print("Index for product_id already exists")
            else:
                raise
        
        try:
            cursor.execute("""
                ALTER TABLE `invoice_items` 
                ADD CONSTRAINT `fk_invoice_items_product` 
                FOREIGN KEY (`product_id`) REFERENCES `products` (`id`) ON DELETE SET NULL
            """)
            print("Added foreign key constraint for product_id")
        except Error as e:
            if "Duplicate foreign key" in str(e) or "already exists" in str(e).lower():
                print("Foreign key constraint already exists")
            else:
                raise
        
        connection.commit()
        print("\n[SUCCESS] Successfully created products table and related structures!")
        print("[SUCCESS] Inventory management system is ready to use!")
        
    except Error as e:
        print(f"[ERROR] Error creating tables: {e}")
        if connection:
            connection.rollback()
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    print("=" * 50)
    print("Inventory Management System Setup")
    print("=" * 50)
    print()
    create_products_table()

