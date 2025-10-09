
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for, send_from_directory, session, Response, make_response
from flask_cors import CORS
from flask_restx import Api, Resource, fields, Namespace
from functools import wraps
import mysql.connector
from mysql.connector import Error
import os
import csv
import json
from datetime import datetime, date, timezone, timedelta
import pytz
import uuid
import random
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import pandas as pd
import io
import mimetypes
import shutil
# PDF processing imports
try:
    import PyPDF2
    import fitz  # PyMuPDF for advanced PDF manipulation
    from PIL import Image, ImageDraw, ImageFont
    PDF_PROCESSING_AVAILABLE = True
except ImportError:
    PDF_PROCESSING_AVAILABLE = False

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
CORS(app, supports_credentials=True)

# Configure Swagger/OpenAPI documentation
api = Api(
    app,
    version='1.0',
    title='Laitusneo Track API',
    description='A comprehensive expense tracking and invoicing system API',
    doc='/docs/',  # Swagger UI will be available at /docs/
    prefix='/api',
    authorizations={
        'Bearer': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Add a JWT token to the header with ** Bearer &lt;JWT&gt; ** token to authorize'
        }
    },
    security='Bearer'
)

# Create API namespaces for better organization
auth_ns = Namespace('auth', description='Authentication operations')
expenses_ns = Namespace('expenses', description='Expense management')
invoices_ns = Namespace('invoices', description='Invoice management')
transactions_ns = Namespace('transactions', description='Transaction management')
admin_ns = Namespace('admin', description='Admin operations')
sub_users_ns = Namespace('sub-users', description='Sub-user management')
dashboard_ns = Namespace('dashboard', description='Dashboard and statistics')
profile_ns = Namespace('profile', description='User profile management')
settings_ns = Namespace('settings', description='User settings')

# Add namespaces to API
api.add_namespace(auth_ns)
api.add_namespace(expenses_ns)
api.add_namespace(invoices_ns)
api.add_namespace(transactions_ns)
api.add_namespace(admin_ns)
api.add_namespace(sub_users_ns)
api.add_namespace(dashboard_ns)
api.add_namespace(profile_ns)
api.add_namespace(settings_ns)

# Define common data models for documentation
user_model = api.model('User', {
    'id': fields.Integer(required=True, description='User ID'),
    'username': fields.String(required=True, description='Username'),
    'email': fields.String(required=True, description='User email'),
    'first_name': fields.String(description='First name'),
    'last_name': fields.String(description='Last name'),
    'created_at': fields.DateTime(description='Account creation date')
})

expense_model = api.model('Expense', {
    'id': fields.Integer(required=True, description='Expense ID'),
    'amount': fields.Float(required=True, description='Expense amount'),
    'category': fields.String(required=True, description='Expense category'),
    'description': fields.String(description='Expense description'),
    'date': fields.Date(required=True, description='Expense date'),
    'receipt_path': fields.String(description='Path to receipt file'),
    'created_at': fields.DateTime(description='Creation timestamp')
})

invoice_model = api.model('Invoice', {
    'id': fields.Integer(required=True, description='Invoice ID'),
    'invoice_number': fields.String(required=True, description='Invoice number'),
    'client_name': fields.String(required=True, description='Client name'),
    'amount': fields.Float(required=True, description='Invoice amount'),
    'status': fields.String(required=True, description='Invoice status'),
    'due_date': fields.Date(required=True, description='Due date'),
    'created_at': fields.DateTime(description='Creation timestamp')
})

transaction_model = api.model('Transaction', {
    'id': fields.Integer(required=True, description='Transaction ID'),
    'type': fields.String(required=True, description='Transaction type'),
    'amount': fields.Float(required=True, description='Transaction amount'),
    'description': fields.String(description='Transaction description'),
    'date': fields.Date(required=True, description='Transaction date'),
    'created_at': fields.DateTime(description='Creation timestamp')
})

# Configuration
UPLOAD_FOLDER = 'uploads'
EXPORT_FOLDER = 'exports'
TEMPLATE_FOLDER = 'uploads/templates'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}
ALLOWED_PDF_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXPORT_FOLDER'] = EXPORT_FOLDER
app.config['TEMPLATE_FOLDER'] = TEMPLATE_FOLDER

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXPORT_FOLDER, exist_ok=True)
os.makedirs(TEMPLATE_FOLDER, exist_ok=True)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',  # Change this to your MySQL username
    'password': '',  # Change this to your MySQL password
    'database': 'expense_tracker'
}

def get_db_connection():
    """Get database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to database: {e}")
        return None

def create_sub_users_table():
    """Create sub_users table if it doesn't exist"""
    try:
        print("Creating sub_users table...")
        connection = get_db_connection()
        if not connection:
            print("Failed to get database connection")
            return False
        
        cursor = connection.cursor()
        
        # Create sub_users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sub_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sub_user_id VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                email VARCHAR(255),
                created_by INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
                INDEX idx_sub_user_id (sub_user_id),
                INDEX idx_created_by (created_by)
            )
        """)
        
        # Add approval tracking columns to invoices table if they don't exist
        try:
            cursor.execute("ALTER TABLE invoices ADD COLUMN approved_at TIMESTAMP NULL")
            print("Added approved_at column to invoices table")
        except:
            pass  # Column already exists
            
        try:
            cursor.execute("ALTER TABLE invoices ADD COLUMN approved_by INT NULL")
            print("Added approved_by column to invoices table")
        except:
            pass  # Column already exists
            
        try:
            cursor.execute("ALTER TABLE invoices ADD COLUMN approved_bank_account_id INT NULL")
            print("Added approved_bank_account_id column to invoices table")
        except:
            pass  # Column already exists
            
        try:
            cursor.execute("ALTER TABLE invoices ADD COLUMN approved_payment_method VARCHAR(20) NULL")
            print("Added approved_payment_method column to invoices table")
        except:
            pass  # Column already exists
        
        # Create sub_user_requests table for expense/transaction requests
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sub_user_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sub_user_id INT NOT NULL,
                request_type ENUM('expense', 'transaction', 'invoice') NOT NULL,
                request_data JSON NOT NULL,
                status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                reviewed_by INT,
                reviewed_at TIMESTAMP NULL,
                notes TEXT,
                FOREIGN KEY (sub_user_id) REFERENCES sub_users(id) ON DELETE CASCADE,
                FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
                INDEX idx_sub_user_id (sub_user_id),
                INDEX idx_status (status),
                INDEX idx_request_type (request_type)
            )
        """)
        
        # Add created_by_sub_user column to expenses table if it doesn't exist
        try:
            cursor.execute("SHOW COLUMNS FROM expenses LIKE 'created_by_sub_user'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE expenses ADD COLUMN created_by_sub_user INT NULL")
                cursor.execute("ALTER TABLE expenses ADD FOREIGN KEY (created_by_sub_user) REFERENCES sub_users(id) ON DELETE SET NULL")
        except Exception as e:
            print(f"Error adding created_by_sub_user to expenses: {e}")
        
        # Add created_by_sub_user column to transactions table if it doesn't exist
        try:
            cursor.execute("SHOW COLUMNS FROM transactions LIKE 'created_by_sub_user'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE transactions ADD COLUMN created_by_sub_user INT NULL")
                cursor.execute("ALTER TABLE transactions ADD FOREIGN KEY (created_by_sub_user) REFERENCES sub_users(id) ON DELETE SET NULL")
        except Exception as e:
            print(f"Error adding created_by_sub_user to transactions: {e}")
        
        # Create sub_user_bank_accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sub_user_bank_accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sub_user_id INT NOT NULL,
                bank_name VARCHAR(255) NOT NULL,
                account_number VARCHAR(50) NOT NULL,
                ifsc_code VARCHAR(20) NOT NULL,
                account_holder_name VARCHAR(255) NOT NULL,
                upi_id VARCHAR(255),
                phone_number VARCHAR(20),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (sub_user_id) REFERENCES sub_users(id) ON DELETE CASCADE,
                UNIQUE KEY unique_sub_user_bank (sub_user_id),
                INDEX idx_sub_user_id (sub_user_id)
            )
        """)
        
        connection.commit()
        cursor.close()
        connection.close()
        print("Sub_users table created successfully")
        return True
        
    except Error as e:
        print(f"Error creating sub_users table: {e}")
        return False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_pdf_file(filename):
    """Check if file is a valid PDF template"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_PDF_EXTENSIONS

def generate_unique_id(record_type='TXN'):
    """Generate unique ID for any record type"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))
    return f"{record_type}-{timestamp}-{random_suffix}"

def generate_invoice_number(user_id, invoice_type='out'):
    """Generate unique invoice number for user based on invoice type"""
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            # Different prefixes for IN and OUT invoices
            if invoice_type == 'in':
                prefix = "LNTS"
            else:
                prefix = "LNTP"
            
            print(f"DEBUG: Generating {invoice_type} invoice with prefix: {prefix}")
            
            # Find the highest invoice number for this user and type
            cursor.execute(
                "SELECT MAX(CAST(SUBSTRING(invoice_number, LENGTH(%s) + 1) AS UNSIGNED)) FROM invoices WHERE user_id = %s AND invoice_number LIKE %s",
                (prefix, user_id, f"{prefix}%")
            )
            result = cursor.fetchone()[0]
            
            # If no invoices exist for this user and type, start with 001
            next_number = 1 if result is None else result + 1
            
            print(f"DEBUG: Next number for {prefix}: {next_number}")
            
            invoice_number = f"{prefix}{next_number:03d}"
            
            # Verify that this invoice number doesn't already exist
            cursor.execute(
                "SELECT COUNT(*) FROM invoices WHERE user_id = %s AND invoice_number = %s",
                (user_id, invoice_number)
            )
            exists = cursor.fetchone()[0] > 0
            
            # If it exists, try the next number (with safety limit)
            max_attempts = 1000  # Prevent infinite loops
            attempts = 0
            while exists and attempts < max_attempts:
                next_number += 1
                invoice_number = f"{prefix}{next_number:03d}"
                cursor.execute(
                    "SELECT COUNT(*) FROM invoices WHERE user_id = %s AND invoice_number = %s",
                    (user_id, invoice_number)
                )
                exists = cursor.fetchone()[0] > 0
                attempts += 1
            
            if attempts >= max_attempts:
                print(f"WARNING: Could not find unique invoice number after {max_attempts} attempts")
                # Fall back to timestamp-based number
                timestamp = datetime.now().strftime("%H%M%S")
                invoice_number = f"{prefix}{timestamp}"
                
            cursor.close()
            connection.close()
            return invoice_number
        except Exception as e:
            print(f"Error generating invoice number: {e}")
            cursor.close()
            connection.close()
            
    # Fallback pattern with timestamp to ensure uniqueness
    timestamp = datetime.now().strftime("%H%M%S")
    if invoice_type == 'in':
        return f"LNTS{timestamp}"
    else:
        return f"LNTP{timestamp}"

def update_bank_balance(bank_account_id, amount, transaction_type, user_id):
    """Update bank account balance based on transaction type"""
    try:
        connection = get_db_connection()
        if not connection:
            print("Database connection failed for bank balance update")
            return False
        
        cursor = connection.cursor()
        
        if transaction_type == 'credit':
            # Credit: Add money to bank account
            cursor.execute("""
                UPDATE bank_accounts 
                SET current_balance = current_balance + %s 
                WHERE id = %s AND user_id = %s
            """, (amount, bank_account_id, user_id))
            print(f"Added ₹{amount} to bank account {bank_account_id}")
        else:
            # Debit: Deduct money from bank account
            cursor.execute("""
                UPDATE bank_accounts 
                SET current_balance = current_balance - %s 
                WHERE id = %s AND user_id = %s
            """, (amount, bank_account_id, user_id))
            print(f"Deducted ₹{amount} from bank account {bank_account_id}")
        
        if cursor.rowcount == 0:
            print(f"Warning: Could not update bank account {bank_account_id} balance")
            return False
        
        connection.commit()
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        print(f"Error updating bank balance: {e}")
        return False

def create_invoice_transaction(invoice_id, invoice_type, total_amount, invoice_number, client_name, bank_account_id=None, cursor=None, connection=None, user_id=None):
    """Create automatic transaction for invoice and update bank balance"""
    try:
        # Use provided cursor/connection or create new ones
        if cursor is None or connection is None:
            connection = get_db_connection()
            if not connection:
                print("Database connection failed for invoice transaction")
                return None
            cursor = connection.cursor()
            should_close_connection = True
        else:
            should_close_connection = False
        
        # Get user_id from parameter or session
        if user_id is None:
            user_id = session.get('user_id')
            if not user_id:
                print("Error: No user_id available for invoice transaction")
                return None
        
        # First, ensure the transactions table has the required columns
        try:
            cursor.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source VARCHAR(50)")
            cursor.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source_id INT")
            cursor.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) DEFAULT 'cash'")
            cursor.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS bank_account_id INT NULL")
            connection.commit()
        except Exception as e:
            print(f"Warning: Could not add columns to transactions table: {e}")
        
        # Determine transaction type based on invoice type
        if invoice_type == 'in':
            transaction_type = 'credit'  # Money coming in
            title = invoice_number  # Just the invoice number
            description = f"Invoice {invoice_number}"
            payment_method = 'online' if bank_account_id else 'cash'
        else:
            transaction_type = 'debit'   # Money going out
            title = invoice_number  # Just the invoice number
            description = f"Invoice {invoice_number}"
            payment_method = 'online' if bank_account_id else 'cash'
        
        # Get the invoice's unique ID to use for the transaction
        cursor.execute("SELECT unique_id FROM invoices WHERE id = %s", (invoice_id,))
        invoice_unique_id = cursor.fetchone()[0]
        
        # If invoice unique_id is empty, use invoice_number as fallback
        if not invoice_unique_id:
            cursor.execute("SELECT invoice_number FROM invoices WHERE id = %s", (invoice_id,))
            invoice_unique_id = cursor.fetchone()[0]
        
        # Create transaction with the SAME unique ID as the invoice
        cursor.execute("""
            INSERT INTO transactions (user_id, unique_id, title, description, purpose, amount, transaction_type, 
                                    category, payment_method, transaction_date, source, source_id, bank_account_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            invoice_unique_id,  # Use the SAME unique ID as the invoice
            title,
            description,
            'Invoice Payment',
            total_amount,
            transaction_type,
            'Invoice',
            payment_method,
            datetime.now().date(),
            'invoice',
            invoice_id,
            bank_account_id
        ))
        
        transaction_id = cursor.lastrowid
        
        # Update balances based on payment method
        print(f"Updating balances for invoice transaction: bank_account_id={bank_account_id}, payment_method={payment_method}, transaction_type={transaction_type}, amount={total_amount}")
        if bank_account_id and payment_method == 'online':
            result = update_bank_balance(bank_account_id, total_amount, transaction_type, user_id)
            print(f"Bank balance update result: {result}")
        elif payment_method == 'cash':
            result = update_cash_balance_transaction(total_amount, transaction_type, user_id)
            print(f"Cash balance update result: {result}")
        else:
            print(f"No balance update needed - bank_account_id: {bank_account_id}, payment_method: {payment_method}")
        
        connection.commit()
        
        # Only close connection if we created it
        if should_close_connection:
            cursor.close()
            connection.close()
        
        print(f"Created {transaction_type} transaction for invoice {invoice_number}")
        return transaction_id
        
    except Exception as e:
        print(f"Error creating invoice transaction: {e}")
        # Only close connection if we created it
        if should_close_connection and 'connection' in locals():
            try:
                cursor.close()
                connection.close()
            except:
                pass
        return None

def extract_text_positions(pdf_path):
    """Extract text positions from PDF"""
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]  # Get first page
        text_instances = page.get_text("dict")
        
        positions = []
        for block in text_instances["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        positions.append({
                            'text': span['text'],
                            'x': span['bbox'][0],
                            'y': span['bbox'][1],
                            'font_size': span['size'],
                            'font': span['font']
                        })
        
        doc.close()
        return positions
    except Exception as e:
        print(f"Error extracting PDF text positions: {e}")
        return []

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Initialize sub_users table
@app.route('/init-sub-users')
def init_sub_users_table():
    """Initialize sub_users table"""
    try:
        success = create_sub_users_table()
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Sub users table created successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to create sub users table'
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Test database connectivity route
@app.route('/test-db')
def test_database_connection():
    """Test database connectivity and show table structure"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({
                'status': 'error',
                'message': 'Database connection failed',
                'config': {
                    'host': DB_CONFIG['host'],
                    'user': DB_CONFIG['user'],
                    'database': DB_CONFIG['database']
                }
            }), 500
        
        cursor = connection.cursor()
        
        # Test basic query
        cursor.execute("SELECT 1 as test")
        test_result = cursor.fetchone()
        
        # Check if tables exist
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        # Check users table specifically
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        # Check invoices table
        cursor.execute("SELECT COUNT(*) FROM invoices")
        invoice_count = cursor.fetchone()[0]
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'status': 'success',
            'message': 'Database connection successful',
            'test_query': test_result,
            'tables': [table[0] for table in tables],
            'user_count': user_count,
            'invoice_count': invoice_count
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'error_type': type(e).__name__
        }), 500

# Test session/authentication status
@app.route('/test-session')
def test_session_status():
    """Test current session status"""
    return jsonify({
        'logged_in': 'user_id' in session,
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'session_keys': list(session.keys())
    })

@app.route('/debug-invoices')
def debug_invoices():
    """Debug endpoint to test invoice data retrieval"""
    if not session.get('user_id'):
        return jsonify({'error': 'Not logged in', 'redirect': '/login'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Test basic invoice query
        user_id = session['user_id']
        print(f"DEBUG: Testing invoices for user_id: {user_id}")
        
        cursor.execute("""SELECT COUNT(*) as count FROM invoices WHERE user_id = %s""", (user_id,))
        count_result = cursor.fetchone()
        print(f"DEBUG: Invoice count for user {user_id}: {count_result['count']}")
        
        cursor.execute("""
            SELECT id, invoice_number, client_name, total_amount, status, invoice_date, due_date, created_at
            FROM invoices 
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 5
        """, (user_id,))
        sample_invoices = cursor.fetchall()
        
        # Convert dates to strings for JSON serialization
        for invoice in sample_invoices:
            if invoice['invoice_date']:
                invoice['invoice_date'] = invoice['invoice_date'].isoformat()
            if invoice['due_date']:
                invoice['due_date'] = invoice['due_date'].isoformat()
            if invoice['created_at']:
                invoice['created_at'] = invoice['created_at'].isoformat()
        
        # Also test the exact query used by the API endpoint
        cursor.execute("""
            SELECT * FROM invoices 
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        all_invoices = cursor.fetchall()
        
        # Convert dates for all invoices
        for invoice in all_invoices:
            if invoice['invoice_date']:
                invoice['invoice_date'] = invoice['invoice_date'].isoformat()
            if invoice['due_date']:
                invoice['due_date'] = invoice['due_date'].isoformat()
            if invoice['created_at']:
                invoice['created_at'] = invoice['created_at'].isoformat()
            if invoice['updated_at']:
                invoice['updated_at'] = invoice['updated_at'].isoformat()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'total_invoices': count_result['count'],
            'sample_invoices': sample_invoices,
            'all_invoices': all_invoices,
            'message': f'Found {len(all_invoices)} invoices for user {user_id}'
        })
        
    except Exception as e:
        print(f"DEBUG: Error in debug_invoices: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/test-api-direct')
@login_required
def test_api_direct():
    """Test the actual /api/invoices endpoint behavior"""
    try:
        # Call the actual get_invoices function directly
        from flask import request as flask_request
        
        # Temporarily override request args for search
        original_args = flask_request.args
        
        # Test the actual API endpoint logic
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed', 'step': 'connection'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        user_id = session['user_id']
        print(f"DIRECT TEST: Testing invoices for user_id: {user_id}")
        
        # Use the exact same query as the API endpoint
        cursor.execute("""
            SELECT * FROM invoices 
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        
        invoices = cursor.fetchall()
        print(f"DIRECT TEST: Found {len(invoices)} invoices")
        
        # Convert date objects to strings (same as API endpoint)
        for invoice in invoices:
            if invoice['invoice_date']:
                invoice['invoice_date'] = invoice['invoice_date'].isoformat()
            if invoice['due_date']:
                invoice['due_date'] = invoice['due_date'].isoformat()
            if invoice['created_at']:
                invoice['created_at'] = invoice['created_at'].isoformat()
            if invoice['updated_at']:
                invoice['updated_at'] = invoice['updated_at'].isoformat()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'method': 'direct_test',
            'user_id': user_id,
            'invoice_count': len(invoices),
            'invoices': invoices,
            'message': f'Direct API test successful - {len(invoices)} invoices found'
        })
        
    except Exception as e:
        print(f"DIRECT TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'step': 'execution'}), 500

def get_current_user():
    """Get current user from session"""
    if 'user_id' not in session:
        return None
    
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, username, email, first_name, last_name FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.close()
        connection.close()
        return user
    return None

def get_india_time():
    """Get current time in India timezone"""
    india_tz = pytz.timezone('Asia/Kolkata')
    return datetime.now(india_tz)

def format_india_time(dt):
    """Format datetime to India timezone string"""
    if dt is None:
        return None
    try:
        india_tz = pytz.timezone('Asia/Kolkata')
        if dt.tzinfo is None:
            # If datetime is naive, assume it's in UTC
            dt = pytz.utc.localize(dt)
        return dt.astimezone(india_tz).strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        # Fallback to simple formatting if timezone conversion fails
        if isinstance(dt, str):
            return dt
        return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else None

# Admin Authentication and Authorization
def admin_required(f):
    """Decorator to require admin login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please log in as admin to access this page.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_admin():
    """Get current admin from session"""
    if 'admin_id' not in session:
        return None
    
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT id, username, email, first_name, last_name, role FROM admin_users WHERE id = %s", (session['admin_id'],))
        admin = cursor.fetchone()
        cursor.close()
        connection.close()
        return admin
    return None

def log_audit_event(user_id=None, admin_id=None, action='', table_name=None, record_id=None, old_values=None, new_values=None):
    """Log audit events"""
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        india_time = get_india_time()
        cursor.execute("""
            INSERT INTO audit_logs (user_id, admin_id, action, table_name, record_id, old_values, new_values, ip_address, user_agent, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, admin_id, action, table_name, record_id,
            json.dumps(old_values) if old_values else None,
            json.dumps(new_values) if new_values else None,
            request.remote_addr,
            request.headers.get('User-Agent', ''),
            india_time
        ))
        connection.commit()
        cursor.close()
        connection.close()

def track_user_session(user_id, session_id):
    """Track user session"""
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        india_time = get_india_time()
        cursor.execute("""
            INSERT INTO user_sessions (user_id, session_id, ip_address, user_agent, login_time, last_activity)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, session_id, request.remote_addr, request.headers.get('User-Agent', ''), india_time, india_time))
        connection.commit()
        cursor.close()
        connection.close()

def update_user_last_login(user_id):
    """Update user's last login time"""
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        india_time = get_india_time()
        cursor.execute("UPDATE users SET last_login = %s WHERE id = %s", (india_time, user_id))
        connection.commit()
        cursor.close()
        connection.close()

def update_admin_last_login(admin_id):
    """Update admin's last login time"""
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        india_time = get_india_time()
        cursor.execute("UPDATE admin_users SET last_login = %s WHERE id = %s", (india_time, admin_id))
        connection.commit()
        cursor.close()
        connection.close()



# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember')
        
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                
                if remember:
                    session.permanent = True
                
                # Track session and update last login
                session_id = str(uuid.uuid4())
                track_user_session(user['id'], session_id)
                update_user_last_login(user['id'])
                
                # Log audit event
                log_audit_event(user_id=user['id'], action='LOGIN', table_name='users')
                
                flash('Successfully logged in!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid email or password.', 'error')
        else:
            flash('Database connection error.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('register.html')
        
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            
            # Check if username or email already exists
            cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
            existing_user = cursor.fetchone()
            
            if existing_user:
                flash('Username or email already exists.', 'error')
                cursor.close()
                connection.close()
                return render_template('register.html')
            
            # Create new user
            password_hash = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, first_name, last_name) VALUES (%s, %s, %s, %s, %s)",
                (username, email, password_hash, first_name, last_name)
            )
            connection.commit()
            user_id = cursor.lastrowid
            
            # Create default company settings for the user
            cursor.execute(
                "INSERT INTO company_settings (user_id, company_name, company_address, company_phone, company_email, tax_number) VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, 'Your Company Name', 'Your Company Address', '+1-234-567-8900', 'info@company.com', 'TAX123456789')
            )
            connection.commit()
            
            cursor.close()
            connection.close()
            
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Database connection error.', 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', current_user=get_current_user())

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', current_user=get_current_user())

# Main Routes
@app.route('/')
@app.route('/index')
@login_required
def index():
    return render_template('index.html', current_user=get_current_user())

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', current_user=get_current_user())

@app.route('/expenses')
@login_required
def expenses():
    return render_template('expenses.html', current_user=get_current_user())

@app.route('/transactions')
@login_required
def transactions():
    return render_template('transactions.html', current_user=get_current_user())

@app.route('/invoices')
@login_required
def invoices():
    return render_template('invoices.html', current_user=get_current_user())

@app.route('/sub-users')
@login_required
def sub_users():
    return render_template('sub_users.html', current_user=get_current_user())

# File serving route
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            # Get file mimetype
            mimetype = mimetypes.guess_type(file_path)[0]
            return send_from_directory(app.config['UPLOAD_FOLDER'], filename, mimetype=mimetype)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# API Routes for Expenses
@auth_ns.route('/check')
class AuthCheck(Resource):
    @api.doc('check_authentication')
    @api.response(200, 'Authentication status checked successfully')
    @api.response(401, 'User not authenticated')
    def get(self):
        """Check if user is authenticated"""
        if 'user_id' in session:
            return {'authenticated': True, 'user_id': session['user_id']}, 200
        else:
            return {'authenticated': False}, 401

# Keep the original route for backward compatibility
@app.route('/api/auth/check')
def check_auth():
    """Check if user is authenticated"""
    if 'user_id' in session:
        return jsonify({'authenticated': True, 'user_id': session['user_id']})
    else:
        return jsonify({'authenticated': False}), 401

@expenses_ns.route('/')
class ExpenseList(Resource):
    @api.doc('get_expenses', security='Bearer')
    @api.marshal_list_with(expense_model)
    @api.response(200, 'Expenses retrieved successfully')
    @api.response(401, 'Authentication required')
    @api.response(500, 'Database connection failed')
    def get(self):
        """Get all expenses for the authenticated user"""
        if 'user_id' not in session:
            return {'error': 'Authentication required'}, 401
            
        connection = get_db_connection()
        if not connection:
            return {'error': 'Database connection failed'}, 500
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT e.*, 
                   su.sub_user_id, CONCAT(su.first_name, ' ', su.last_name) as sub_user_name
            FROM expenses e
            LEFT JOIN sub_users su ON e.created_by_sub_user = su.id
            WHERE e.user_id = %s
            ORDER BY e.created_at DESC
        """, (session['user_id'],))
        expenses = cursor.fetchall()
        
        # Convert date objects to strings
        for expense in expenses:
            if expense['expense_date']:
                expense['expense_date'] = expense['expense_date'].isoformat()
            if expense['created_at']:
                expense['created_at'] = expense['created_at'].isoformat()
            if expense['updated_at']:
                expense['updated_at'] = expense['updated_at'].isoformat()
        
        cursor.close()
        connection.close()
        return expenses, 200

    @api.doc('create_expense', security='Bearer')
    @api.expect(api.parser().add_argument('amount', type=float, required=True, help='Expense amount')
                          .add_argument('category', type=str, required=True, help='Expense category')
                          .add_argument('description', type=str, help='Expense description')
                          .add_argument('expense_date', type=str, required=True, help='Expense date (YYYY-MM-DD)')
                          .add_argument('bill_file', type='file', location='files', help='Receipt/bill file'))
    @api.response(200, 'Expense created successfully')
    @api.response(400, 'Invalid input data')
    @api.response(401, 'Authentication required')
    @api.response(500, 'Database connection failed')
    def post(self):
        """Create a new expense"""
        # This will use the existing add_expense logic
        return add_expense()

# Keep the original route for backward compatibility
@app.route('/api/expenses', methods=['GET'])
@login_required
def get_expenses():
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*, 
               su.sub_user_id, CONCAT(su.first_name, ' ', su.last_name) as sub_user_name
        FROM expenses e
        LEFT JOIN sub_users su ON e.created_by_sub_user = su.id
        WHERE e.user_id = %s
        ORDER BY e.created_at DESC
    """, (session['user_id'],))
    expenses = cursor.fetchall()
    
    # Convert date objects to strings
    for expense in expenses:
        if expense['expense_date']:
            expense['expense_date'] = expense['expense_date'].isoformat()
        if expense['created_at']:
            expense['created_at'] = expense['created_at'].isoformat()
        if expense['updated_at']:
            expense['updated_at'] = expense['updated_at'].isoformat()
    
    cursor.close()
    connection.close()
    return jsonify(expenses)

@app.route('/api/expenses', methods=['POST'])
@login_required
def add_expense():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in. Please log in and try again.'}), 400
        
        data = request.form.to_dict()
        print(f"DEBUG: Received expense data: {data}")
        file = request.files.get('bill_file')
        
        filename = None
        if file and file.filename and allowed_file(file.filename):
            filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Ensure required columns exist in expenses table
        try:
            cursor.execute("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS payment_type ENUM('invoice', 'cash') DEFAULT 'cash'")
            cursor.execute("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS payment_method ENUM('cash', 'online') DEFAULT 'cash'")
            cursor.execute("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS bank_account_id INT NULL")
            cursor.execute("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS unique_id VARCHAR(50)")
            cursor.execute("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS purpose VARCHAR(255)")
            connection.commit()
        except Exception as e:
            print(f"Warning: Could not add columns to expenses table: {e}")
            # Continue with existing structure
        
        purpose_value = data.get('purpose', data.get('title', ''))
        
        # Check the foreign key constraints on expenses table
        try:
            cursor.execute("""
                SELECT 
                    CONSTRAINT_NAME,
                    COLUMN_NAME,
                    REFERENCED_TABLE_NAME,
                    REFERENCED_COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE 
                WHERE TABLE_SCHEMA = 'expense_tracker' 
                AND TABLE_NAME = 'expenses' 
                AND REFERENCED_TABLE_NAME IS NOT NULL
            """)
            foreign_keys = cursor.fetchall()
            print(f"DEBUG: Foreign key constraints on expenses table: {foreign_keys}")
            
            # If there's a foreign key constraint pointing to user_banks, try to fix it
            for fk in foreign_keys:
                if fk[2] == 'user_banks' and fk[1] == 'bank_account_id':
                    print(f"DEBUG: Found problematic foreign key: {fk}")
                    try:
                        # Drop the problematic foreign key
                        cursor.execute(f"ALTER TABLE expenses DROP FOREIGN KEY {fk[0]}")
                        print(f"DEBUG: Dropped foreign key constraint: {fk[0]}")
                        
                        # Add new foreign key constraint pointing to bank_accounts
                        cursor.execute("""
                            ALTER TABLE expenses 
                            ADD CONSTRAINT fk_expenses_bank_accounts 
                            FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE SET NULL
                        """)
                        print("DEBUG: Added new foreign key constraint to bank_accounts")
                        connection.commit()
                    except Exception as fk_error:
                        print(f"Warning: Could not fix foreign key constraint: {fk_error}")
        except Exception as e:
            print(f"Warning: Could not check foreign keys: {e}")
        
        # Try to update expense_type enum if it exists
        try:
            cursor.execute("ALTER TABLE expenses MODIFY COLUMN expense_type ENUM('completed', 'upcoming') NOT NULL DEFAULT 'completed'")
        except:
            # If expense_type column doesn't exist, create it
            cursor.execute("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS expense_type ENUM('completed', 'upcoming') NOT NULL DEFAULT 'completed'")
        
        # Validate required fields
        if not data.get('amount') or data.get('amount').strip() == '':
            return jsonify({'error': 'Amount is required and cannot be empty'}), 400
        
        try:
            amount = float(data['amount'])
            if amount <= 0:
                return jsonify({'error': 'Amount must be greater than 0'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid amount format. Please enter a valid number'}), 400
        
        # Generate unique ID for expense
        expense_unique_id = generate_unique_id('EXP')
        
        # Handle bank_account_id based on payment method
        payment_method = data.get('payment_method', 'cash')
        bank_account_id = None
        if payment_method == 'online' and data.get('bank_account_id'):
            bank_account_id = data.get('bank_account_id')
        
        print(f"DEBUG: Payment method: {payment_method}")
        print(f"DEBUG: Bank account ID: {bank_account_id}")
        
        # Check which columns exist and build dynamic query
        cursor.execute("DESCRIBE expenses")
        columns = [row[0] for row in cursor.fetchall()]
        
        if 'payment_type' in columns and 'unique_id' in columns and 'purpose' in columns:
            # Full structure available
            cursor.execute("""
                INSERT INTO expenses (user_id, unique_id, title, purpose, description, amount, category, payment_method, payment_type, expense_type, expense_date, bill_file, bank_account_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session['user_id'],
                expense_unique_id,
                purpose_value,  # title
                purpose_value,  # purpose (same value for consistency)
                data.get('description', ''),
                amount,
                data.get('category', ''),
                payment_method,
                data.get('payment_type', 'cash'),
                data.get('expense_type', 'completed'),
                data['expense_date'],
                filename,
                bank_account_id
            ))
        else:
            # Fallback to basic structure
            cursor.execute("""
                INSERT INTO expenses (user_id, title, description, amount, category, expense_type, expense_date, bill_file)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session['user_id'],
                purpose_value,
                data.get('description', ''),
                amount,
                data.get('category', ''),
                data.get('expense_type', 'completed'),
                data['expense_date'],
                filename
            ))
        
        connection.commit()
        expense_id = cursor.lastrowid
        
        # Ensure the expense is committed before creating invoice
        connection.commit()
        
        # Ensure required columns exist in transactions table
        try:
            cursor.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS unique_id VARCHAR(50)")
            cursor.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS payment_method ENUM('cash', 'online') DEFAULT 'cash'")
            cursor.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source VARCHAR(50)")
            cursor.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS source_id INT")
            connection.commit()
        except Exception as e:
            print(f"Warning: Could not add columns to transactions table: {e}")
            # Continue with existing structure
        
        # Check which columns exist in transactions table and build dynamic query
        cursor.execute("DESCRIBE transactions")
        trans_columns = [row[0] for row in cursor.fetchall()]
        
        # Only create transaction if it's NOT an invoice type expense
        # Invoice type expenses will be handled by the invoice transaction creation
        if data.get('payment_type') != 'invoice':
            if 'unique_id' in trans_columns and 'payment_method' in trans_columns and 'source' in trans_columns:
                # Full structure available
                cursor.execute("""
                    INSERT INTO transactions (user_id, unique_id, title, description, purpose, amount, transaction_type, category, payment_method, transaction_date, source, source_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session['user_id'],
                    expense_unique_id,  # Use the SAME unique ID as the expense
                    f"Expense: {purpose_value}",  # title with "Expense:" prefix
                    data.get('description', ''),
                    purpose_value,  # purpose - use the actual expense purpose directly
                    float(data['amount']),
                    'debit',
                    data.get('category', ''),
                    data.get('payment_method', 'cash'),
                    data['expense_date'],
                    'expense',
                    expense_id
                ))
            else:
                # Fallback to basic structure
                cursor.execute("""
                    INSERT INTO transactions (user_id, title, description, purpose, amount, transaction_type, category, transaction_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session['user_id'],
                    f"Expense: {purpose_value}",  # title with "Expense:" prefix
                    data.get('description', ''),
                    purpose_value,  # purpose - use the actual expense purpose directly
                    float(data['amount']),
                    'debit',
                    data.get('category', ''),
                    data['expense_date']
                ))
        
        connection.commit()
        
        # Create invoice record if payment_type is 'invoice'
        invoice_id = None
        if data.get('payment_type') == 'invoice' and filename:
            try:
                # Use the expense's unique ID for the invoice number
                invoice_number = expense_unique_id
                
                # Create invoice record
                print(f"Creating invoice for expense {expense_id} with unique_id: {expense_unique_id}")
                cursor.execute("""
                    INSERT INTO invoices (user_id, unique_id, invoice_number, client_name, client_email, client_address, 
                                        invoice_date, due_date, subtotal, tax_amount, total_amount, status, 
                                        invoice_type, notes, bank_account_id, expense_id, source_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session['user_id'],
                    expense_unique_id,  # Store unique ID in unique_id column
                    invoice_number,
                    'Expense Invoice',  # Default client name
                    '',  # No email
                    '',  # No address
                    data['expense_date'],
                    data['expense_date'],  # Due date same as expense date
                    float(data['amount']),  # Subtotal
                    0.0,  # No tax for expense invoices
                    float(data['amount']),  # Total amount
                    'paid',  # Mark as paid since it's an expense
                    'out',  # Outgoing invoice (expense)
                    filename,  # Store filename in notes
                    bank_account_id,  # Transfer bank account ID
                    expense_id,
                    'expense'
                ))
                
                invoice_id = cursor.lastrowid
                print(f"Created invoice {invoice_id} linked to expense {expense_id}")
                
                # Create invoice item
                cursor.execute("""
                    INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price, sac_code, tax_rate)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    invoice_id,
                    purpose_value,  # Description from expense
                    1,  # Quantity
                    float(data['amount']),  # Unit price
                    float(data['amount']),  # Total price
                    '998313',  # Default SAC code
                    0  # No tax
                ))
                
                # Create transaction for the invoice
                cursor.execute("""
                    INSERT INTO transactions (user_id, unique_id, title, description, purpose, amount, transaction_type, 
                                            category, payment_method, transaction_date, source, source_id, bank_account_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session['user_id'],
                    expense_unique_id,  # Use the same unique ID as expense
                    invoice_number,  # Just the invoice number
                    f"Invoice {invoice_number}",
                    'Invoice Payment',
                    float(data['amount']),
                    'debit',  # Money going out for expense
                    'Invoice',
                    payment_method,
                    data['expense_date'],
                    'invoice',
                    invoice_id,
                    bank_account_id
                ))
                
                # Update balances based on payment method
                if payment_method == 'online' and bank_account_id:
                    cursor.execute("""
                        UPDATE bank_accounts 
                        SET current_balance = current_balance - %s 
                        WHERE id = %s AND user_id = %s
                    """, (float(data['amount']), bank_account_id, session['user_id']))
                elif payment_method == 'cash':
                    cursor.execute("""
                        UPDATE users 
                        SET cash_balance = cash_balance - %s 
                        WHERE id = %s
                    """, (float(data['amount']), session['user_id']))
                
                connection.commit()
                print(f"Created invoice {invoice_id} and transaction for expense {expense_id}")
                
            except Exception as e:
                print(f"Error creating invoice for expense: {e}")
                import traceback
                traceback.print_exc()
                connection.rollback()
                return jsonify({'error': str(e)}), 400
        else:
            # For non-invoice expenses, update balances directly
            if payment_method == 'online' and bank_account_id:
                cursor.execute("""
                    UPDATE bank_accounts 
                    SET current_balance = current_balance - %s 
                    WHERE id = %s AND user_id = %s
                """, (float(data['amount']), bank_account_id, session['user_id']))
            elif payment_method == 'cash':
                cursor.execute("""
                    UPDATE users 
                    SET cash_balance = cash_balance - %s 
                    WHERE id = %s
                """, (float(data['amount']), session['user_id']))
            
            connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'id': expense_id, 'invoice_id': invoice_id})
    except KeyError as e:
        return jsonify({'error': f'Missing required field: {str(e)}'}), 400
    except ValueError as e:
        return jsonify({'error': f'Invalid data format: {str(e)}'}), 400
    except Exception as e:
        print(f"Error in add_expense: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 400

@app.route('/api/expenses/<int:expense_id>', methods=['PUT'])
@login_required
def update_expense(expense_id):
    try:
        data = request.get_json()
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Ensure required columns exist in expenses table
        try:
            cursor.execute("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS payment_type ENUM('invoice', 'cash') DEFAULT 'cash'")
            cursor.execute("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS payment_method ENUM('cash', 'online') DEFAULT 'cash'")
            cursor.execute("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS bank_account_id INT NULL")
            cursor.execute("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS unique_id VARCHAR(50)")
            cursor.execute("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS purpose VARCHAR(255)")
            connection.commit()
        except Exception as e:
            print(f"Warning: Could not add columns to expenses table: {e}")
            # Continue with existing structure
        
        purpose_value = data.get('purpose', data.get('title', ''))
        
        # Try to update expense_type enum if it exists
        try:
            cursor.execute("ALTER TABLE expenses MODIFY COLUMN expense_type ENUM('completed', 'upcoming') NOT NULL DEFAULT 'completed'")
        except:
            # If expense_type column doesn't exist, create it
            cursor.execute("ALTER TABLE expenses ADD COLUMN IF NOT EXISTS expense_type ENUM('completed', 'upcoming') NOT NULL DEFAULT 'completed'")
        
        # Handle bank_account_id based on payment method
        payment_method = data.get('payment_method', 'cash')
        bank_account_id = None
        if payment_method == 'online' and data.get('bank_account_id'):
            bank_account_id = data.get('bank_account_id')
        
        print(f"DEBUG UPDATE: Payment method: {payment_method}")
        print(f"DEBUG UPDATE: Bank account ID: {bank_account_id}")
        
        # Check which columns exist and build dynamic query
        cursor.execute("DESCRIBE expenses")
        columns = [row[0] for row in cursor.fetchall()]
        
        if 'payment_type' in columns and 'unique_id' in columns and 'purpose' in columns:
            # Full structure available
            cursor.execute("""
                UPDATE expenses 
                SET title=%s, purpose=%s, description=%s, amount=%s, category=%s, payment_method=%s, payment_type=%s, expense_type=%s, expense_date=%s, bank_account_id=%s
                WHERE id=%s AND user_id=%s
            """, (
                purpose_value,  # title
                purpose_value,  # purpose (same value for consistency)
                data.get('description', ''),
                float(data['amount']),
                data.get('category', ''),
                payment_method,
                data.get('payment_type', 'cash'),
                data.get('expense_type', 'completed'),
                data['expense_date'],
                bank_account_id,
                expense_id,
                session['user_id']
            ))
        else:
            # Fallback to basic structure
            cursor.execute("""
                UPDATE expenses 
                SET title=%s, description=%s, amount=%s, category=%s, expense_type=%s, expense_date=%s
                WHERE id=%s AND user_id=%s
            """, (
                purpose_value,
                data.get('description', ''),
                float(data['amount']),
                data.get('category', ''),
                data.get('expense_type', 'completed'),
                data['expense_date'],
                expense_id,
                session['user_id']
            ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
@login_required
def delete_expense(expense_id):
    try:
        print(f"DEBUG: Delete expense {expense_id} called")
        print(f"DEBUG: Session user_id: {session.get('user_id')}")
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # First, get the expense details for balance reversal
        cursor.execute("""
            SELECT bill_file, amount, payment_method, bank_account_id, payment_type, unique_id, created_by_sub_user
            FROM expenses 
            WHERE id=%s AND user_id=%s
        """, (expense_id, session['user_id']))
        expense = cursor.fetchone()
        
        if not expense:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Expense not found'}), 404
        
        # Delete the associated file if it exists
        if expense['bill_file']:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], expense['bill_file'])
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass  # Continue even if file deletion fails
        
        # Reverse balances - ALWAYS reverse for all expenses
        # For sub-user expenses: balance was deducted during approval, so we add it back
        # For regular expenses: balance was deducted when created, so we add it back
        print(f"DEBUG: Reversing balance for expense {expense_id}, amount: {expense['amount']}, payment_method: {expense['payment_method']}, created_by_sub_user: {expense.get('created_by_sub_user')}")
        
        if expense['payment_method'] == 'online' and expense['bank_account_id']:
            # For online payments, add back to bank account balance
            cursor.execute("""
                UPDATE bank_accounts 
                SET current_balance = current_balance + %s 
                WHERE id = %s AND user_id = %s
            """, (float(expense['amount']), expense['bank_account_id'], session['user_id']))
            print(f"DEBUG: Added {expense['amount']} back to bank account {expense['bank_account_id']}")
        elif expense['payment_method'] == 'cash':
            # For cash payments, add back to cash balance
            cursor.execute("""
                UPDATE users 
                SET cash_balance = cash_balance + %s 
                WHERE id = %s
            """, (float(expense['amount']), session['user_id']))
            print(f"DEBUG: Added {expense['amount']} back to cash balance for user {session['user_id']}")
        else:
            print(f"DEBUG: Warning - Unknown payment method: {expense['payment_method']} or missing bank_account_id")
        
        # Add a credit transaction to log the balance adjustment for all expenses
        try:
            cursor.execute("""
                INSERT INTO transactions (
                    user_id, transaction_type, amount, description, 
                    transaction_date, payment_method, source, source_id
                ) VALUES (
                    %s, 'credit', %s, %s, 
                    NOW(), %s, 'expense_deletion', %s
                )
            """, (
                session['user_id'], 
                float(expense['amount']), 
                f"Expense deletion adjustment - Expense ID: {expense_id}" + (" (Sub-user expense)" if expense.get('created_by_sub_user') else ""), 
                expense['payment_method'],
                expense_id
            ))
            print(f"DEBUG: Added credit transaction for expense deletion adjustment")
        except Exception as trans_error:
            print(f"DEBUG: Warning - Could not add credit transaction: {trans_error}")
        
        # For sub-user expenses, update the original request status to 'deleted'
        if expense.get('created_by_sub_user'):
            try:
                cursor.execute("""
                    UPDATE sub_user_requests 
                    SET status = 'deleted', 
                        notes = CONCAT(COALESCE(notes, ''), '\\nDeleted by main user - Expense ID: ', %s),
                        updated_at = NOW()
                    WHERE sub_user_id = %s 
                    AND request_type = 'expense' 
                    AND JSON_EXTRACT(request_data, '$.title') = %s
                    AND JSON_EXTRACT(request_data, '$.amount') = %s
                    AND status = 'approved'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (expense_id, expense['created_by_sub_user'], expense.get('title', ''), expense['amount']))
                
                updated_requests = cursor.rowcount
                if updated_requests > 0:
                    print(f"DEBUG: Updated {updated_requests} sub-user request(s) to 'deleted' status")
                else:
                    print(f"DEBUG: No matching sub-user request found to update")
            except Exception as request_error:
                print(f"DEBUG: Warning - Could not update sub-user request status: {request_error}")
        
        # Delete the associated transaction if it exists
        try:
            # First try to delete by source and source_id
            cursor.execute("DELETE FROM transactions WHERE source = 'expense' AND source_id = %s AND user_id = %s", 
                         (expense_id, session['user_id']))
            deleted_count = cursor.rowcount
            
            # Also try to delete by unique_id (in case the transaction was created with the same unique_id as expense)
            if expense.get('unique_id'):
                cursor.execute("DELETE FROM transactions WHERE unique_id = %s AND user_id = %s", 
                             (expense['unique_id'], session['user_id']))
                deleted_count += cursor.rowcount
            
            if deleted_count > 0:
                print(f"Deleted {deleted_count} associated transaction(s) for expense {expense_id}")
        except Exception as trans_error:
            print(f"Warning: Could not delete associated transaction: {trans_error}")
        
        # Delete any transactions directly linked to this expense (regardless of payment_type)
        try:
            # Delete transactions linked by expense_id
            cursor.execute("DELETE FROM transactions WHERE source = 'expense' AND source_id = %s AND user_id = %s", 
                         (expense_id, session['user_id']))
            expense_trans_deleted = cursor.rowcount
            print(f"Deleted {expense_trans_deleted} transactions directly linked to expense {expense_id}")
            
            # Also delete transactions linked by unique_id
            if expense.get('unique_id'):
                cursor.execute("DELETE FROM transactions WHERE unique_id = %s AND user_id = %s", 
                             (expense['unique_id'], session['user_id']))
                unique_trans_deleted = cursor.rowcount
                print(f"Deleted {unique_trans_deleted} transactions linked by unique_id {expense['unique_id']}")
        except Exception as trans_error:
            print(f"Warning: Could not delete expense transactions: {trans_error}")
        
        # If this is an invoice-type expense, also delete the associated invoice and its transaction
        if expense.get('payment_type') == 'invoice':
            try:
                print(f"Looking for invoice associated with expense {expense_id}")
                
                # Simple approach: Delete invoice directly by expense_id
                print(f"Deleting invoice associated with expense {expense_id}")
                
                # Delete invoice items first (foreign key constraint)
                cursor.execute("DELETE FROM invoice_items WHERE invoice_id IN (SELECT id FROM invoices WHERE expense_id = %s AND user_id = %s)", 
                             (expense_id, session['user_id']))
                items_deleted = cursor.rowcount
                print(f"Deleted {items_deleted} invoice items for expense {expense_id}")
                
                # Delete bank details if exists
                cursor.execute("DELETE FROM bank_details WHERE invoice_id IN (SELECT id FROM invoices WHERE expense_id = %s AND user_id = %s)", 
                             (expense_id, session['user_id']))
                bank_details_deleted = cursor.rowcount
                print(f"Deleted {bank_details_deleted} bank details for expense {expense_id}")
                
                # Delete invoice transactions
                cursor.execute("DELETE FROM transactions WHERE source = 'invoice' AND source_id IN (SELECT id FROM invoices WHERE expense_id = %s AND user_id = %s)", 
                             (expense_id, session['user_id']))
                trans_deleted = cursor.rowcount
                print(f"Deleted {trans_deleted} invoice transactions for expense {expense_id}")
                
                # Delete the invoice directly
                cursor.execute("DELETE FROM invoices WHERE expense_id = %s AND user_id = %s", 
                             (expense_id, session['user_id']))
                invoice_deleted = cursor.rowcount
                
                if invoice_deleted > 0:
                    print(f"Successfully deleted {invoice_deleted} invoice(s) associated with expense {expense_id}")
                else:
                    print(f"No invoice found for expense {expense_id}")
                    
                    # Let's also check if there are any invoices with the same unique_id
                    if expense.get('unique_id'):
                        print(f"Checking for invoices with unique_id: {expense['unique_id']}")
                        cursor.execute("DELETE FROM invoices WHERE unique_id = %s AND user_id = %s", 
                                     (expense['unique_id'], session['user_id']))
                        unique_invoice_deleted = cursor.rowcount
                        if unique_invoice_deleted > 0:
                            print(f"Deleted {unique_invoice_deleted} invoice(s) with unique_id {expense['unique_id']}")
                            
                            # Delete invoice items first (foreign key constraint)
                            cursor.execute("DELETE FROM invoice_items WHERE invoice_id = %s", (invoice_id,))
                            items_deleted = cursor.rowcount
                            print(f"Deleted {items_deleted} invoice items for invoice {invoice_id}")
                            
                            # Delete bank details if exists
                            cursor.execute("DELETE FROM bank_details WHERE invoice_id = %s", (invoice_id,))
                            bank_details_deleted = cursor.rowcount
                            print(f"Deleted {bank_details_deleted} bank details for invoice {invoice_id}")
                            
                            # Delete invoice transaction (if exists) - try multiple ways
                            cursor.execute("DELETE FROM transactions WHERE source = 'invoice' AND source_id = %s AND user_id = %s", 
                                         (invoice_id, session['user_id']))
                            trans_deleted = cursor.rowcount
                            
                            # Also try to delete by unique_id
                            cursor.execute("DELETE FROM transactions WHERE unique_id = %s AND user_id = %s", 
                                         (expense['unique_id'], session['user_id']))
                            trans_deleted += cursor.rowcount
                            
                            # Also try to delete by expense_id
                            cursor.execute("DELETE FROM transactions WHERE source = 'expense' AND source_id = %s AND user_id = %s", 
                                         (expense_id, session['user_id']))
                            trans_deleted += cursor.rowcount
                            
                            print(f"Deleted {trans_deleted} invoice transactions for invoice {invoice_id}")
                            
                            # Delete the invoice
                            cursor.execute("DELETE FROM invoices WHERE id = %s AND user_id = %s", 
                                         (invoice_id, session['user_id']))
                            invoice_deleted = cursor.rowcount
                            
                            if invoice_deleted > 0:
                                print(f"Successfully deleted invoice {invoice_id} found by unique_id")
                            else:
                                print(f"Warning: Could not delete invoice {invoice_id} - no rows affected")
                        else:
                            print(f"No invoice found by unique_id: {expense['unique_id']}")
                    
            except Exception as invoice_error:
                print(f"Error deleting associated invoice: {invoice_error}")
                import traceback
                traceback.print_exc()
                # Don't fail the expense deletion if invoice deletion fails
        
        # Delete the expense record LAST (after invoice due to foreign key constraint)
        cursor.execute("DELETE FROM expenses WHERE id=%s AND user_id=%s", (expense_id, session['user_id']))
        expense_deleted = cursor.rowcount
        
        if expense_deleted > 0:
            print(f"Successfully deleted expense {expense_id}")
        else:
            print(f"Warning: Could not delete expense {expense_id} - no rows affected")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Bulk export expenses
@app.route('/api/expenses/export', methods=['POST'])
@login_required
def export_expenses():
    try:
        expense_ids = request.form.getlist('expense_ids')
        if not expense_ids:
            return jsonify({'error': 'No expenses selected for export'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Get selected expenses
        placeholders = ','.join(['%s'] * len(expense_ids))
        cursor.execute(f"""
            SELECT e.*, ba.bank_name, ba.account_number
            FROM expenses e
            LEFT JOIN bank_accounts ba ON e.bank_account_id = ba.id
            WHERE e.id IN ({placeholders}) AND e.user_id = %s
            ORDER BY e.expense_date DESC
        """, expense_ids + [session['user_id']])
        
        expenses = cursor.fetchall()
        cursor.close()
        connection.close()
        
        if not expenses:
            return jsonify({'error': 'No expenses found for export'}), 404
        
        # Generate PDF
        try:
            pdf_buffer = generate_expenses_pdf(expenses)
            
            # Return PDF as response
            response = make_response(pdf_buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=expenses_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            
            return response
        except Exception as pdf_error:
            print(f"Error generating PDF: {pdf_error}")
            return jsonify({'error': f'Failed to generate PDF: {str(pdf_error)}'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def generate_expenses_pdf(expenses):
    """Generate PDF for expenses export"""
    from reportlab.lib.pagesizes import letter, A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    import io
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    # Title
    title = Paragraph("Expenses Export Report", title_style)
    
    # Table data
    table_data = [['Unique ID', 'Purpose', 'Amount', 'Category', 'Payment Method', 'Date', 'Bank Account']]
    
    total_amount = 0
    for expense in expenses:
        bank_info = f"{expense.get('bank_name', 'N/A')} ({expense.get('account_number', 'N/A')})" if expense.get('bank_name') else 'Cash'
        table_data.append([
            expense.get('unique_id', 'N/A'),
            expense.get('purpose', 'N/A'),
            f"Rs. {expense.get('amount', 0):,.2f}",
            expense.get('category', 'N/A'),
            expense.get('payment_method', 'N/A'),
            expense.get('expense_date', 'N/A'),
            bank_info
        ])
        total_amount += float(expense.get('amount', 0))
    
    # Add total row
    table_data.append(['', '', f"Rs. {total_amount:,.2f}", '', '', '', 'TOTAL'])
    
    # Create table with optimized column widths for landscape
    table = Table(table_data, colWidths=[2.5*inch, 2*inch, 1.2*inch, 1*inch, 1*inch, 1*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (2, 1), (2, -1), 'RIGHT'),  # Right align amounts
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),  # Bold total row
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),  # Highlight total row
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Vertical alignment
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.lightgrey]),  # Alternating row colors
    ]))
    
    # Build PDF
    elements = [title, Spacer(1, 12), table]
    doc.build(elements)
    
    buffer.seek(0)
    return buffer

# Bulk export invoices
@app.route('/api/invoices/export', methods=['POST'])
@login_required
def export_invoices():
    try:
        invoice_ids = request.form.getlist('invoice_ids')
        if not invoice_ids:
            return jsonify({'error': 'No invoices selected for export'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Get selected invoices
        placeholders = ','.join(['%s'] * len(invoice_ids))
        cursor.execute(f"""
            SELECT i.*, ba.bank_name, ba.account_number
            FROM invoices i
            LEFT JOIN bank_accounts ba ON i.bank_account_id = ba.id
            WHERE i.id IN ({placeholders}) AND i.user_id = %s
            ORDER BY i.invoice_date DESC
        """, invoice_ids + [session['user_id']])
        
        invoices = cursor.fetchall()
        cursor.close()
        connection.close()
        
        if not invoices:
            return jsonify({'error': 'No invoices found for export'}), 404
        
        # Generate PDF
        try:
            pdf_buffer = generate_invoices_pdf(invoices)
            
            # Return PDF as response
            response = make_response(pdf_buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=invoices_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            
            return response
        except Exception as pdf_error:
            print(f"Error generating PDF: {pdf_error}")
            return jsonify({'error': f'Failed to generate PDF: {str(pdf_error)}'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def generate_invoices_pdf(invoices):
    """Generate PDF for invoices export"""
    from reportlab.lib.pagesizes import letter, A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    import io
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    # Title
    title = Paragraph("Invoices Export Report", title_style)
    
    # Table data
    table_data = [['Unique ID', 'Invoice #', 'Client', 'Type', 'Date', 'Amount', 'Status']]
    
    total_amount = 0
    for invoice in invoices:
        table_data.append([
            invoice.get('unique_id', 'N/A'),
            invoice.get('invoice_number', 'N/A'),
            invoice.get('client_name', 'N/A'),
            'In' if invoice.get('invoice_type') == 'in' else 'Out',
            invoice.get('invoice_date', 'N/A'),
            f"Rs. {invoice.get('total_amount', 0):,.2f}",
            invoice.get('status', 'N/A')
        ])
        total_amount += float(invoice.get('total_amount', 0))
    
    # Add total row
    table_data.append(['', '', '', '', '', f"Rs. {total_amount:,.2f}", 'TOTAL'])
    
    # Create table with optimized column widths for landscape
    table = Table(table_data, colWidths=[2.5*inch, 2*inch, 2*inch, 0.8*inch, 1*inch, 1.2*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (5, 1), (5, -1), 'RIGHT'),  # Right align amounts
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),  # Bold total row
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),  # Highlight total row
    ]))
    
    # Build PDF
    elements = [title, Spacer(1, 12), table]
    doc.build(elements)
    
    buffer.seek(0)
    return buffer

# Bulk delete transactions
@app.route('/api/transactions/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_transactions():
    """Bulk delete transactions and adjust financial balances"""
    try:
        data = request.get_json()
        transaction_ids = data.get('transaction_ids', [])
        
        if not transaction_ids:
            return jsonify({'success': False, 'message': 'No transaction IDs provided'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Get all transactions to be deleted
        placeholders = ','.join(['%s'] * len(transaction_ids))
        cursor.execute(f"""
            SELECT id, receipt_file, amount, transaction_type, payment_method, bank_account_id, description
            FROM transactions 
            WHERE id IN ({placeholders}) AND user_id = %s
        """, transaction_ids + [user_id])
        
        transactions = cursor.fetchall()
        
        if not transactions:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'No transactions found or access denied'}), 404
        
        total_adjustment = 0
        adjustments_made = 0
        
        # Process each transaction for financial adjustments
        for transaction in transactions:
            amount = float(transaction['amount']) if transaction['amount'] else 0
            payment_method = transaction['payment_method']
            transaction_type = transaction['transaction_type']
            
            print(f"DEBUG: Bulk delete - processing transaction {transaction['id']}, amount: {amount}, type: {transaction_type}, payment_method: {payment_method}")
            
            if amount > 0:
                # Delete associated file if it exists
                if transaction['receipt_file']:
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], transaction['receipt_file'])
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except OSError:
                            pass  # Continue even if file deletion fails
                
                # Reverse bank balance if payment method was online
                if payment_method == 'online' and transaction['bank_account_id']:
                    try:
                        if transaction_type == 'credit':
                            # Reverse credit: deduct the amount from bank account
                            cursor.execute("""
                                UPDATE bank_accounts 
                                SET current_balance = current_balance - %s 
                                WHERE id = %s AND user_id = %s
                            """, (amount, transaction['bank_account_id'], user_id))
                            print(f"DEBUG: Reversed credit transaction: Deducted ₹{amount} from bank account {transaction['bank_account_id']}")
                        else:
                            # Reverse debit: add the amount back to bank account
                            cursor.execute("""
                                UPDATE bank_accounts 
                                SET current_balance = current_balance + %s 
                                WHERE id = %s AND user_id = %s
                            """, (amount, transaction['bank_account_id'], user_id))
                            print(f"DEBUG: Reversed debit transaction: Added ₹{amount} back to bank account {transaction['bank_account_id']}")
                        
                        if cursor.rowcount > 0:
                            total_adjustment += amount
                            adjustments_made += 1
                            
                    except Exception as bank_error:
                        print(f"Error reversing bank balance for transaction {transaction['id']}: {bank_error}")
                
                # Reverse cash balance if payment method was cash
                elif payment_method == 'cash':
                    try:
                        if transaction_type == 'credit':
                            # Reverse credit: deduct the amount from cash balance
                            cursor.execute("""
                                UPDATE users 
                                SET cash_balance = cash_balance - %s 
                                WHERE id = %s
                            """, (amount, user_id))
                            print(f"DEBUG: Bulk delete - Reversed credit transaction: Deducted ₹{amount} from cash balance for user {user_id}")
                        else:
                            # Reverse debit: add the amount back to cash balance
                            cursor.execute("""
                                UPDATE users 
                                SET cash_balance = cash_balance + %s 
                                WHERE id = %s
                            """, (amount, user_id))
                            print(f"DEBUG: Bulk delete - Reversed debit transaction: Added ₹{amount} back to cash balance for user {user_id}")
                        
                        if cursor.rowcount > 0:
                            total_adjustment += amount
                            adjustments_made += 1
                            
                    except Exception as cash_error:
                        print(f"Error reversing cash balance for transaction {transaction['id']}: {cash_error}")
        
        # Delete all transactions
        cursor.execute(f"""
            DELETE FROM transactions 
            WHERE id IN ({placeholders}) AND user_id = %s
        """, transaction_ids + [user_id])
        
        deleted_count = cursor.rowcount
        
        connection.commit()
        cursor.close()
        connection.close()
        
        message = f"Successfully deleted {deleted_count} transaction(s)"
        if adjustments_made > 0:
            message += f" and adjusted balances by ₹{total_adjustment:.2f} across {adjustments_made} transactions"
        
        return jsonify({
            'success': True, 
            'message': message,
            'deleted_count': deleted_count,
            'adjustments_made': adjustments_made,
            'total_adjustment': total_adjustment
        })
        
    except Exception as e:
        print(f"Bulk delete transactions error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

# Bulk export transactions
@app.route('/api/transactions/export', methods=['POST'])
@login_required
def export_transactions():
    try:
        transaction_ids = request.form.getlist('transaction_ids')
        if not transaction_ids:
            return jsonify({'error': 'No transactions selected for export'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Get selected transactions
        placeholders = ','.join(['%s'] * len(transaction_ids))
        cursor.execute(f"""
            SELECT t.*, ba.bank_name, ba.account_number
            FROM transactions t
            LEFT JOIN bank_accounts ba ON t.bank_account_id = ba.id
            WHERE t.id IN ({placeholders}) AND t.user_id = %s
            ORDER BY t.transaction_date DESC
        """, transaction_ids + [session['user_id']])
        
        transactions = cursor.fetchall()
        cursor.close()
        connection.close()
        
        if not transactions:
            return jsonify({'error': 'No transactions found for export'}), 404
        
        # Generate PDF
        try:
            pdf_buffer = generate_transactions_pdf(transactions)
            
            # Return PDF as response
            response = make_response(pdf_buffer.getvalue())
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=transactions_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            
            return response
        except Exception as pdf_error:
            print(f"Error generating PDF: {pdf_error}")
            return jsonify({'error': f'Failed to generate PDF: {str(pdf_error)}'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def generate_transactions_pdf(transactions):
    """Generate PDF for transactions export"""
    from reportlab.lib.pagesizes import letter, A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    import io
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    # Title
    title = Paragraph("Transactions Export Report", title_style)
    
    # Table data
    table_data = [['Unique ID', 'Title', 'Purpose', 'Amount', 'Type', 'Category', 'Payment Method', 'Date', 'Bank Account']]
    
    total_credits = 0
    total_debits = 0
    for transaction in transactions:
        bank_info = f"{transaction.get('bank_name', 'N/A')} ({transaction.get('account_number', 'N/A')})" if transaction.get('bank_name') else 'Cash'
        table_data.append([
            transaction.get('unique_id', 'N/A'),
            transaction.get('title', 'N/A'),
            transaction.get('purpose', 'N/A'),
            f"Rs. {transaction.get('amount', 0):,.2f}",
            transaction.get('transaction_type', 'N/A'),
            transaction.get('category', 'N/A'),
            transaction.get('payment_method', 'N/A'),
            transaction.get('transaction_date', 'N/A'),
            bank_info
        ])
        if transaction.get('transaction_type') == 'credit':
            total_credits += float(transaction.get('amount', 0))
        else:
            total_debits += float(transaction.get('amount', 0))
    
    # Add total rows
    table_data.append(['', '', '', f"Rs. {total_credits:,.2f}", 'CREDITS', '', '', '', ''])
    table_data.append(['', '', '', f"Rs. {total_debits:,.2f}", 'DEBITS', '', '', '', ''])
    table_data.append(['', '', '', f"Rs. {total_credits - total_debits:,.2f}", 'NET', '', '', '', ''])
    
    # Create table with optimized column widths for landscape
    table = Table(table_data, colWidths=[2*inch, 1.5*inch, 1.2*inch, 1*inch, 0.8*inch, 1*inch, 1*inch, 1*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -4), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),  # Right align amounts
        ('FONTNAME', (0, -3), (-1, -1), 'Helvetica-Bold'),  # Bold total rows
        ('BACKGROUND', (0, -3), (-1, -1), colors.lightgrey),  # Highlight total rows
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Vertical alignment
        ('ROWBACKGROUNDS', (0, 1), (-1, -4), [colors.white, colors.lightgrey]),  # Alternating row colors
    ]))
    
    # Build PDF
    elements = [title, Spacer(1, 12), table]
    doc.build(elements)
    
    buffer.seek(0)
    return buffer

# API Routes for Transactions
@app.route('/api/transactions', methods=['GET'])
@login_required
def get_transactions():
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT t.*, 
               i.invoice_number, i.client_name as invoice_client_name, i.invoice_type,
               i.invoice_date, i.due_date, i.status as invoice_status,
               su.sub_user_id, CONCAT(su.first_name, ' ', su.last_name) as sub_user_name
        FROM transactions t
        LEFT JOIN invoices i ON t.source_id = i.id AND t.source = 'invoice'
        LEFT JOIN sub_users su ON t.created_by_sub_user = su.id
        WHERE t.user_id = %s
        ORDER BY t.created_at DESC
    """, (session['user_id'],))
    transactions = cursor.fetchall()
    
    # Convert date objects to strings
    for transaction in transactions:
        if transaction['transaction_date']:
            transaction['transaction_date'] = transaction['transaction_date'].isoformat()
        if transaction['created_at']:
            transaction['created_at'] = transaction['created_at'].isoformat()
        if transaction['updated_at']:
            transaction['updated_at'] = transaction['updated_at'].isoformat()
        if transaction.get('invoice_date'):
            transaction['invoice_date'] = transaction['invoice_date'].isoformat()
        if transaction.get('due_date'):
            transaction['due_date'] = transaction['due_date'].isoformat()
    
    cursor.close()
    connection.close()
    return jsonify(transactions)

@app.route('/api/transactions', methods=['POST'])
@login_required
def add_transaction():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in. Please log in and try again.'}), 401
        
        data = request.form.to_dict()
        file = request.files.get('receipt_file')
        
        filename = None
        if file and file.filename and allowed_file(file.filename):
            filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Generate unique ID for transaction
        transaction_unique_id = generate_unique_id('TXN')
        
        cursor.execute("""
            INSERT INTO transactions (user_id, unique_id, title, description, purpose, utr_number, amount, transaction_type, category, payment_method, bank_account_id, transaction_date, receipt_file)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session['user_id'],
            transaction_unique_id,
            data['title'],
            data.get('description', ''),
            data.get('purpose', ''),
            data.get('utr_number', ''),
            float(data['amount']),
            data['transaction_type'],
            data.get('category', ''),
            data.get('payment_method', 'cash'),
            data.get('bank_account_id', None),
            data['transaction_date'],
            filename
        ))
        
        transaction_id = cursor.lastrowid
        
        # Update bank balance if bank account is specified and payment method is online
        bank_account_id = data.get('bank_account_id')
        payment_method = data.get('payment_method', 'cash')
        transaction_type = data['transaction_type']
        amount = float(data['amount'])
        
        if bank_account_id and payment_method == 'online':
            try:
                if transaction_type == 'credit':
                    # Credit: Add money to bank account
                    cursor.execute("""
                        UPDATE bank_accounts 
                        SET current_balance = current_balance + %s 
                        WHERE id = %s AND user_id = %s
                    """, (amount, bank_account_id, session['user_id']))
                    print(f"DEBUG: Added ₹{amount} to bank account {bank_account_id} for user {session['user_id']}")
                else:
                    # Debit: Deduct money from bank account
                    cursor.execute("""
                        UPDATE bank_accounts 
                        SET current_balance = current_balance - %s 
                        WHERE id = %s AND user_id = %s
                    """, (amount, bank_account_id, session['user_id']))
                    print(f"DEBUG: Deducted ₹{amount} from bank account {bank_account_id} for user {session['user_id']}")
                
                if cursor.rowcount == 0:
                    print(f"Warning: Could not update bank account {bank_account_id} balance")
            except Exception as bank_error:
                print(f"Error updating bank balance: {bank_error}")
        
        # Update cash balance if payment method is cash
        if payment_method == 'cash':
            try:
                if transaction_type == 'credit':
                    # Credit: Add money to cash balance
                    cursor.execute("""
                        UPDATE users 
                        SET cash_balance = cash_balance + %s 
                        WHERE id = %s
                    """, (amount, session['user_id']))
                    print(f"DEBUG: Added ₹{amount} to cash balance for user {session['user_id']}")
                else:
                    # Debit: Deduct money from cash balance
                    cursor.execute("""
                        UPDATE users 
                        SET cash_balance = cash_balance - %s 
                        WHERE id = %s
                    """, (amount, session['user_id']))
                    print(f"DEBUG: Deducted ₹{amount} from cash balance for user {session['user_id']}")
                
                if cursor.rowcount == 0:
                    print(f"Warning: Could not update cash balance for user {session['user_id']}")
            except Exception as cash_error:
                print(f"Error updating cash balance: {cash_error}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'id': transaction_id})
    except KeyError as e:
        return jsonify({'error': f'Missing required field: {str(e)}'}), 400
    except ValueError as e:
        return jsonify({'error': f'Invalid data format: {str(e)}'}), 400
    except Exception as e:
        print(f"Error in add_transaction: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 400

@app.route('/api/transactions/<int:transaction_id>', methods=['PUT'])
@login_required
def update_transaction(transaction_id):
    try:
        data = request.get_json()
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE transactions 
            SET title=%s, description=%s, purpose=%s, payment_method=%s, utr_number=%s, amount=%s, transaction_type=%s, category=%s, bank_account_id=%s, transaction_date=%s
            WHERE id=%s AND user_id=%s
        """, (
            data['title'],
            data.get('description', ''),
            data.get('purpose', ''),
            data.get('payment_method', 'cash'),
            data.get('utr_number', ''),
            float(data['amount']),
            data['transaction_type'],
            data.get('category', ''),
            data.get('bank_account_id', None),
            data['transaction_date'],
            transaction_id,
            session['user_id']
        ))
        
        connection.commit()
        

        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/transactions/<int:transaction_id>', methods=['DELETE'])
@login_required
def delete_transaction(transaction_id):
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # First, get the transaction details for balance reversal
        cursor.execute("""
            SELECT receipt_file, amount, transaction_type, payment_method, bank_account_id, description, created_by_sub_user
            FROM transactions 
            WHERE id=%s AND user_id=%s
        """, (transaction_id, session['user_id']))
        transaction = cursor.fetchone()
        
        print(f"DEBUG: Deleting transaction {transaction_id} with details: {transaction}")
        
        if not transaction:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Transaction not found'}), 404
        
        # Check if this transaction was created by expense deletion (skip balance reversal)
        is_expense_deletion_transaction = (
            transaction.get('description') and 
            'Expense deletion adjustment' in transaction.get('description', '')
        )
        
        is_sub_user_transaction = transaction.get('created_by_sub_user') is not None
        
        if is_expense_deletion_transaction:
            print(f"DEBUG: Skipping balance reversal for expense deletion transaction {transaction_id}")
        else:
            print(f"DEBUG: Will reverse balance for transaction {transaction_id} - sub_user: {is_sub_user_transaction}")
        
        # Delete the associated file if it exists
        if transaction['receipt_file']:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], transaction['receipt_file'])
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass  # Continue even if file deletion fails
        
        # Reverse bank balance if payment method was online (skip only for expense deletion transactions)
        if not is_expense_deletion_transaction and transaction['payment_method'] == 'online' and transaction['bank_account_id']:
            try:
                # Get current bank balance before update
                cursor.execute("SELECT current_balance FROM bank_accounts WHERE id = %s AND user_id = %s", (transaction['bank_account_id'], session['user_id']))
                current_bank_balance = cursor.fetchone()
                if current_bank_balance and 'current_balance' in current_bank_balance:
                    print(f"DEBUG: Current bank balance before deletion: ₹{current_bank_balance['current_balance']}")
                
                if transaction['transaction_type'] == 'credit':
                    # Reverse credit: deduct the amount from bank account
                    cursor.execute("""
                        UPDATE bank_accounts 
                        SET current_balance = current_balance - %s 
                        WHERE id = %s AND user_id = %s
                    """, (float(transaction['amount']), transaction['bank_account_id'], session['user_id']))
                    print(f"DEBUG: Reversed credit transaction deletion: Deducted ₹{transaction['amount']} from bank account {transaction['bank_account_id']}")
                else:
                    # Reverse debit: add the amount back to bank account
                    cursor.execute("""
                        UPDATE bank_accounts 
                        SET current_balance = current_balance + %s 
                        WHERE id = %s AND user_id = %s
                    """, (float(transaction['amount']), transaction['bank_account_id'], session['user_id']))
                    print(f"DEBUG: Reversed debit transaction deletion: Added ₹{transaction['amount']} back to bank account {transaction['bank_account_id']}")
                
                if cursor.rowcount == 0:
                    print(f"Warning: Could not reverse bank balance for transaction {transaction_id}")
                else:
                    print(f"DEBUG: Bank balance update successful for transaction {transaction_id}")
                
            except Exception as bank_error:
                print(f"Error reversing bank balance for transaction deletion: {bank_error}")
                # Don't fail the deletion if balance reversal fails
        
        # Reverse cash balance if payment method was cash (skip only for expense deletion transactions)
        if not is_expense_deletion_transaction and transaction['payment_method'] == 'cash':
            try:
                # Get current cash balance before update
                cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (session['user_id'],))
                current_balance = cursor.fetchone()
                if current_balance and 'cash_balance' in current_balance:
                    print(f"DEBUG: Current cash balance before deletion: ₹{current_balance['cash_balance']}")
                
                if transaction['transaction_type'] == 'credit':
                    # Reverse credit: deduct the amount from cash balance
                    cursor.execute("""
                        UPDATE users 
                        SET cash_balance = cash_balance - %s 
                        WHERE id = %s
                    """, (float(transaction['amount']), session['user_id']))
                    print(f"DEBUG: Reversed credit transaction deletion: Deducted ₹{transaction['amount']} from cash balance for user {session['user_id']}")
                else:
                    # Reverse debit: add the amount back to cash balance
                    cursor.execute("""
                        UPDATE users 
                        SET cash_balance = cash_balance + %s 
                        WHERE id = %s
                    """, (float(transaction['amount']), session['user_id']))
                    print(f"DEBUG: Reversed debit transaction deletion: Added ₹{transaction['amount']} back to cash balance for user {session['user_id']}")
                
                if cursor.rowcount == 0:
                    print(f"Warning: Could not reverse cash balance for transaction {transaction_id}")
                else:
                    print(f"DEBUG: Cash balance update successful for transaction {transaction_id}")
                
            except Exception as cash_error:
                print(f"Error reversing cash balance for transaction deletion: {cash_error}")
                # Don't fail the deletion if balance reversal fails
        
        # For sub-user transactions, update the original request status to 'deleted'
        if is_sub_user_transaction and transaction.get('created_by_sub_user'):
            try:
                cursor.execute("""
                    UPDATE sub_user_requests 
                    SET status = 'deleted', 
                        notes = CONCAT(COALESCE(notes, ''), '\\nDeleted by main user - Transaction ID: ', %s),
                        updated_at = NOW()
                    WHERE sub_user_id = %s 
                    AND request_type = 'transaction' 
                    AND JSON_EXTRACT(request_data, '$.title') = %s
                    AND JSON_EXTRACT(request_data, '$.amount') = %s
                    AND status = 'approved'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (transaction_id, transaction['created_by_sub_user'], transaction.get('description', ''), transaction['amount']))
                
                updated_requests = cursor.rowcount
                if updated_requests > 0:
                    print(f"DEBUG: Updated {updated_requests} sub-user request(s) to 'deleted' status")
                else:
                    print(f"DEBUG: No matching sub-user request found to update")
            except Exception as request_error:
                print(f"DEBUG: Warning - Could not update sub-user request status: {request_error}")
        
        # Delete the transaction record
        cursor.execute("DELETE FROM transactions WHERE id=%s AND user_id=%s", (transaction_id, session['user_id']))
        
        # Verify balance updates by checking current balances
        if transaction['payment_method'] == 'cash':
            cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (session['user_id'],))
            updated_cash_balance = cursor.fetchone()
            if updated_cash_balance and 'cash_balance' in updated_cash_balance:
                print(f"DEBUG: Updated cash balance for user {session['user_id']}: ₹{updated_cash_balance['cash_balance']}")
        elif transaction['payment_method'] == 'online' and transaction['bank_account_id']:
            cursor.execute("SELECT current_balance FROM bank_accounts WHERE id = %s AND user_id = %s", (transaction['bank_account_id'], session['user_id']))
            updated_bank_balance = cursor.fetchone()
            if updated_bank_balance and 'current_balance' in updated_bank_balance:
                print(f"DEBUG: Updated bank balance for account {transaction['bank_account_id']}: ₹{updated_bank_balance['current_balance']}")
        
        connection.commit()
        
        # Final verification - check balances one more time after commit
        if transaction['payment_method'] == 'cash':
            cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (session['user_id'],))
            final_cash_balance = cursor.fetchone()
            if final_cash_balance and 'cash_balance' in final_cash_balance:
                print(f"DEBUG: Final cash balance after commit: ₹{final_cash_balance['cash_balance']}")
        elif transaction['payment_method'] == 'online' and transaction['bank_account_id']:
            cursor.execute("SELECT current_balance FROM bank_accounts WHERE id = %s AND user_id = %s", (transaction['bank_account_id'], session['user_id']))
            final_bank_balance = cursor.fetchone()
            if final_bank_balance and 'current_balance' in final_bank_balance:
                print(f"DEBUG: Final bank balance after commit: ₹{final_bank_balance['current_balance']}")
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Transaction deleted successfully and balances adjusted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400



# API Routes for Invoices
# Add a temporary route to run migration with better error handling
@app.route('/run-migration')
def run_migration():
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Check if column already exists
        try:
            cursor.execute("SHOW COLUMNS FROM invoices LIKE 'invoice_type'")
            column_exists = cursor.fetchone() is not None
            
            if column_exists:
                cursor.close()
                connection.close()
                return jsonify({'success': True, 'message': 'Column already exists', 'column_exists': True})
            
            # Add invoice_type column if it doesn't exist
            cursor.execute("""
                ALTER TABLE invoices 
                ADD COLUMN invoice_type ENUM('in', 'out') DEFAULT 'out' AFTER status
            """)
            
            # Create index for better performance
            cursor.execute("CREATE INDEX idx_invoices_type ON invoices(invoice_type)")
            
            connection.commit()
            
            # Verify column was added
            cursor.execute("SHOW COLUMNS FROM invoices LIKE 'invoice_type'")
            verification = cursor.fetchone() is not None
            
            cursor.close()
            connection.close()
            
            if verification:
                return jsonify({'success': True, 'message': 'Migration completed successfully', 'column_exists': True})
            else:
                return jsonify({'success': False, 'message': 'Migration failed to add column', 'column_exists': False})
                
        except mysql.connector.Error as db_error:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': f'Database error: {str(db_error)}', 'error_details': str(db_error)})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'General error: {str(e)}', 'error_details': str(e)}), 500

# Add a temporary route to run migration immediately
@app.route('/fix-database')
def fix_database():
    try:
        connection = get_db_connection()
        if not connection:
            return "<h2>Error: Database connection failed</h2><p>Please check your database configuration.</p>"
        
        cursor = connection.cursor()
        
        # Check if column already exists
        cursor.execute("SHOW COLUMNS FROM invoices LIKE 'invoice_type'")
        column_exists = cursor.fetchone() is not None
        
        if column_exists:
            cursor.close()
            connection.close()
            return "<h2>Success: Column already exists</h2><p>The invoice_type column already exists in your database.</p>"
        
        # Add invoice_type column
        try:
            cursor.execute("""
                ALTER TABLE invoices 
                ADD COLUMN invoice_type ENUM('in', 'out') DEFAULT 'out' AFTER status
            """)
            
            # Create index
            cursor.execute("CREATE INDEX idx_invoices_type ON invoices(invoice_type)")
            
            connection.commit()
            
            # Verify column was added
            cursor.execute("SHOW COLUMNS FROM invoices LIKE 'invoice_type'")
            verification = cursor.fetchone() is not None
            
            cursor.close()
            connection.close()
            
            if verification:
                return """
                <h2>Success: Database fixed!</h2>
                <p>The invoice_type column has been successfully added to your database.</p>
                <p>You can now create both In and Out invoices.</p>
                <a href="/invoices">Go to Invoices Page</a>
                """
            else:
                return "<h2>Error: Migration failed</h2><p>The column was not added successfully. Please try again.</p>"
                
        except mysql.connector.Error as db_error:
            cursor.close()
            connection.close()
            return f"<h2>Database Error:</h2><p>{str(db_error)}</p><p>Please check your database permissions.</p>"
            
    except Exception as e:
        return f"<h2>General Error:</h2><p>{str(e)}</p>"

# Add a new route to check database structure
@app.route('/check-db-structure')
def check_db_structure():
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Get all columns from invoices table
        cursor.execute("DESCRIBE invoices")
        columns = cursor.fetchall()
        
        # Format columns for JSON response
        column_info = []
        for col in columns:
            column_info.append({
                'field': col[0],
                'type': col[1],
                'null': col[2],
                'key': col[3],
                'default': col[4],
                'extra': col[5]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'columns': column_info,
            'invoice_type_exists': any(col[0] == 'invoice_type' for col in columns)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@invoices_ns.route('/')
class InvoiceList(Resource):
    @api.doc('get_invoices', security='Bearer')
    @api.marshal_list_with(invoice_model)
    @api.param('search', 'Search query for invoice number or client name', _in='query', required=False)
    @api.response(200, 'Invoices retrieved successfully')
    @api.response(401, 'Authentication required')
    @api.response(500, 'Database connection failed')
    def get(self):
        """Get all invoices for the authenticated user with optional search"""
        if 'user_id' not in session:
            return {'error': 'Authentication required'}, 401
        return get_invoices()

# Keep the original route for backward compatibility
@app.route('/api/invoices', methods=['GET'])
@login_required
def get_invoices():
    search = request.args.get('search', '')
    
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = connection.cursor(dictionary=True)
    
    if search:
        cursor.execute("""
            SELECT * FROM invoices 
            WHERE user_id = %s AND status != 'deleted_by_expense' AND (invoice_number LIKE %s OR client_name LIKE %s)
            ORDER BY created_at DESC
        """, (session['user_id'], f'%{search}%', f'%{search}%'))
    else:
        cursor.execute("""
            SELECT * FROM invoices 
            WHERE user_id = %s AND status != 'deleted_by_expense'
            ORDER BY created_at DESC
        """, (session['user_id'],))
    
    invoices = cursor.fetchall()
    
    # Convert date objects to strings
    for invoice in invoices:
        if invoice['invoice_date']:
            invoice['invoice_date'] = invoice['invoice_date'].isoformat()
        if invoice['due_date']:
            invoice['due_date'] = invoice['due_date'].isoformat()
        if invoice['created_at']:
            invoice['created_at'] = invoice['created_at'].isoformat()
        if invoice['updated_at']:
            invoice['updated_at'] = invoice['updated_at'].isoformat()
    
    cursor.close()
    connection.close()
    return jsonify(invoices)

@app.route('/api/invoices', methods=['POST'])
@login_required
def create_invoice():
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in. Please log in and try again.'}), 401
        
        data = request.get_json()
        print(f"DEBUG: Received invoice data: {data}")
        print(f"DEBUG: Bank account ID from request: {data.get('bank_account_id')}")
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Ensure required columns exist in invoices table
        try:
            cursor.execute("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS bank_account_id INT NULL")
            connection.commit()
        except Exception as e:
            print(f"Warning: Could not add bank_account_id column: {e}")
        
        # Determine invoice type (default to 'out' if not specified)
        invoice_type = data.get('invoice_type', 'out')
        print(f"DEBUG: Creating invoice with type: {invoice_type}")
        
        # Generate invoice number based on type
        invoice_number = generate_invoice_number(session['user_id'], invoice_type)
        
        # Calculate totals
        subtotal = sum(item['quantity'] * item['unit_price'] for item in data['items'])
        tax_amount = float(data.get('tax_amount', 0))
        cgst_rate = float(data.get('cgst_rate', 0))
        sgst_rate = float(data.get('sgst_rate', 0))
        igst_rate = float(data.get('igst_rate', 0))
        
        cgst_amount = subtotal * cgst_rate / 100
        sgst_amount = subtotal * sgst_rate / 100
        igst_amount = subtotal * igst_rate / 100
        total_amount = subtotal + tax_amount + cgst_amount + sgst_amount + igst_amount
        
        # For 'in' invoices, swap company and client information
        if invoice_type == 'in':
            # Swap company and client info
            company_name = data.get('client_name', '')
            company_email = data.get('client_email', '')
            company_phone = data.get('client_phone', '')
            company_address = data.get('client_address', '')
            
            client_name = data.get('company_name', '')
            client_email = data.get('company_email', '')
            client_phone = data.get('company_phone', '')
            client_address = data.get('company_address', '')
        else:
            # Normal order for 'out' invoices
            company_name = data.get('company_name', '')
            company_email = data.get('company_email', '')
            company_phone = data.get('company_phone', '')
            company_address = data.get('company_address', '')
            
            client_name = data.get('client_name', '')
            client_email = data.get('client_email', '')
            client_phone = data.get('client_phone', '')
            client_address = data.get('client_address', '')
        
        # Generate unique ID for invoice
        invoice_unique_id = generate_unique_id('INV')
        
        # Insert invoice
        cursor.execute("""
            INSERT INTO invoices (user_id, unique_id, invoice_number, client_name, client_email, client_address, client_phone,
                                client_state, client_pin, client_gstin, client_pan,
                                invoice_date, due_date, subtotal, tax_amount, total_amount, status, invoice_type, notes,
                                billing_company_name, billing_address, billing_city, billing_state, billing_pin,
                                gstin_number, pan_number, cgst_rate, cgst_amount, sgst_rate, sgst_amount, 
                                igst_rate, igst_amount, received_amount, terms_conditions)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session['user_id'],
            invoice_unique_id,
            invoice_number,
            client_name,
            client_email,
            client_address,
            client_phone,
            data.get('client_state', ''),
            data.get('client_pin', ''),
            data.get('client_gstin', ''),
            data.get('client_pan', ''),
            data['invoice_date'],
            data.get('due_date'),
            subtotal,
            tax_amount,
            total_amount,
            data.get('status', 'draft'),
            invoice_type,
            data.get('notes', ''),
            data.get('billing_company_name', ''),
            data.get('billing_address', ''),
            data.get('billing_city', ''),
            data.get('billing_state', ''),
            data.get('billing_pin', ''),
            data.get('gstin_number', ''),
            data.get('pan_number', ''),
            cgst_rate,
            cgst_amount,
            sgst_rate,
            sgst_amount,
            igst_rate,
            igst_amount,
            data.get('received_amount', 0),
            data.get('terms_conditions', '')
        ))
        
        print(f"DEBUG: Invoice inserted with type: {invoice_type}")
        
        invoice_id = cursor.lastrowid
        
        # Insert invoice items
        for item in data['items']:
            cursor.execute("""
                INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price, sac_code, tax_rate)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                invoice_id,
                item['description'],
                item['quantity'],
                item['unit_price'],
                item['quantity'] * item['unit_price'],
                item.get('sac_code', '998313'),
                item.get('tax_rate', 18)
            ))
        
        # Insert bank details if provided
        if data.get('account_number') or data.get('ifsc_code') or data.get('bank_name') or data.get('upi_id'):
            cursor.execute("""
                INSERT INTO bank_details (invoice_id, account_number, ifsc_code, bank_name, upi_id)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                invoice_id,
                data.get('account_number', ''),
                data.get('ifsc_code', ''),
                data.get('bank_name', ''),
                data.get('upi_id', '')
            ))
        
        # Store bank account ID for balance updates if provided
        bank_account_id = data.get('bank_account_id')
        if bank_account_id:
            # First ensure the bank_account_id column exists
            try:
                cursor.execute("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS bank_account_id INT NULL")
                connection.commit()
            except Exception as e:
                print(f"Warning: Could not add bank_account_id column: {e}")
            
            cursor.execute("""
                UPDATE invoices SET bank_account_id = %s WHERE id = %s
            """, (bank_account_id, invoice_id))
        
        # Handle UPI QR code upload if provided
        upi_qr_code_path = None
        if 'upi_qr_code' in request.files:
            upi_qr_file = request.files['upi_qr_code']
            if upi_qr_file and upi_qr_file.filename != '':
                filename = secure_filename(f"upi_qr_{invoice_id}_{upi_qr_file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'upi_qr_codes', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                upi_qr_file.save(filepath)
                upi_qr_code_path = f"/uploads/upi_qr_codes/{filename}"
                
                # Update bank details with QR code path
                cursor.execute("""
                    UPDATE bank_details SET upi_qr_code_path = %s WHERE invoice_id = %s
                """, (upi_qr_code_path, invoice_id))
        
        connection.commit()
        
        # If this is an OUT invoice, create a corresponding expense record so it shows in Expenses
        # and avoid double-counting by NOT creating a separate invoice transaction.
        transaction_id = None
        if invoice_type == 'out':
            try:
                # Ensure invoices table has expense_id column to link
                try:
                    cursor.execute("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS expense_id INT NULL")
                    connection.commit()
                except Exception as e:
                    print(f"Warning: Could not ensure invoices.expense_id column: {e}")

                # Derive payment method and bank account for the expense
                expense_payment_method = 'cash'
                expense_bank_account_id = None
                req_bank_id = data.get('bank_account_id')
                if req_bank_id:
                    expense_payment_method = 'online'
                    expense_bank_account_id = req_bank_id

                # Prepare expense fields
                expense_title = data.get('notes') or f"Invoice {invoice_number}"
                expense_purpose = expense_title
                expense_date = data.get('invoice_date')

                # Create expense using dynamic columns similar to add_expense
                cursor.execute("DESCRIBE expenses")
                exp_cols = [row[0] for row in cursor.fetchall()]

                expense_unique_id = generate_unique_id('EXP')

                if all(col in exp_cols for col in ['payment_type', 'unique_id', 'purpose', 'payment_method', 'bank_account_id']):
                    cursor.execute(
                        """
                        INSERT INTO expenses (user_id, unique_id, title, purpose, description, amount, category, 
                                             payment_method, payment_type, expense_type, expense_date, bill_file, bank_account_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            session['user_id'],
                            expense_unique_id,
                            expense_title,
                            expense_purpose,
                            data.get('notes', ''),
                            total_amount,
                            'Invoice',
                            expense_payment_method,
                            'cash',  # IMPORTANT: mark as cash to avoid invoice auto-creation path
                            'completed',
                            expense_date,
                            None,
                            expense_bank_account_id,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO expenses (user_id, title, description, amount, category, expense_type, expense_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            session['user_id'],
                            expense_title,
                            data.get('notes', ''),
                            total_amount,
                            'Invoice',
                            'completed',
                            expense_date,
                        ),
                    )

                expense_id = cursor.lastrowid

                # Link the invoice to this expense
                cursor.execute("UPDATE invoices SET expense_id = %s WHERE id = %s", (expense_id, invoice_id))

                # Insert a matching transaction for the expense (debit) if transactions table supports it
                try:
                    cursor.execute("DESCRIBE transactions")
                    trans_cols = [row[0] for row in cursor.fetchall()]

                    if all(col in trans_cols for col in ['payment_method', 'source', 'source_id']):
                        cursor.execute(
                            """
                            INSERT INTO transactions (user_id, title, description, purpose, amount, transaction_type, category, 
                                                      payment_method, transaction_date, source, source_id, bank_account_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                session['user_id'],
                                f"Expense: {expense_title}",
                                f"Expense created for OUT invoice {invoice_number}",
                                expense_purpose,
                                total_amount,
                                'debit',
                                'Invoice',
                                expense_payment_method,
                                expense_date,
                                'expense',
                                expense_id,
                                expense_bank_account_id,
                            ),
                        )
                    else:
                        cursor.execute(
                            """
                            INSERT INTO transactions (user_id, title, description, purpose, amount, transaction_type, category, transaction_date)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                session['user_id'],
                                f"Expense: {expense_title}",
                                f"Expense created for OUT invoice {invoice_number}",
                                expense_purpose,
                                total_amount,
                                'debit',
                                'Invoice',
                                expense_date,
                            ),
                        )
                except Exception as e:
                    print(f"Warning: Could not create expense transaction for OUT invoice: {e}")

                # Update balances once based on payment method
                if expense_payment_method == 'online' and expense_bank_account_id:
                    cursor.execute(
                        """
                        UPDATE bank_accounts SET current_balance = current_balance - %s 
                        WHERE id = %s AND user_id = %s
                        """,
                        (float(total_amount), expense_bank_account_id, session['user_id']),
                    )
                elif expense_payment_method == 'cash':
                    cursor.execute(
                        """
                        UPDATE users SET cash_balance = cash_balance - %s 
                        WHERE id = %s
                        """,
                        (float(total_amount), session['user_id']),
                    )

                connection.commit()
                print(f"Created expense {expense_id} for OUT invoice {invoice_id} and deducted once")
            except Exception as e:
                print(f"Error creating expense for OUT invoice: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Only create automatic transaction for IN invoices when status is 'paid'
            if data.get('status', 'draft') == 'paid':
                transaction_id = create_invoice_transaction(invoice_id, invoice_type, total_amount, invoice_number, client_name, bank_account_id, user_id=session['user_id'])
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True, 
            'invoice_number': invoice_number, 
            'id': invoice_id,
            'transaction_id': transaction_id
        })
    except KeyError as e:
        return jsonify({'error': f'Missing required field: {str(e)}'}), 400
    except ValueError as e:
        return jsonify({'error': f'Invalid data format: {str(e)}'}), 400
    except Exception as e:
        print(f"Error in create_invoice: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 400

@app.route('/api/invoices/<int:invoice_id>', methods=['GET'])
@login_required
def get_invoice(invoice_id):
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = connection.cursor(dictionary=True)
        
        # Get invoice details
        cursor.execute("""SELECT * FROM invoices 
                       WHERE id = %s AND user_id = %s""", 
                     (invoice_id, session['user_id']))
        invoice = cursor.fetchone()
        
        if not invoice:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Get invoice items
        cursor.execute("""SELECT * FROM invoice_items 
                       WHERE invoice_id = %s""", 
                     (invoice_id,))
        items = cursor.fetchall()
        
        # Convert datetime objects to strings
        if invoice.get('invoice_date'):
            invoice['invoice_date'] = invoice['invoice_date'].isoformat()
        if invoice.get('due_date'):
            invoice['due_date'] = invoice['due_date'].isoformat()
        if invoice.get('created_at'):
            invoice['created_at'] = invoice['created_at'].isoformat()
        if invoice.get('updated_at'):
            invoice['updated_at'] = invoice['updated_at'].isoformat()
        
        # Add items to invoice
        invoice['items'] = items
        
        # Ensure invoice_type is included (default to 'out' if not set)
        if 'invoice_type' not in invoice or invoice['invoice_type'] is None:
            invoice['invoice_type'] = 'out'
        
        cursor.close()
        connection.close()
        
        return jsonify(invoice)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/invoices/<int:invoice_id>', methods=['PUT'])
@login_required
def update_invoice(invoice_id):
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500

        cursor = connection.cursor(dictionary=True)
        
        # Ensure required columns exist in invoices table
        try:
            cursor.execute("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS bank_account_id INT NULL")
            connection.commit()
        except Exception as e:
            print(f"Warning: Could not add bank_account_id column: {e}")
        
        # Check if invoice exists and belongs to user
        cursor.execute("""SELECT id FROM invoices 
                       WHERE id = %s AND user_id = %s""", 
                     (invoice_id, session['user_id']))
        existing_invoice = cursor.fetchone()
        
        if not existing_invoice:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Invoice not found or not authorized to edit'}), 404
        
        # Get request data
        data = request.get_json()
        
        # Basic validation
        if not data or not data.get('client_name') or not data.get('invoice_date'):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Determine invoice type (default to 'out' if not specified)
        invoice_type = data.get('invoice_type', 'out')
        print(f"DEBUG: Updating invoice with type: {invoice_type}")
        
        # For 'in' invoices, swap company and client information
        if invoice_type == 'in':
            # Swap company and client info
            company_name = data.get('client_name', '')
            company_email = data.get('client_email', '')
            company_phone = data.get('client_phone', '')
            company_address = data.get('client_address', '')
            
            client_name = data.get('company_name', '')
            client_email = data.get('company_email', '')
            client_phone = data.get('company_phone', '')
            client_address = data.get('company_address', '')
        else:
            # Normal order for 'out' invoices
            company_name = data.get('company_name', '')
            company_email = data.get('company_email', '')
            company_phone = data.get('company_phone', '')
            company_address = data.get('company_address', '')
            
            client_name = data.get('client_name', '')
            client_email = data.get('client_email', '')
            client_phone = data.get('client_phone', '')
            client_address = data.get('client_address', '')
        
        # Update invoice
        update_query = """
        UPDATE invoices SET
            client_name = %s,
            client_email = %s,
            client_address = %s,
            client_phone = %s,
            client_state = %s,
            client_pin = %s,
            client_gstin = %s,
            client_pan = %s,
            invoice_date = %s,
            due_date = %s,
            subtotal = %s,
            tax_amount = %s,
            total_amount = %s,
            status = %s,
            invoice_type = %s,
            notes = %s,
            billing_company_name = %s,
            billing_address = %s,
            billing_city = %s,
            billing_state = %s,
            billing_pin = %s,
            gstin_number = %s,
            pan_number = %s,
            cgst_rate = %s,
            cgst_amount = %s,
            sgst_rate = %s,
            sgst_amount = %s,
            igst_rate = %s,
            igst_amount = %s,
            updated_at = NOW()
        WHERE id = %s AND user_id = %s
        """
        
        # Calculate totals
        subtotal = sum(item['quantity'] * item['unit_price'] for item in data.get('items', []))
        tax_amount = float(data.get('tax_amount', 0))
        cgst_rate = float(data.get('cgst_rate', 0))
        sgst_rate = float(data.get('sgst_rate', 0))
        igst_rate = float(data.get('igst_rate', 0))
        
        cgst_amount = subtotal * cgst_rate / 100
        sgst_amount = subtotal * sgst_rate / 100
        igst_amount = subtotal * igst_rate / 100
        total_amount = subtotal + tax_amount + cgst_amount + sgst_amount + igst_amount
        
        cursor.execute(update_query, (
            client_name,
            client_email,
            client_address,
            client_phone,
            data.get('client_state', ''),
            data.get('client_pin', ''),
            data.get('client_gstin', ''),
            data.get('client_pan', ''),
            data.get('invoice_date', ''),
            data.get('due_date', None),
            subtotal,
            tax_amount,
            total_amount,
            data.get('status', 'draft'),
            invoice_type,
            data.get('notes', ''),
            data.get('billing_company_name', ''),
            data.get('billing_address', ''),
            data.get('billing_city', ''),
            data.get('billing_state', ''),
            data.get('billing_pin', ''),
            data.get('gstin_number', ''),
            data.get('pan_number', ''),
            cgst_rate,
            cgst_amount,
            sgst_rate,
            sgst_amount,
            igst_rate,
            igst_amount,
            invoice_id,
            session['user_id']
        ))
        
        # Delete old items
        cursor.execute("DELETE FROM invoice_items WHERE invoice_id = %s", (invoice_id,))
        
        # Insert new items
        items = data.get('items', [])
        if items:
            for item in items:
                cursor.execute("""
                INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price, sac_code, tax_rate)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    invoice_id,
                    item.get('description', ''),
                    item.get('quantity', 0),
                    item.get('unit_price', 0),
                    item.get('quantity', 0) * item.get('unit_price', 0),
                    item.get('sac_code', '998313'),
                    item.get('tax_rate', 18)
                ))
        
        # Update bank details if provided
        if data.get('account_number') or data.get('ifsc_code') or data.get('bank_name') or data.get('upi_id'):
            # Check if bank details exist for this invoice
            cursor.execute("SELECT id FROM bank_details WHERE invoice_id = %s", (invoice_id,))
            existing_bank = cursor.fetchone()
            
            if existing_bank:
                # Update existing bank details
                cursor.execute("""
                    UPDATE bank_details 
                    SET account_number = %s, ifsc_code = %s, bank_name = %s, upi_id = %s
                    WHERE invoice_id = %s
                """, (
                    data.get('account_number', ''),
                    data.get('ifsc_code', ''),
                    data.get('bank_name', ''),
                    data.get('upi_id', ''),
                    invoice_id
                ))
            else:
                # Insert new bank details
                cursor.execute("""
                    INSERT INTO bank_details (invoice_id, account_number, ifsc_code, bank_name, upi_id)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    invoice_id,
                    data.get('account_number', ''),
                    data.get('ifsc_code', ''),
                    data.get('bank_name', ''),
                    data.get('upi_id', '')
                ))
        
        # Update bank account ID if provided
        bank_account_id = data.get('bank_account_id')
        if bank_account_id:
            cursor.execute("""
                UPDATE invoices SET bank_account_id = %s WHERE id = %s
            """, (bank_account_id, invoice_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def generate_pdf_template_invoice(invoice, items, company, pdf_template_path, filepath, filename):
    """Generate invoice using PDF template as background"""
    try:
        # Construct full path to the PDF template
        template_full_path = os.path.join(app.config['UPLOAD_FOLDER'], 'templates', pdf_template_path)
        
        if not os.path.exists(template_full_path):
            print(f"DEBUG: PDF template not found at {template_full_path}")
            # Since we only use pdftemp.html now, get bank_details and call pdftemp function
            bank_details = None
            try:
                connection = get_db_connection()
                if connection:
                    cursor = connection.cursor(dictionary=True)
                    cursor.execute("SELECT * FROM bank_details ORDER BY id DESC LIMIT 1")
                    bank_details = cursor.fetchone()
                    cursor.close()
                    connection.close()
            except Exception as e:
                print(f"DEBUG: Error getting bank details: {e}")
            return generate_pdftemp_invoice(invoice, items, company, bank_details, filepath, filename)
        
        # Generate content PDF using reportlab
        content_pdf_path = os.path.join(app.config['EXPORT_FOLDER'], f"content_{filename}")
        
        # Create content PDF with invoice data
        doc = SimpleDocTemplate(content_pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Company header
        if company:
            story.append(Paragraph(f"<b>{company['company_name']}</b>", styles['Title']))
            story.append(Paragraph(company['company_address'] or '', styles['Normal']))
            story.append(Paragraph(f"Phone: {company['company_phone'] or ''}", styles['Normal']))
            story.append(Paragraph(f"Email: {company['company_email'] or ''}", styles['Normal']))
            story.append(Spacer(1, 20))
        
        # Invoice details
        story.append(Paragraph(f"<b>INVOICE #{invoice['invoice_number']}</b>", styles['Heading1']))
        story.append(Paragraph(f"Date: {invoice['invoice_date']}", styles['Normal']))
        if invoice['due_date']:
            story.append(Paragraph(f"Due Date: {invoice['due_date']}", styles['Normal']))
        story.append(Spacer(1, 20))        # Client details - respect invoice type
        invoice_type = invoice.get('invoice_type', 'out')
        if invoice_type == 'in':
            story.append(Paragraph("<b>Bill To:</b>", styles['Heading2']))
        else:
            story.append(Paragraph("<b>Bill From:</b>", styles['Heading2']))
        story.append(Paragraph(invoice['client_name'], styles['Normal']))
        if invoice['client_address']:
            story.append(Paragraph(invoice['client_address'], styles['Normal']))
        if invoice['client_phone']:
            story.append(Paragraph(f"Phone: {invoice['client_phone']}", styles['Normal']))
        if invoice['client_email']:
            story.append(Paragraph(f"Email: {invoice['client_email']}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Items table
        table_data = [['Description', 'Quantity', 'Unit Price', 'Total']]
        for item in items:
            table_data.append([
                item['description'],
                str(item['quantity']),
                f"₹{item['unit_price']:.2f}",
                f"₹{item['total_price']:.2f}"
            ])
        
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        story.append(Spacer(1, 20))
        
        # Totals
        story.append(Paragraph(f"<b>Subtotal: ₹{invoice['subtotal']:.2f}</b>", styles['Normal']))
        if invoice['tax_rate'] > 0:
            story.append(Paragraph(f"<b>Tax ({invoice['tax_rate']}%): ₹{invoice['tax_amount']:.2f}</b>", styles['Normal']))
        story.append(Paragraph(f"<b>Total: ₹{invoice['total_amount']:.2f}</b>", styles['Heading2']))
        
        if invoice['notes']:
            story.append(Spacer(1, 20))
            story.append(Paragraph("<b>Notes:</b>", styles['Heading2']))
            story.append(Paragraph(invoice['notes'], styles['Normal']))
        
        doc.build(story)
        
        # Try to overlay content on PDF template using PyPDF2
        try:
            from PyPDF2 import PdfReader, PdfWriter
            from reportlab.pdfgen import canvas
            from io import BytesIO
            
            # Read the template PDF
            template_reader = PdfReader(template_full_path)
            template_page = template_reader.pages[0]
            
            # Create a new PDF with the content
            content_writer = PdfWriter()
            content_writer.add_page(template_page)
            
            # Create a BytesIO object to hold the content PDF
            content_buffer = BytesIO()
            content_writer.write(content_buffer)
            content_buffer.seek(0)
            
            # Read the content PDF
            content_reader = PdfReader(content_buffer)
            content_page = content_reader.pages[0]
            
            # Merge the content onto the template
            template_page.merge_page(content_page)
            
            # Write the final PDF
            with open(filepath, 'wb') as output_file:
                content_writer.write(output_file)
            
            # Clean up temporary file
            if os.path.exists(content_pdf_path):
                os.remove(content_pdf_path)
            
            print(f"DEBUG: PDF template overlay successful at {filepath}")
            return filepath
            
        except ImportError as e:
            print(f"DEBUG: PyPDF2 not available: {e}")
            # Fallback: just use the template PDF as is
            import shutil
            shutil.copy2(template_full_path, filepath)
            return filepath
            
        except Exception as e:
            print(f"DEBUG: PDF overlay failed: {e}")
            # Fallback to pdftemp generation
            try:
                cursor = mysql.connection.cursor()
                cursor.execute("SELECT * FROM bank_details ORDER BY id DESC LIMIT 1")
                bank_details = cursor.fetchone()
                cursor.close()
            except Exception as e:
                print(f"DEBUG: Error getting bank details: {e}")
                bank_details = None
            return generate_pdftemp_invoice(invoice, items, company, bank_details, filepath, filename)
        
    except Exception as e:
        print(f"DEBUG: PDF template generation error: {e}")
        try:
            connection = get_db_connection()
            if connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT * FROM bank_details ORDER BY id DESC LIMIT 1")
                bank_details = cursor.fetchone()
                cursor.close()
                connection.close()
            else:
                bank_details = None
        except Exception as e:
            print(f"DEBUG: Error getting bank details: {e}")
            bank_details = None
        return generate_pdftemp_invoice(invoice, items, company, bank_details, filepath, filename)

def generate_default_invoice_pdf(invoice, items, company, filepath, filename):
    """Generate default PDF invoice using reportlab"""
    try:
        doc = SimpleDocTemplate(filepath, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Company header
        if company:
            story.append(Paragraph(f"<b>{company['company_name']}</b>", styles['Title']))
            story.append(Paragraph(company['company_address'] or '', styles['Normal']))
            story.append(Paragraph(f"Phone: {company['company_phone'] or ''}", styles['Normal']))
            story.append(Paragraph(f"Email: {company['company_email'] or ''}", styles['Normal']))
            story.append(Spacer(1, 20))
        
        # Invoice details
        story.append(Paragraph(f"<b>INVOICE #{invoice['invoice_number']}</b>", styles['Heading1']))
        story.append(Paragraph(f"Date: {invoice['invoice_date']}", styles['Normal']))
        if invoice['due_date']:
            story.append(Paragraph(f"Due Date: {invoice['due_date']}", styles['Normal']))
        story.append(Spacer(1, 20))        # Client details - respect invoice type
        invoice_type = invoice.get('invoice_type', 'out')
        if invoice_type == 'in':
            story.append(Paragraph("<b>Bill To:</b>", styles['Heading2']))
        else:
            story.append(Paragraph("<b>Bill From:</b>", styles['Heading2']))
        story.append(Paragraph(invoice['client_name'], styles['Normal']))
        if invoice['client_address']:
            story.append(Paragraph(invoice['client_address'], styles['Normal']))
        if invoice['client_phone']:
            story.append(Paragraph(f"Phone: {invoice['client_phone']}", styles['Normal']))
        if invoice['client_email']:
            story.append(Paragraph(f"Email: {invoice['client_email']}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Items table
        table_data = [['Description', 'Quantity', 'Unit Price', 'Total']]
        for item in items:
            table_data.append([
                item['description'],
                str(item['quantity']),
                f"₹{item['unit_price']:.2f}",
                f"₹{item['total_price']:.2f}"
            ])
        
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        story.append(Spacer(1, 20))
        
        # Totals
        story.append(Paragraph(f"<b>Subtotal: ₹{invoice['subtotal']:.2f}</b>", styles['Normal']))
        if invoice['tax_rate'] > 0:
            story.append(Paragraph(f"<b>Tax ({invoice['tax_rate']}%): ₹{invoice['tax_amount']:.2f}</b>", styles['Normal']))
        story.append(Paragraph(f"<b>Total: ₹{invoice['total_amount']:.2f}</b>", styles['Heading2']))
        
        if invoice['notes']:
            story.append(Spacer(1, 20))
            story.append(Paragraph("<b>Notes:</b>", styles['Heading2']))
            story.append(Paragraph(invoice['notes'], styles['Normal']))
        
        doc.build(story)
        
        return filepath
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def convert_number_to_words(amount):
    """Convert number to proper English words for invoice total amount"""
    try:
        amount = int(amount)
        if amount == 0:
            return "Zero Rupees"
        
        # Define number words
        ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine']
        teens = ['Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
        tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']
        
        def convert_less_than_one_thousand(n):
            if n == 0:
                return ""
            elif n < 10:
                return ones[n]
            elif n < 20:
                return teens[n - 10]
            elif n < 100:
                return tens[n // 10] + (" " + ones[n % 10] if n % 10 != 0 else "")
            else:
                return ones[n // 100] + " Hundred" + (" and " + convert_less_than_one_thousand(n % 100) if n % 100 != 0 else "")
        
        def convert_number(n):
            if n == 0:
                return "Zero"
            elif n < 1000:
                return convert_less_than_one_thousand(n)
            elif n < 100000:
                return convert_less_than_one_thousand(n // 1000) + " Thousand" + (" " + convert_less_than_one_thousand(n % 1000) if n % 1000 != 0 else "")
            elif n < 10000000:  # Less than 1 crore
                return convert_less_than_one_thousand(n // 100000) + " Lakh" + (" " + convert_number(n % 100000) if n % 100000 != 0 else "")
            else:
                return convert_less_than_one_thousand(n // 10000000) + " Crore" + (" " + convert_number(n % 10000000) if n % 10000000 != 0 else "")
        
        result = convert_number(amount) + " Rupees"
        return result
        
    except:
        return f"{amount} Rupees"

def generate_sales_template_invoice(invoice, items, company, bank_details, filepath, filename):
    """Generate PDF invoice using the PDF-style template matching template.pdf design"""
    try:
        # Read the PDF-style template HTML (matching template.pdf design)
        sales_template_path = os.path.join('sales', 'pdf_style_template.html')
        
        if not os.path.exists(sales_template_path):
            print(f"DEBUG: PDF-style template not found at {sales_template_path}")
            # Fallback to custom template
            sales_template_path = os.path.join('sales', 'custom_template.html')
            if not os.path.exists(sales_template_path):
                print(f"DEBUG: Custom template also not found")
                # Use pdftemp.html instead
                return generate_pdftemp_invoice(invoice, items, company, bank_details, filepath, filename)
        
        with open(sales_template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Replace basic invoice information
        html_content = html_content.replace('{{invoice_number}}', str(invoice['invoice_number']))
        html_content = html_content.replace('{{invoice_date}}', str(invoice['invoice_date']))
        html_content = html_content.replace('{{due_date}}', str(invoice['due_date']) if invoice['due_date'] else 'N/A')
        html_content = html_content.replace('{{status}}', str(invoice['status']).upper())
        
        # Replace company information
        if company:
            html_content = html_content.replace('{{company_name}}', company['company_name'] or 'Your Company Name')
            html_content = html_content.replace('{{company_address}}', company['company_address'] or 'Your Company Address')
            html_content = html_content.replace('{{company_phone}}', company['company_phone'] or 'Your Phone Number')
            html_content = html_content.replace('{{company_email}}', company['company_email'] or 'your@email.com')
            html_content = html_content.replace('{{company_gstin}}', company.get('tax_number', '') or 'Your GSTIN')
            html_content = html_content.replace('{{company_pan}}', company.get('pan_number', '') or 'Your PAN')
            html_content = html_content.replace('{{company_city}}', company.get('company_city', 'Your City') or 'Your City')
        else:
            # Use default values if no company settings
            html_content = html_content.replace('{{company_name}}', 'Your Company Name')
            html_content = html_content.replace('{{company_address}}', 'Your Company Address')
            html_content = html_content.replace('{{company_phone}}', 'Your Phone Number')
            html_content = html_content.replace('{{company_email}}', 'your@email.com')
            html_content = html_content.replace('{{company_gstin}}', 'Your GSTIN')
            html_content = html_content.replace('{{company_pan}}', 'Your PAN')
            html_content = html_content.replace('{{company_city}}', 'Your City')
        
        # Replace client information
        html_content = html_content.replace('{{client_name}}', invoice['client_name'] or 'Client Name')
        html_content = html_content.replace('{{client_email}}', invoice.get('client_email', '') or '')
        html_content = html_content.replace('{{client_phone}}', invoice.get('client_phone', '') or '')
        html_content = html_content.replace('{{client_address}}', invoice.get('client_address', '') or '')
        
        # Replace new billing fields
        html_content = html_content.replace('{{billing_company_name}}', invoice.get('billing_company_name', '') or '')
        html_content = html_content.replace('{{billing_address}}', invoice.get('billing_address', '') or '')
        html_content = html_content.replace('{{billing_city}}', invoice.get('billing_city', '') or '')
        html_content = html_content.replace('{{billing_state}}', invoice.get('billing_state', '') or '')
        html_content = html_content.replace('{{billing_pin}}', invoice.get('billing_pin', '') or '')
        html_content = html_content.replace('{{gstin_number}}', invoice.get('gstin_number', '') or '')
        html_content = html_content.replace('{{pan_number}}', invoice.get('pan_number', '') or '')
        
        # Generate items table HTML with PDF-style formatting
        items_html = ''
        total_quantity = 0
        total_tax = 0
        for item in items:
            quantity = item['quantity']
            # Convert to float to avoid decimal multiplication issues
            total_price = float(item['total_price'])
            unit_price = float(item['unit_price'])
            tax_amount = total_price * 0.18  # Assuming 18% tax
            total_quantity += quantity
            total_tax += tax_amount
            
            items_html += f'''
                    <tr>
                        <td class="text-left">{item['description']}</td>
                        <td class="text-center">{item.get('sac_code', '998313')}</td>
                        <td class="text-center">{quantity}</td>
                        <td class="text-right">₹ {unit_price:,.2f}</td>
                        <td class="text-right">₹ {tax_amount:,.2f}<br><small>(18%)</small></td>
                        <td class="text-right">₹ {total_price:,.2f}</td>
                    </tr>
            '''
        
        # Replace items table
        html_content = html_content.replace('{{items_rows}}', items_html)
        
        # Replace additional calculated fields with proper formatting
        html_content = html_content.replace('{{total_quantity}}', str(int(total_quantity)))
        html_content = html_content.replace('{{total_tax}}', f"{total_tax:,.2f}")
        
        # Replace financial information with proper decimal formatting
        html_content = html_content.replace('{{subtotal}}', f"{float(invoice['subtotal']):,.2f}")
        html_content = html_content.replace('{{tax_rate}}', f"{float(invoice.get('tax_rate', 0)):.1f}")
        html_content = html_content.replace('{{tax_amount}}', f"{float(invoice.get('tax_amount', 0)):,.2f}")
        html_content = html_content.replace('{{cgst_rate}}', f"{float(invoice.get('cgst_rate', 9)):.0f}")
        html_content = html_content.replace('{{cgst_amount}}', f"{float(invoice.get('cgst_amount', 0)):,.2f}")
        html_content = html_content.replace('{{sgst_rate}}', f"{float(invoice.get('sgst_rate', 9)):.0f}")
        html_content = html_content.replace('{{sgst_amount}}', f"{float(invoice.get('sgst_amount', 0)):,.2f}")
        html_content = html_content.replace('{{total_amount}}', f"{float(invoice['total_amount']):,.2f}")
        html_content = html_content.replace('{{received_amount}}', "0.00")
        html_content = html_content.replace('{{currency_symbol}}', '₹')
        
        # Add total amount in words (simplified)
        total_amount_text = convert_number_to_words(float(invoice['total_amount']))
        html_content = html_content.replace('{{total_amount_words}}', total_amount_text)
        
        # Replace bank details if available
        if bank_details:
            html_content = html_content.replace('{{account_number}}', bank_details.get('account_number', '') or 'N/A')
            html_content = html_content.replace('{{ifsc_code}}', bank_details.get('ifsc_code', '') or 'N/A')
            html_content = html_content.replace('{{bank_name}}', bank_details.get('bank_name', '') or 'Bank Name')
            html_content = html_content.replace('{{upi_id}}', bank_details.get('upi_id', '') or 'N/A')
            html_content = html_content.replace('{{bank_account_name}}', company.get('company_name', 'Company Name') if company else 'Company Name')
            
            # Handle UPI QR code
            if bank_details.get('upi_qr_code_path'):
                qr_html = f'<img src="{bank_details["upi_qr_code_path"]}" alt="UPI QR Code" style="max-width: 150px;">'
            else:
                qr_html = '<div style="border: 2px dashed #ccc; padding: 20px; text-align: center; max-width: 150px;">QR Code Not Available</div>'
            html_content = html_content.replace('{{upi_qr_code_section}}', qr_html)
        else:
            html_content = html_content.replace('{{account_number}}', 'N/A')
            html_content = html_content.replace('{{ifsc_code}}', 'N/A')
            html_content = html_content.replace('{{bank_name}}', 'Bank Name')
            html_content = html_content.replace('{{upi_id}}', 'N/A')
            html_content = html_content.replace('{{bank_account_name}}', company.get('company_name', 'Company Name') if company else 'Company Name')
            html_content = html_content.replace('{{upi_qr_code_section}}', '<div style="border: 2px dashed #ccc; padding: 20px; text-align: center; max-width: 150px;">QR Code Not Available</div>')
        
        # Handle notes section
        if invoice.get('notes'):
            notes_html = f'''
        <div class="notes-section">
            <h4>Notes:</h4>
            <p>{invoice['notes']}</p>
        </div>
            '''
        else:
            notes_html = ''
        html_content = html_content.replace('{{notes_section}}', notes_html)
        
        print(f"DEBUG: Generated HTML content length: {len(html_content)}")
        
        # Convert HTML to PDF using ReportLab for better Windows compatibility
        try:
            # First try WeasyPrint if available
            try:
                from weasyprint import HTML
                print("DEBUG: Using weasyprint to convert PDF-style template HTML to PDF")
                
                # Set base URL to handle relative image paths
                base_url = os.path.abspath('sales')
                HTML(string=html_content, base_url=base_url).write_pdf(filepath)
                
                print(f"DEBUG: PDF-style template PDF generated successfully at {filepath}")
                return filepath
            except (ImportError, OSError) as e:
                print(f"DEBUG: WeasyPrint not available or has issues: {e}")
                # Fall back to ReportLab-based generation
                return generate_sales_template_with_reportlab(invoice, items, company, bank_details, filepath, filename)
            
        except Exception as e:
            print(f"DEBUG: PDF generation error: {e}")
            return generate_default_invoice_pdf(invoice, items, company, filepath, filename)
        
    except Exception as e:
        print(f"DEBUG: Sales template generation error: {e}")
        return generate_default_invoice_pdf(invoice, items, company, filepath, filename)

def generate_pdftemp_invoice(invoice, items, company, bank_details, filepath, filename):
    """Generate PDF invoice using the pdftemp.html template with Jinja2"""
    try:
        from jinja2 import Template
        
        # Determine which template to use based on invoice type
        invoice_type = invoice.get('invoice_type', 'out')
        print(f"DEBUG: Invoice type from database: {invoice_type}")
        
        # SWAPPED: IN invoices use pdftemp.html, OUT invoices use pdftemp_in.html
        if invoice_type == 'in':
            template_path = 'pdftemp.html'
            print("DEBUG: Using In Invoice template (pdftemp.html)")
        else:
            template_path = 'pdftemp_in.html'
            print("DEBUG: Using Out Invoice template (pdftemp_in.html)")
        
        # Get current working directory for debugging
        current_dir = os.getcwd()
        print(f"DEBUG: Current working directory: {current_dir}")
        print(f"DEBUG: Looking for template at: {os.path.abspath(template_path)}")
        
        if not os.path.exists(template_path):
            print(f"DEBUG: {template_path} template not found at {template_path}")
            return jsonify({'error': 'Template not found'}), 400
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Debug print for template content
        print(f"DEBUG: generate_pdftemp_invoice - First 100 chars of '{template_path}': '{template_content[:100]}'")
        
        # Create Jinja2 template
        template = Template(template_content)
        
        # Prepare data for template - Use actual billing information from database
        # For 'in' invoices, we show the client as the billing party (BILL TO)
        # For 'out' invoices, we show the client as the billing party (BILL FROM)
        if invoice_type == 'in':
            # For In invoices, use client information as the billing party (BILL TO)
            billing_company_name = invoice.get('client_name', '')
            billing_address = invoice.get('client_address', '')
            billing_state = invoice.get('client_state', '')  # Use client_state instead of billing_state
            billing_pin = invoice.get('client_pin', '')      # Use client_pin instead of billing_pin
            gstin_number = invoice.get('client_gstin', '')   # Use client_gstin instead of gstin_number
            pan_number = invoice.get('client_pan', '')       # Use client_pan instead of pan_number
            
            # Debug print for IN invoices
            print(f"DEBUG: IN Invoice - Client Name: {billing_company_name}")
            print(f"DEBUG: IN Invoice - Client Address: {billing_address}")
            print(f"DEBUG: IN Invoice - Client State: {billing_state}")
            print(f"DEBUG: IN Invoice - Client PIN: {billing_pin}")
            print(f"DEBUG: IN Invoice - Client GSTIN: {gstin_number}")
            print(f"DEBUG: IN Invoice - Client PAN: {pan_number}")
        else:
            # For Out invoices, use client information as the billing party (BILL FROM)
            billing_company_name = invoice.get('client_name', '')
            billing_address = invoice.get('client_address', '')
            billing_state = invoice.get('billing_state', '')
            billing_pin = invoice.get('billing_pin', '')
            gstin_number = invoice.get('gstin_number', '')
            pan_number = invoice.get('pan_number', '')
            
            # Debug print for OUT invoices
            print(f"DEBUG: OUT Invoice - Client Name: {billing_company_name}")
            print(f"DEBUG: OUT Invoice - Client Address: {billing_address}")
            print(f"DEBUG: OUT Invoice - Billing State: {billing_state}")
            print(f"DEBUG: OUT Invoice - Billing PIN: {billing_pin}")
            print(f"DEBUG: OUT Invoice - GSTIN: {gstin_number}")
            print(f"DEBUG: OUT Invoice - PAN: {pan_number}")
        
        template_data = {
            'invoice_number': str(invoice['invoice_number']),
            'invoice_date': str(invoice['invoice_date']),
            'due_date': str(invoice['due_date']) if invoice['due_date'] else 'N/A',
            'status': str(invoice['status']).upper(),
            'billing_company_name': billing_company_name,
            'billing_address': billing_address,
            'billing_state': billing_state,
            'billing_pin': billing_pin,
            'gstin_number': gstin_number,
            'pan_number': pan_number,
            'items': [],
            'subtotal': f"{float(invoice.get('subtotal', 0)):,.2f}",
            'cgst_rate': f"{float(invoice.get('cgst_rate', 0)):.1f}",
            'cgst_amount': f"{float(invoice.get('cgst_amount', 0)):,.2f}",
            'sgst_rate': f"{float(invoice.get('sgst_rate', 0)):.1f}",
            'sgst_amount': f"{float(invoice.get('sgst_amount', 0)):,.2f}",
            'igst_rate': f"{float(invoice.get('igst_rate', 0)):.1f}",
            'igst_amount': f"{float(invoice.get('igst_amount', 0)):,.2f}",
            'total_amount': f"{float(invoice.get('total_amount', 0)):,.2f}",
            'received_amount': f"{float(invoice.get('received_amount', 0)):,.2f}",
            'total_in_words': convert_number_to_words(float(invoice.get('total_amount', 0))),
            'currency_symbol': '₹',
            'bank_name': 'N/A',
            'account_number': 'N/A',
            'ifsc_code': 'N/A',
            'upi_id': 'N/A'
        }
        
        # Process items for template
        for item in items:
            template_data['items'].append({
                'description': item['description'],
                'sac': item.get('sac_code', '998313'),
                'quantity': item['quantity'],
                'unit_price': f"{float(item['unit_price']):,.2f}",
                'tax': item.get('tax_rate', 18),
                'total_price': f"{float(item['total_price']):,.2f}"
            })
        
        # Add bank details if available
        if bank_details:
            template_data.update({
                'bank_name': bank_details.get('bank_name', '') or 'N/A',
                'account_number': bank_details.get('account_number', '') or 'N/A',
                'ifsc_code': bank_details.get('ifsc_code', '') or 'N/A',
                'upi_id': bank_details.get('upi_id', '') or 'N/A'
            })
        
        # Render template
        html_content = template.render(**template_data)
        
        print(f"DEBUG: Generated pdftemp HTML content length: {len(html_content)}")
        
        # Convert HTML to PDF using weasyprint with fallback to ReportLab
        try:
            from weasyprint import HTML
            print("DEBUG: Using weasyprint to convert pdftemp HTML to PDF")
            
            # Set base URL to handle relative paths
            base_url = os.path.abspath('.')
            HTML(string=html_content, base_url=base_url).write_pdf(filepath)
            
            print(f"DEBUG: pdftemp PDF generated successfully at {filepath}")
            return filepath
            
        except ImportError:
            print("DEBUG: weasyprint not available, trying ReportLab fallback")
            return generate_reportlab_fallback(invoice, items, company, bank_details, filepath, filename)
        except Exception as e:
            print(f"DEBUG: weasyprint conversion error: {e}")
            print("DEBUG: Falling back to ReportLab")
            return generate_reportlab_fallback(invoice, items, company, bank_details, filepath, filename)
            
    except Exception as e:
        print(f"DEBUG: pdftemp template generation error: {e}")
        # Return simple error response without jsonify to avoid Flask context issues
        return {'error': str(e)}, 400

def get_bill_label_for_reportlab(invoice):
    """Helper function to determine the correct billing label for ReportLab PDFs"""
    # Try different ways to access invoice_type
    if isinstance(invoice, dict):
        # First try direct dictionary access
        if 'invoice_type' in invoice:
            invoice_type = invoice['invoice_type']
        # Then try get method
        else:
            invoice_type = invoice.get('invoice_type', 'out')
    else:
        # For object-like access
        try:
            invoice_type = invoice.invoice_type
        except (AttributeError, TypeError):
            invoice_type = 'out'
    
    # Convert to string and normalize to lowercase
    if invoice_type is not None:
        invoice_type = str(invoice_type).lower().strip()
    else:
        invoice_type = 'out'
    
    # Debug print
    print(f"DEBUG: get_bill_label_for_reportlab - Received invoice_type: '{invoice_type}'")
    
    # SWAPPED: IN invoices get "BILL TO", OUT invoices get "BILL FROM"
    if invoice_type == 'in':
        label = "BILL TO"
    else:
        label = "BILL FROM"
    
    print(f"DEBUG: get_bill_label_for_reportlab - Returning label: '{label}'")
    return label

def generate_reportlab_fallback(invoice, items, company, bank_details, filepath, filename):
    """Generate professional single-page PDF invoice using ReportLab"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        
        print("DEBUG: Using ReportLab fallback for PDF generation")
        
        # Determine invoice type and debug
        invoice_type = invoice.get('invoice_type', 'out')
        print(f"DEBUG: ReportLab - Invoice type from database: {invoice_type}")
        
        # Create PDF document with professional margins for single-page layout
        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
        styles = getSampleStyleSheet()
        story = []
        
        # Professional styles for modern invoice design
        company_style = ParagraphStyle(
            'CompanyStyle',
            parent=styles['Title'],
            fontSize=22,
            textColor=colors.HexColor('#1a365d'),
            alignment=TA_LEFT,
            spaceAfter=8,
            fontName='Helvetica-Bold'
        )
        
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Heading1'],
            fontSize=12,
            textColor=colors.HexColor('#2d3748'),
            alignment=TA_LEFT,
            spaceAfter=6,
            spaceBefore=8,
            fontName='Helvetica'
        )
        
        section_title_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1a365d'),
            alignment=TA_LEFT,
            spaceAfter=6,
            spaceBefore=10,
            fontName='Helvetica-Bold'
        )
        
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#4a5568'),
            alignment=TA_LEFT,
            spaceAfter=3,
            fontName='Helvetica'
        )
        
        # Professional header with company branding and logo
        logo_path = 'static/L icon.jpg'
        if os.path.exists(logo_path):
            try:
                # Create a table with logo image and company info - Compact version
                logo_img = Image(logo_path, width=0.5*inch, height=0.5*inch)  # Reduced logo size
                header_data = [
                    [logo_img, f"INVOICE #{invoice['invoice_number']}"],
                    ['LAITUSNEO TECHNOLOGIES PRIVATE LIMITED', f"Date: {invoice['invoice_date']}"],
                    ['NH2, Agra Road, Shanti Colony, near ITI Chauraha', f"Due Date: {invoice['due_date'] if invoice['due_date'] else 'N/A'}"],
                    ['Etawah, UP, 206001', f"Status: {invoice['status'].upper()}"],
                    ['Mobile: 8265915605 | GSTIN: 09JMVPK4466C1ZE', '']
                ]
                print("DEBUG: Logo image loaded successfully")
            except Exception as e:
                print(f"DEBUG: Logo image failed: {e}")
                # Fallback to text logo if image fails
                header_data = [
                    ['⚡ LAITUSNEO ⚡', f"INVOICE #{invoice['invoice_number']}"],
                    ['LAITUSNEO TECHNOLOGIES PRIVATE LIMITED', f"Date: {invoice['invoice_date']}"],
                    ['NH2, Agra Road, Shanti Colony, near ITI Chauraha', f"Due Date: {invoice['due_date'] if invoice['due_date'] else 'N/A'}"],
                    ['Etawah, UP, 206001', f"Status: {invoice['status'].upper()}"],
                    ['Mobile: 8265915605 | GSTIN: 09JMVPK4466C1ZE', '']
                ]
        else:
            print(f"DEBUG: Logo path not found: {logo_path}")
            # Fallback to text logo if image doesn't exist
            header_data = [
                ['⚡ LAITUSNEO ⚡', f"INVOICE #{invoice['invoice_number']}"],
                ['LAITUSNEO TECHNOLOGIES PRIVATE LIMITED', f"Date: {invoice['invoice_date']}"],
                ['NH2, Agra Road, Shanti Colony, near ITI Chauraha', f"Due Date: {invoice['due_date'] if invoice['due_date'] else 'N/A'}"],
                ['Etawah, UP, 206001', f"Status: {invoice['status'].upper()}"],
                ['Mobile: 8265915605 | GSTIN: 09JMVPK4466C1ZE', '']
            ]
        
        header_table = Table(header_data, colWidths=[4.2*inch, 2.3*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),  # Logo bold
            ('FONTNAME', (0, 1), (0, 1), 'Helvetica-Bold'),  # Company name bold
            ('FONTNAME', (0, 2), (-1, -1), 'Helvetica'),     # Other text normal
            ('FONTSIZE', (0, 0), (0, 0), 14),  # Logo - reduced
            ('FONTSIZE', (0, 1), (0, 1), 12),   # Company name - reduced
            ('FONTSIZE', (0, 2), (-1, -1), 8),  # Address and details - reduced
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('TEXTCOLOR', (0, 0), (0, 0), colors.HexColor('#1a365d')),  # Logo color
            ('TEXTCOLOR', (0, 1), (0, 1), colors.HexColor('#1a365d')),  # Company name in company color
            ('TEXTCOLOR', (1, 0), (1, 0), colors.HexColor('#1a365d')),  # Invoice number
            ('TEXTCOLOR', (1, 1), (1, 1), colors.HexColor('#1a365d')),  # Date
            ('TEXTCOLOR', (1, 2), (1, 2), colors.HexColor('#1a365d')),  # Due Date
            ('TEXTCOLOR', (1, 3), (1, 3), colors.HexColor('#1a365d')),  # Status
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#e2e8f0')),  # Subtle line
        ]))
        
        story.append(header_table)
        story.append(Spacer(1, 5))  # Further reduced spacing
        
        # Professional Bill To section - Compact version
        # Use the correct information based on invoice type
        # SWAPPED: IN invoices show client information as BILL TO, OUT invoices show as BILL FROM
        if invoice_type == 'in':
            # For In invoices, show client information as BILL TO
            bill_to_data = [
                ['BILL TO'],  # Static label for In invoices
                [f"Company: {invoice.get('client_name', '')}"],
                [f"Address: {invoice.get('client_address', '')}"],
                [f"GSTIN: {invoice.get('client_gstin', '')}"],  # Assuming client GSTIN field exists
                [f"PAN: {invoice.get('client_pan', '')}"],      # Assuming client PAN field exists
                [f"State: {invoice.get('client_state', '')}"],  # Assuming client state field exists
                [f"PIN: {invoice.get('client_pin', '')}"]       # Assuming client PIN field exists
            ]
        else:
            # For Out invoices, show normal billing information as BILL FROM
            bill_to_data = [
                ['BILL FROM'],  # Static label for Out invoices
                [f"Company: {invoice.get('billing_company_name', '') or invoice.get('client_name', '')}"],
                [f"Address: {invoice.get('billing_address', '') or invoice.get('client_address', '')}"],
                [f"GSTIN: {invoice.get('gstin_number', '')}"],
                [f"PAN: {invoice.get('pan_number', '')}"],
                [f"State: {invoice.get('billing_state', '')}"],
                [f"PIN: {invoice.get('billing_pin', '')}"]
            ]
        
        bill_to_table = Table(bill_to_data, colWidths=[6.5*inch])
        bill_to_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f7fafc')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),  # Reduced font size
            ('FONTSIZE', (0, 1), (-1, -1), 8),  # Reduced font size
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('LEFTPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
        ]))
        
        story.append(bill_to_table)
        story.append(Spacer(1, 5))  # Further reduced spacing
        
        # Professional Items table with currency symbols - Compact version
        items_data = [['Services', 'SAC', 'QTY', 'Rate (Rs.)', 'Tax', 'Amount (Rs.)']]
        for item in items:
            items_data.append([
                item['description'],
                item.get('sac_code', '998313'),
                str(item['quantity']),
                f"Rs. {item['unit_price']:,.2f}",
                f"{item.get('tax_rate', 18)}%",
                f"Rs. {item['total_price']:,.2f}"
            ])
        
        items_table = Table(items_data, colWidths=[2.2*inch, 0.8*inch, 0.6*inch, 1*inch, 0.6*inch, 1.3*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f7fafc')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),  # Reduced header font size
            ('FONTSIZE', (0, 1), (-1, -1), 8),  # Reduced data font size
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),  # Services left-aligned
            ('ALIGN', (1, 0), (2, -1), 'CENTER'),  # SAC and QTY centered
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),  # Numbers right-aligned
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('LEFTPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
        ]))
        
        story.append(items_table)
        story.append(Spacer(1, 5))  # Further reduced spacing
        
        # Professional Totals section with currency symbols - Compact version
        totals_data = [
            ['Subtotal:', f"Rs. {invoice.get('subtotal', 0):,.2f}"]
        ]
        
        # Add CGST and SGST only if they exist (same state)
        if invoice.get('cgst_rate', 0) > 0 and invoice.get('sgst_rate', 0) > 0:
            totals_data.append([f"CGST ({invoice.get('cgst_rate', 0):.1f}%):", f"Rs. {invoice.get('cgst_amount', 0):,.2f}"])
            totals_data.append([f"SGST ({invoice.get('sgst_rate', 0):.1f}%):", f"Rs. {invoice.get('sgst_amount', 0):,.2f}"])
        
        # Add IGST only if it exists (different state)
        if invoice.get('igst_rate', 0) > 0:
            totals_data.append([f"IGST ({invoice.get('igst_rate', 0):.1f}%):", f"Rs. {invoice.get('igst_amount', 0):,.2f}"])
        
        # Add other tax if exists
        if invoice.get('tax_amount', 0) > 0:
            totals_data.append(['Other Tax:', f"Rs. {invoice.get('tax_amount', 0):,.2f}"])
        
        totals_data.extend([
            ['Total Amount:', f"Rs. {invoice.get('total_amount', 0):,.2f}"],
            ['Received Amount:', f"Rs. {invoice.get('received_amount', 0):,.2f}"]
        ])
        
        totals_table = Table(totals_data, colWidths=[3.5*inch, 2.5*inch])
        # Calculate the index of the Total Amount row (second to last)
        total_amount_index = len(totals_data) - 2
        
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),  # Reduced font size
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
            ('BACKGROUND', (0, total_amount_index), (-1, total_amount_index), colors.HexColor('#f7fafc')),  # Total Amount row highlighted
            ('TEXTCOLOR', (0, total_amount_index), (-1, total_amount_index), colors.HexColor('#1a365d')),   # Total Amount row in company color
            ('TOPPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
            ('LEFTPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
        ]))
        
        story.append(totals_table)
        story.append(Spacer(1, 5))  # Further reduced spacing
        
        # Professional Total in Words section - Compact version
        total_in_words = convert_number_to_words(float(invoice.get('total_amount', 0)))
        total_words_data = [[f"Total Amount (in words): {total_in_words}"]]
        
        total_words_table = Table(total_words_data, colWidths=[6.5*inch])
        total_words_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),  # Reduced font size
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('LEFTPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
        ]))
        
        story.append(total_words_table)
        story.append(Spacer(1, 6))  # Further reduced spacing
        
        # Professional Bank Details section - Compact version
        bank_data = [
            ['BANK DETAILS'],
            [f"Bank: {bank_details.get('bank_name', 'N/A') if bank_details else 'N/A'}"],
            [f"Account Number: {bank_details.get('account_number', 'N/A') if bank_details else 'N/A'}"],
            [f"IFSC Code: {bank_details.get('ifsc_code', 'N/A') if bank_details else 'N/A'}"]
        ]
        
        bank_table = Table(bank_data, colWidths=[6.5*inch])
        bank_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f7fafc')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),  # Reduced font size
            ('FONTSIZE', (0, 1), (-1, -1), 8),  # Reduced font size
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('LEFTPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
        ]))
        
        story.append(bank_table)
        story.append(Spacer(1, 6))  # Further reduced spacing
        
        # Professional Payment section - Compact version
        payment_data = [
            ['PAYMENT'],
            [f"UPI ID: {bank_details.get('upi_id', 'N/A') if bank_details else 'N/A'}"]
        ]
        
        payment_table = Table(payment_data, colWidths=[6.5*inch])
        payment_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f7fafc')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),  # Reduced font size
            ('FONTSIZE', (0, 1), (-1, -1), 8),  # Reduced font size
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('LEFTPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
        ]))
        
        story.append(payment_table)
        story.append(Spacer(1, 6))  # Further reduced spacing
        
        # Professional Terms and Conditions section - Compact version
        terms_data = [
            ['TERMS AND CONDITIONS'],
            ['1. Service once sold will not be taken back or exchanged'],
            ['2. All disputes are subject to Bidhuna jurisdiction only']
        ]
        
        terms_table = Table(terms_data, colWidths=[6.5*inch])
        terms_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f7fafc')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),  # Reduced font size
            ('FONTSIZE', (0, 1), (-1, -1), 8),  # Reduced font size
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),  # Reduced padding
            ('LEFTPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),  # Reduced padding
        ]))
        
        story.append(terms_table)
        story.append(Spacer(1, 8))  # Further reduced spacing
        
        # Professional Signature section - Compact version
        signature_data = [
            ['', 'Authorised Signatory'],
            ['', 'For Laitusneo Technologies Pvt. Ltd.']
        ]
        
        signature_table = Table(signature_data, colWidths=[4.5*inch, 2*inch])
        signature_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),  # Reduced font size
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1a365d')),  # Signature in company color
        ]))
        
        story.append(signature_table)
        story.append(Spacer(1, 8))  # Reduced space after signature
        
        # Computer-generated invoice disclaimer - Compact version
        disclaimer_style = ParagraphStyle(
            'DisclaimerStyle',
            parent=styles['Normal'],
            fontSize=7,  # Reduced font size
            textColor=colors.HexColor('#718096'),
            alignment=TA_CENTER,
            spaceAfter=3,  # Reduced spacing
            fontName='Helvetica'
        )
        
        disclaimer_text = Paragraph("This is a computer-generated invoice and does not require a signature.", disclaimer_style)
        story.append(disclaimer_text)
        
        # Build PDF
        try:
            doc.build(story)
            print(f"DEBUG: ReportLab PDF generated successfully at {filepath}")
            # Return file path instead of send_file to avoid Flask context issues
            return filepath
        except Exception as e:
            print(f"DEBUG: PDF build failed: {e}")
            # Return error response
            return {'error': f'PDF build failed: {str(e)}'}, 500
        
    except Exception as e:
        print(f"DEBUG: ReportLab fallback error: {e}")
        # Return a simple error response without jsonify to avoid Flask context issues
        return {'error': f'PDF generation failed: {str(e)}'}, 500

def generate_pdftemp_with_reportlab(invoice, items, company, bank_details, filepath, filename):
    """Generate pdftemp-style PDF using ReportLab with exact pdftemp.html layout"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.pdfgen import canvas
        
        print("DEBUG: Using ReportLab to generate pdftemp-style PDF")
        
        # Reduce margins to fit everything on one page with better spacing
        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles matching pdftemp.html design
        company_style = ParagraphStyle(
            'CompanyStyle',
            parent=styles['Title'],
            fontSize=20,
            textColor=colors.black,
            alignment=TA_LEFT,
            spaceAfter=5
        )
        
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Heading1'],
            fontSize=14,
            textColor=colors.black,
            alignment=TA_LEFT,
            spaceAfter=8,
            spaceBefore=15
        )
        

        
        # Header with logo and company info (left side) - Improved layout
        header_data = [
            ['⚡ LAITUSNEO ⚡', f"Invoice #: {invoice['invoice_number']}"],
            ['Laitusneo Technologies Pvt. Ltd.', f"Date: {invoice['invoice_date']}"],
            ['NH2, Agra Road, Shanti Colony, near ITI Chauraha, Etawah, UP, 206001', f"Due Date: {invoice['due_date'] if invoice['due_date'] else 'N/A'}"],
            ['Mobile: 8265915605 | GSTIN: 09JMVPK4466C1ZE', f"Status: {invoice['status'].upper()}"]
        ]
        
        header_table = Table(header_data, colWidths=[4*inch, 2*inch])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 14),  # Logo text larger and more prominent
            ('FONTSIZE', (0, 1), (0, 1), 10),   # Company name
            ('FONTSIZE', (0, 2), (-1, -1), 8),  # Address and other details
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TEXTCOLOR', (0, 0), (0, 0), colors.HexColor('#1f4e79')),  # Logo in company blue
        ]))
        
        story.append(header_table)
        story.append(Spacer(1, 10))  # Reduced spacing
        
        # Get the correct billing label using our helper function
        bill_label = get_bill_label_for_reportlab(invoice)
        print(f"DEBUG: Using bill label in pdftemp_with_reportlab: {bill_label}")
        
        # Bill To section with border (exactly like pdftemp.html)
        bill_to_data = [
            [bill_label],
            [f"Company Name: {invoice.get('billing_company_name', '') or invoice.get('client_name', '')}"],
            [f"Address: {invoice.get('billing_address', '') or invoice.get('client_address', '')}"],
            [f"GSTIN: {invoice.get('gstin_number', '')}"],
            [f"PAN Number: {invoice.get('pan_number', '')}"],
            [f"State: {invoice.get('billing_state', '')}"],
            [f"PIN: {invoice.get('billing_pin', '')}"],
        ]
        
        bill_to_table = Table(bill_to_data, colWidths=[6*inch])
        bill_to_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),  # Reduced left padding for better alignment
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),  # Reduced right padding for consistency
        ]))
        
        story.append(bill_to_table)
        story.append(Spacer(1, 10))  # Reduced spacing
        
        # Items table (exactly like pdftemp.html)
        items_data = [['Services', 'SAC', 'QTY', 'Rate', 'Tax', 'Amount']]
        for item in items:
            items_data.append([
                item['description'],
                item.get('sac_code', '998313'),
                str(item['quantity']),
                f"Rs. {float(item['unit_price']):,.2f}",  # Added space after Rs. for better alignment
                f"{item.get('tax_rate', 18)}%",
                f"Rs. {float(item['total_price']):,.2f}"  # Added space after Rs. for better alignment
            ])
        
        items_table = Table(items_data, colWidths=[2.5*inch, 0.8*inch, 0.8*inch, 1*inch, 0.8*inch, 1*inch])
        items_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Description left-aligned
            ('ALIGN', (3, 1), (3, -1), 'RIGHT'),  # Rate right-aligned
            ('ALIGN', (5, 1), (5, -1), 'RIGHT'),  # Amount right-aligned
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        
        story.append(items_table)
        story.append(Spacer(1, 10))  # Reduced spacing
        
        # Totals section (exactly like pdftemp.html)
        subtotal = float(invoice.get('subtotal', 0))
        cgst_rate = float(invoice.get('cgst_rate', 0))
        cgst_amount = float(invoice.get('cgst_amount', 0))
        sgst_rate = float(invoice.get('sgst_rate', 0))
        sgst_amount = float(invoice.get('sgst_amount', 0))
        total_amount = float(invoice.get('total_amount', 0))
        received_amount = float(invoice.get('received_amount', 0))
        
        totals_data = [
            ['Subtotal:', f"Rs. {subtotal:,.2f}"],
            [f'CGST ({cgst_rate:.1f}%):', f"Rs. {cgst_amount:,.2f}"],
            [f'SGST ({sgst_rate:.1f}%):', f"Rs. {sgst_amount:,.2f}"],
            ['Total Amount:', f"Rs. {total_amount:,.2f}"],
            ['Received Amount:', f"Rs. {received_amount:,.2f}"],
        ]
        
        totals_table = Table(totals_data, colWidths=[2*inch, 1.5*inch])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, -2), (-1, -2), colors.lightgrey),  # Highlight total amount
            ('FONTSIZE', (0, -2), (-1, -2), 10),  # Larger font for total amount
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        
        # Right-align the totals table
        totals_table.hAlign = 'RIGHT'
        story.append(totals_table)
        story.append(Spacer(1, 8))  # Reduced spacing
        
        # Total in Words section (exactly like pdftemp.html)
        total_words_data = [
            [f"Total Amount (in words): {convert_number_to_words(total_amount)}"]
        ]
        
        total_words_table = Table(total_words_data, colWidths=[6*inch])
        total_words_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),  # Consistent padding with other sections
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),  # Consistent padding with other sections
        ]))
        
        story.append(total_words_table)
        story.append(Spacer(1, 10))  # Reduced spacing
        
        # Bank Details section (exactly like pdftemp.html)
        bank_data = [
            ['BANK DETAILS'],
            [f"Bank: {bank_details.get('bank_name', 'N/A') if bank_details else 'N/A'}"],
            [f"Account Number: {bank_details.get('account_number', 'N/A') if bank_details else 'N/A'}"],
            [f"IFSC Code: {bank_details.get('ifsc_code', 'N/A') if bank_details else 'N/A'}"],
        ]
        
        bank_table = Table(bank_data, colWidths=[6*inch])
        bank_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),  # Consistent padding with BILL TO section
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),  # Consistent padding with BILL TO section
        ]))
        
        story.append(bank_table)
        story.append(Spacer(1, 10))  # Reduced spacing
        
        # Payment section (exactly like pdftemp.html)
        payment_data = [
            ['PAYMENT'],
            [f"UPI ID: {bank_details.get('upi_id', 'N/A') if bank_details else 'N/A'}"],
        ]
        
        payment_table = Table(payment_data, colWidths=[6*inch])
        payment_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),  # Consistent padding with other sections
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),  # Consistent padding with other sections
        ]))
        
        story.append(payment_table)
        story.append(Spacer(1, 10))  # Reduced spacing
        
        # Terms and Conditions section (exactly like pdftemp.html)
        terms_data = [
            ['TERMS AND CONDITIONS'],
            ['1. Service once sold will not be taken back or exchanged'],
            ['2. All disputes are subject to Bidhuna jurisdiction only'],
        ]
        
        terms_table = Table(terms_data, colWidths=[6*inch])
        terms_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),  # Consistent padding with other sections
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),  # Consistent padding with other sections
        ]))
        
        story.append(terms_table)
        story.append(Spacer(1, 15))  # Reduced spacing
        
        # Signature section - Improved version
        signature_data = [
            ['', ''],
            ['', '_________________'],
            ['', 'Authorised Signatory'],
            ['', 'For Laitusneo Technologies Pvt. Ltd.'],
        ]
        
        signature_table = Table(signature_data, colWidths=[4*inch, 2*inch])
        signature_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (1, 2), (1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        
        story.append(signature_table)
        
        # Build PDF
        doc.build(story)
        
        print(f"DEBUG: pdftemp ReportLab PDF generated successfully at {filepath}")
        return filepath
        
    except Exception as e:
        print(f"DEBUG: ReportLab pdftemp generation error: {e}")
        return generate_default_invoice_pdf(invoice, items, company, filepath, filename)

def generate_default_invoice_pdf_file(invoice, items, company, filepath, filename):
    """Generate default invoice PDF and save to file (returns boolean)"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        
        print(f"DEBUG: Generating default PDF at {filepath}")
        
        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1f4e79'),
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1f4e79'),
            spaceBefore=20,
            spaceAfter=10
        )
        
        # Title
        story.append(Paragraph("INVOICE", title_style))
        story.append(Spacer(1, 20))
        
        # Company Info Section
        if company:
            story.append(Paragraph(f"<b>{company.get('company_name', 'Your Company')}</b>", styles['Heading3']))
            if company.get('company_address'):
                story.append(Paragraph(company['company_address'], styles['Normal']))
            if company.get('company_phone'):
                story.append(Paragraph(f"Phone: {company['company_phone']}", styles['Normal']))
            if company.get('company_email'):
                story.append(Paragraph(f"Email: {company['company_email']}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Invoice Details
        invoice_data = [
            ['Invoice #:', str(invoice.get('invoice_number', 'N/A')), 'Date:', str(invoice.get('invoice_date', 'N/A'))],
            ['Client:', str(invoice.get('client_name', 'N/A')), 'Due Date:', str(invoice.get('due_date', 'N/A'))],
        ]
        
        invoice_table = Table(invoice_data, colWidths=[1.5*inch, 2*inch, 1*inch, 1.5*inch])
        invoice_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
        ]))
        story.append(invoice_table)
        story.append(Spacer(1, 30))
        
        # Items Table
        if items and len(items) > 0:
            items_data = [['Description', 'Qty', 'Rate', 'Amount']]
            for item in items:
                items_data.append([
                    str(item.get('description', 'N/A')),
                    str(item.get('quantity', 1)),
                    f"₹{float(item.get('unit_price', 0)):,.2f}",
                    f"₹{float(item.get('total_price', 0)):,.2f}"
                ])
        else:
            items_data = [
                ['Description', 'Qty', 'Rate', 'Amount'],
                ['Manual PDF Entry - See details in original PDF', '1', f"₹{float(invoice.get('total_amount', 0)):,.2f}", f"₹{float(invoice.get('total_amount', 0)):,.2f}"]
            ]
        
        # Add totals
        items_data.extend([
            ['', '', 'Subtotal:', f"₹{float(invoice.get('subtotal', 0)):,.2f}"],
            ['', '', 'CGST:', f"₹{float(invoice.get('cgst_amount', 0)):,.2f}"],
            ['', '', 'SGST:', f"₹{float(invoice.get('sgst_amount', 0)):,.2f}"],
            ['', '', 'Tax:', f"₹{float(invoice.get('tax_amount', 0)):,.2f}"],
            ['', '', 'Total:', f"₹{float(invoice.get('total_amount', 0)):,.2f}"]
        ])
        
        items_table = Table(items_data, colWidths=[3*inch, 0.8*inch, 1*inch, 1.2*inch])
        items_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4e79')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, -5), (-1, -1), colors.lightgrey),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 40))
        
        # Notes section
        if invoice.get('notes'):
            story.append(Paragraph("Notes:", styles['Heading3']))
            story.append(Paragraph(str(invoice['notes']), styles['Normal']))
        
        # Build PDF
        doc.build(story)
        print(f"DEBUG: Default PDF generated successfully at {filepath}")
        return True
        
    except Exception as e:
        print(f"DEBUG: Error generating default PDF: {e}")
        return False











    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16)/255.0 for i in (0, 2, 4))


# CSV Export Routes
@app.route('/api/export/expenses')
@login_required
def export_expenses_csv():
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM expenses WHERE user_id = %s ORDER BY expense_date DESC", (session['user_id'],))
        expenses = cursor.fetchall()
        cursor.close()
        connection.close()
        
        filename = f"expenses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(app.config['EXPORT_FOLDER'], filename)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            if expenses:
                fieldnames = expenses[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(expenses)
        
        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/export/transactions')
@login_required
def export_transactions_csv():
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM transactions WHERE user_id = %s ORDER BY transaction_date DESC", (session['user_id'],))
        transactions = cursor.fetchall()
        cursor.close()
        connection.close()
        
        filename = f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(app.config['EXPORT_FOLDER'], filename)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            if transactions:
                fieldnames = transactions[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(transactions)
        
        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/invoices/<int:invoice_id>/status', methods=['PUT'])
@login_required
def update_invoice_status(invoice_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status or new_status not in ['draft', 'sent', 'paid', 'overdue']:
            return jsonify({'error': 'Invalid status. Must be draft, sent, paid, or overdue'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Ensure required columns exist in invoices table
        try:
            cursor.execute("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS bank_account_id INT NULL")
            connection.commit()
        except Exception as e:
            print(f"Warning: Could not add bank_account_id column: {e}")
        
        # Update invoice status
        cursor.execute("""
            UPDATE invoices 
            SET status = %s, updated_at = NOW()
            WHERE id = %s AND user_id = %s
        """, (new_status, invoice_id, session['user_id']))
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Invoice not found'}), 404
        
        # If status is being changed to 'paid', create a transaction
        transaction_id = None
        if new_status == 'paid':
            # Get invoice details for transaction creation
            cursor.execute("""
                SELECT invoice_type, total_amount, invoice_number, client_name 
                FROM invoices 
                WHERE id = %s AND user_id = %s
            """, (invoice_id, session['user_id']))
            invoice_details = cursor.fetchone()
            
            if invoice_details:
                invoice_type, total_amount, invoice_number, client_name = invoice_details
                # Get bank account ID from invoice
                cursor.execute("SELECT bank_account_id FROM invoices WHERE id = %s", (invoice_id,))
                bank_result = cursor.fetchone()
                bank_account_id = bank_result[0] if bank_result else None
                transaction_id = create_invoice_transaction(invoice_id, invoice_type, total_amount, invoice_number, client_name, bank_account_id, user_id=session['user_id'])
        
        # If status is being changed from 'paid' to something else, reverse the bank balance
        elif new_status != 'paid':
            # Check if there was a previous transaction for this invoice
            cursor.execute("""
                SELECT t.id, t.amount, t.transaction_type, t.bank_account_id, i.invoice_type
                FROM transactions t
                JOIN invoices i ON t.source_id = i.id AND t.source = 'invoice'
                WHERE t.source_id = %s AND t.user_id = %s
            """, (invoice_id, session['user_id']))
            
            transaction_details = cursor.fetchone()
            if transaction_details:
                transaction_id, amount, transaction_type, bank_account_id, invoice_type = transaction_details
                
                if bank_account_id:
                    try:
                        if invoice_type == 'in':
                            # Reverse IN invoice: deduct money from bank account (was credit)
                            cursor.execute("""
                                UPDATE bank_accounts 
                                SET current_balance = current_balance - %s 
                                WHERE id = %s AND user_id = %s
                            """, (float(amount), bank_account_id, session['user_id']))
                            print(f"Reversed IN invoice to {new_status}: Deducted ₹{amount} from bank account {bank_account_id}")
                        else:
                            # Reverse OUT invoice: add money back to bank account (was debit)
                            cursor.execute("""
                                UPDATE bank_accounts 
                                SET current_balance = current_balance + %s 
                                WHERE id = %s AND user_id = %s
                            """, (float(amount), bank_account_id, session['user_id']))
                            print(f"Reversed OUT invoice to {new_status}: Added ₹{amount} back to bank account {bank_account_id}")
                        
                        if cursor.rowcount == 0:
                            print(f"Warning: Could not reverse bank balance for invoice {invoice_id}")
                        
                    except Exception as bank_error:
                        print(f"Error reversing bank balance for invoice status change: {bank_error}")
                        # Don't fail the status update if balance reversal fails
                
                # Delete the associated transaction since invoice is no longer paid
                try:
                    cursor.execute("DELETE FROM transactions WHERE id = %s AND user_id = %s", 
                                 (transaction_id, session['user_id']))
                    if cursor.rowcount > 0:
                        print(f"Deleted associated transaction {transaction_id} for invoice {invoice_id} (status changed to {new_status})")
                except Exception as trans_error:
                    print(f"Warning: Could not delete associated transaction: {trans_error}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'message': 'Invoice status updated successfully', 
            'status': new_status,
            'transaction_id': transaction_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/invoices/<int:invoice_id>', methods=['DELETE'])
@login_required
def delete_invoice(invoice_id):
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # First, get invoice details for balance reversal
        cursor.execute("""
            SELECT invoice_type, total_amount, bank_account_id, status, expense_id,
                   approved_payment_method, approved_bank_account_id
            FROM invoices 
            WHERE id=%s AND user_id=%s
        """, (invoice_id, session['user_id']))
        
        invoice_details = cursor.fetchone()
        if not invoice_details:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Invoice not found'}), 404
        
        invoice_type, total_amount, bank_account_id, status, expense_id, approved_payment_method, approved_bank_account_id = invoice_details
        
        # Check if this invoice was already marked as deleted by expense deletion
        if status == 'deleted_by_expense':
            print(f"Invoice {invoice_id} was already marked as deleted by expense deletion - proceeding with cleanup only")
            # Just delete the invoice without balance adjustment
            cursor.execute("DELETE FROM invoices WHERE id = %s AND user_id = %s", (invoice_id, session['user_id']))
            if cursor.rowcount > 0:
                print(f"Successfully cleaned up invoice {invoice_id} that was marked as deleted by expense")
            connection.commit()
            cursor.close()
            connection.close()
            return jsonify({'message': 'Invoice cleaned up successfully'})
        
        # Check if the invoice still exists (might have been deleted by expense deletion)
        cursor.execute("SELECT id FROM invoices WHERE id = %s AND user_id = %s", (invoice_id, session['user_id']))
        if not cursor.fetchone():
            print(f"Invoice {invoice_id} no longer exists - might have been deleted by expense deletion")
            connection.commit()
            cursor.close()
            connection.close()
            return jsonify({'message': 'Invoice already deleted'})
        
        # Check if the associated expense still exists
        expense_exists = False
        if expense_id:
            cursor.execute("SELECT id FROM expenses WHERE id = %s AND user_id = %s", (expense_id, session['user_id']))
            expense_exists = cursor.fetchone() is not None
            print(f"Invoice {invoice_id} associated with expense {expense_id}, expense exists: {expense_exists}")
        
        # Handle refunds for ALL OUT invoices (regardless of status)
        # If a linked expense exists, we'll remove it here to avoid double adjustments and refund exactly once
        print(f"DEBUG: Checking refund conditions - invoice_type: {invoice_type}, status: {status}, expense_exists: {expense_exists}")
        if invoice_type == 'out':
            print(f"Processing refund for OUT invoice {invoice_id} deletion (status: {status})")
            print(f"Payment details - approved_payment_method: {approved_payment_method}, approved_bank_account_id: {approved_bank_account_id}, bank_account_id: {bank_account_id}")
            try:
                # Determine refund method and account based on invoice status and available data
                refund_payment_method = None
                refund_bank_account_id = None
                
                if status == 'approved' and approved_payment_method:
                    # Use exact approval details for approved invoices
                    refund_payment_method = approved_payment_method
                    if approved_payment_method == 'bank' and approved_bank_account_id:
                        refund_bank_account_id = approved_bank_account_id
                        print(f"APPROVED INVOICE: Refunding to selected bank account ID: {refund_bank_account_id}")
                    elif approved_payment_method == 'cash':
                        refund_bank_account_id = None
                        print(f"APPROVED INVOICE: Refunding to cash (as selected during approval)")
                    else:
                        print(f"APPROVED INVOICE: Unknown payment method '{approved_payment_method}', defaulting to cash")
                        refund_payment_method = 'cash'
                elif bank_account_id:
                    # Use original bank account for paid invoices
                    refund_payment_method = 'bank'
                    refund_bank_account_id = bank_account_id
                    print(f"PAID INVOICE: Using original bank account: {refund_bank_account_id}")
                else:
                    # Default to cash for other OUT invoices
                    refund_payment_method = 'cash'
                    refund_bank_account_id = None
                    print(f"OTHER INVOICE: Defaulting to cash refund")
                
                # Get the invoice number for transaction lookup
                cursor.execute("SELECT invoice_number FROM invoices WHERE id = %s", (invoice_id,))
                invoice_number_result = cursor.fetchone()
                invoice_number = invoice_number_result[0] if invoice_number_result else f"INV{invoice_id}"
                print(f"DEBUG: Looking for transactions with invoice_number: {invoice_number}")
                
                # Find and delete related debit transactions
                cursor.execute("""
                    SELECT id, title, description, amount FROM transactions 
                    WHERE user_id = %s 
                    AND transaction_type = 'debit' 
                    AND (category = 'invoice_payment' OR category = 'invoice') 
                    AND (title LIKE %s OR description LIKE %s)
                """, (session['user_id'], f"%{invoice_number}%", f"%{invoice_number}%"))
                transactions_to_delete = cursor.fetchall()
                print(f"DEBUG: Found {len(transactions_to_delete)} transactions to delete:")
                for txn in transactions_to_delete:
                    print(f"  ID: {txn[0]}, Title: {txn[1]}, Amount: {txn[3]}")
                
                # Delete the transactions
                if transactions_to_delete:
                    cursor.execute("""
                        DELETE FROM transactions 
                        WHERE user_id = %s 
                        AND transaction_type = 'debit' 
                        AND (category = 'invoice_payment' OR category = 'invoice') 
                        AND (title LIKE %s OR description LIKE %s)
                    """, (session['user_id'], f"%{invoice_number}%", f"%{invoice_number}%"))
                    deleted_transactions = cursor.rowcount
                    print(f"DEBUG: Deleted {deleted_transactions} transaction(s) for OUT invoice {invoice_id}")
                
                # Process refund based on the exact payment method used during approval
                if refund_payment_method == 'bank' and refund_bank_account_id:
                    # BANK REFUND - Refund to the specific bank account selected during approval
                    print(f"🏦 PROCESSING BANK REFUND to account ID: {refund_bank_account_id}")
                    
                    # Check current balance before refund
                    cursor.execute("SELECT current_balance, bank_name FROM bank_accounts WHERE id = %s AND user_id = %s", 
                                 (refund_bank_account_id, session['user_id']))
                    bank_result = cursor.fetchone()
                    if bank_result:
                        current_balance, bank_name = bank_result
                        print(f"DEBUG: Bank '{bank_name}' current balance before refund: ₹{current_balance}")
                        
                        # Refund to the specific bank account
                        cursor.execute("""
                            UPDATE bank_accounts 
                            SET current_balance = current_balance + %s 
                            WHERE id = %s AND user_id = %s
                        """, (float(total_amount), refund_bank_account_id, session['user_id']))
                        affected_rows = cursor.rowcount
                        print(f"DEBUG: Bank update affected {affected_rows} rows")
                        
                        if affected_rows > 0:
                            # Check balance after refund
                            cursor.execute("SELECT current_balance FROM bank_accounts WHERE id = %s AND user_id = %s", 
                                         (refund_bank_account_id, session['user_id']))
                            new_balance_result = cursor.fetchone()
                            new_balance = new_balance_result[0] if new_balance_result else 0
                            print(f"✅ SUCCESS: Bank '{bank_name}' new balance after refund: ₹{new_balance}")
                            print(f"💰 Refunded ₹{total_amount} to bank account '{bank_name}' (ID: {refund_bank_account_id})")
                            
                            # Create refund transaction record with bank details
                            refund_unique_id = generate_unique_id('TXN')
                            cursor.execute("""
                                INSERT INTO transactions (
                                    user_id, unique_id, title, description, amount, 
                                    transaction_type, transaction_date, payment_method, 
                                    bank_account_id, category, purpose
                                ) VALUES (
                                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                                )
                            """, (
                                session['user_id'], refund_unique_id,
                                f"Refund - OUT Invoice Deletion - {invoice_number}",
                                f"Refund for deleted OUT invoice {invoice_number} to {bank_name}",
                                float(total_amount),  # Positive for refund
                                'credit', 
                                datetime.now().date(),
                                f'{bank_name}',  # Show actual bank name instead of generic 'bank'
                                refund_bank_account_id,
                                'invoice_refund', 'out_invoice_deletion_refund'
                            ))
                            print(f"📝 Created refund transaction record for bank account '{bank_name}'")
                        else:
                            print(f"❌ ERROR: Could not update bank account {refund_bank_account_id} - account not found")
                    else:
                        print(f"❌ ERROR: Bank account {refund_bank_account_id} not found for refund")
                        
                elif refund_payment_method == 'cash':
                    # CASH REFUND - Refund to cash balance (as selected during approval)
                    print(f"💵 PROCESSING CASH REFUND")
                    
                    # Check current cash balance
                    cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (session['user_id'],))
                    cash_result = cursor.fetchone()
                    current_cash = cash_result[0] if cash_result else 0
                    print(f"DEBUG: Current cash balance before refund: ₹{current_cash}")
                    
                    # Refund to cash balance
                    cursor.execute("""
                        UPDATE users 
                        SET cash_balance = cash_balance + %s 
                        WHERE id = %s
                    """, (float(total_amount), session['user_id']))
                    affected_rows = cursor.rowcount
                    
                    if affected_rows > 0:
                        # Check balance after refund
                        cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (session['user_id'],))
                        new_cash_result = cursor.fetchone()
                        new_cash = new_cash_result[0] if new_cash_result else 0
                        print(f"✅ SUCCESS: New cash balance after refund: ₹{new_cash}")
                        print(f"💰 Refunded ₹{total_amount} to cash balance")
                        
                        # Create refund transaction record
                        refund_unique_id = generate_unique_id('TXN')
                        cursor.execute("""
                            INSERT INTO transactions (
                                user_id, unique_id, title, description, amount, 
                                transaction_type, transaction_date, payment_method, 
                                category, purpose
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                            )
                        """, (
                            session['user_id'], refund_unique_id,
                            f"Refund - OUT Invoice Deletion - {invoice_number}",
                            f"Refund for deleted OUT invoice {invoice_number} to Cash",
                            float(total_amount),  # Positive for refund
                            'credit', 
                            datetime.now().date(),
                            'CASH',  # Show CASH clearly in payment method
                            'invoice_refund', 'out_invoice_deletion_refund'
                        ))
                        print(f"📝 Created refund transaction record for cash balance")
                    else:
                        print(f"❌ ERROR: Could not update cash balance for user {session['user_id']}")
                        
                else:
                    print(f"❌ ERROR: Unknown refund method '{refund_payment_method}' or missing bank account ID")
                
                # If a linked expense exists, delete it and its direct transactions so we don't double adjust later
                if expense_exists and expense_id:
                    try:
                        print(f"DEBUG: Linked expense {expense_id} exists - deleting related transactions and expense")
                        cursor.execute("DELETE FROM transactions WHERE source = 'expense' AND source_id = %s AND user_id = %s", (expense_id, session['user_id']))
                        print(f"DEBUG: Deleted {cursor.rowcount} transaction(s) linked to expense {expense_id}")
                        cursor.execute("DELETE FROM expenses WHERE id=%s AND user_id=%s", (expense_id, session['user_id']))
                        print(f"DEBUG: Deleted linked expense {expense_id}")
                    except Exception as etx:
                        print(f"Warning: Could not clean up linked expense {expense_id}: {etx}")

                if cursor.rowcount == 0 and (bank_account_id or approved_bank_account_id):
                    print(f"Warning: Could not process refund for invoice {invoice_id}")
                
            except Exception as refund_error:
                print(f"Error processing refund for invoice deletion: {refund_error}")
                # Don't fail the deletion if refund fails
        elif invoice_type == 'in' and not expense_exists:
            # Handle IN invoice deletions (reverse the credit)
            if bank_account_id:
                cursor.execute("""
                    UPDATE bank_accounts 
                    SET current_balance = current_balance - %s 
                    WHERE id = %s AND user_id = %s
                """, (float(total_amount), bank_account_id, session['user_id']))
                print(f"Reversed IN invoice deletion: Deducted ₹{total_amount} from bank account {bank_account_id}")
        else:
            if expense_exists:
                print(f"Skipping balance adjustment for invoice {invoice_id} because associated expense {expense_id} still exists")
            elif invoice_type == 'in':
                print(f"Skipping balance adjustment for IN invoice {invoice_id} - no specific logic needed")
            else:
                print(f"Skipping balance adjustment for invoice {invoice_id} - no matching conditions")
            
            # Also delete the associated transaction if it exists
            try:
                # First try to delete by source and source_id
                cursor.execute("DELETE FROM transactions WHERE source = 'invoice' AND source_id = %s AND user_id = %s", 
                             (invoice_id, session['user_id']))
                deleted_count = cursor.rowcount
                
                # Also try to delete by unique_id (in case the transaction was created with the same unique_id as invoice)
                cursor.execute("SELECT unique_id FROM invoices WHERE id = %s AND user_id = %s", (invoice_id, session['user_id']))
                invoice_unique_id_result = cursor.fetchone()
                if invoice_unique_id_result and invoice_unique_id_result[0]:
                    invoice_unique_id = invoice_unique_id_result[0]
                    cursor.execute("DELETE FROM transactions WHERE unique_id = %s AND user_id = %s", 
                                 (invoice_unique_id, session['user_id']))
                    deleted_count += cursor.rowcount
                
                if deleted_count > 0:
                    print(f"Deleted {deleted_count} associated transaction(s) for invoice {invoice_id}")
            except Exception as trans_error:
                print(f"Warning: Could not delete associated transaction: {trans_error}")
        
        # Delete the invoice record
        cursor.execute("DELETE FROM invoices WHERE id=%s AND user_id=%s", (invoice_id, session['user_id']))
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400






@app.route('/api/manual-pdf-invoice', methods=['POST'])
@login_required
def create_manual_pdf_invoice():
    """Create a manual PDF invoice entry with auto-generated invoice number"""
    try:
        data = request.get_json()
        print(f"DEBUG: Received manual invoice data: {data}")
        
        # Validate required fields (template_id no longer required)
        required_fields = ['client_name', 'invoice_date', 'total_amount']
        for field in required_fields:
            if not data.get(field):
                print(f"DEBUG: Missing required field: {field}")
                return jsonify({'error': f'{field.replace("_", " ").title()} is required'}), 400
        
        # Generate random invoice number
        import random
        import string
        invoice_number = 'MAN-' + ''.join(random.choices(string.digits, k=8))
        print(f"DEBUG: Generated invoice number: {invoice_number}")
        
        # Ensure invoice number is unique
        connection = get_db_connection()
        if not connection:
            print("DEBUG: Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Check if invoice number exists and generate new one if needed
        attempts = 0
        while attempts < 10:  # Prevent infinite loop
            cursor.execute("SELECT id FROM invoices WHERE invoice_number = %s", (invoice_number,))
            if not cursor.fetchone():
                break
            invoice_number = 'MAN-' + ''.join(random.choices(string.digits, k=8))
            attempts += 1
        
        print(f"DEBUG: Final invoice number: {invoice_number}")
        
        # Insert manual invoice into database
        india_time = get_india_time()
        try:
            cursor.execute("""
                INSERT INTO invoices (
                    user_id, invoice_number, client_name, billing_company_name, 
                    billing_address, gstin_number, invoice_date, due_date,
                    subtotal, cgst_amount, sgst_amount, tax_amount, total_amount,
                    status, notes, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session['user_id'], invoice_number, data.get('client_name'),
                data.get('billing_company_name'), data.get('billing_address'),
                data.get('gstin_number'), data.get('invoice_date'), data.get('due_date'),
                data.get('subtotal', 0), data.get('cgst_amount', 0),
                data.get('sgst_amount', 0), data.get('tax_amount', 0),
                data.get('total_amount', 0), 'manual', 'Manual PDF Entry',
                india_time, india_time
            ))
            
            invoice_id = cursor.lastrowid
            print(f"DEBUG: Created invoice with ID: {invoice_id}")
            
            # Add a single invoice item for manual entries
            cursor.execute("""
                INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price)
                VALUES (%s, %s, %s, %s, %s)
            """, (invoice_id, 'Manual PDF Entry - See PDF for details', 1, 
                  data.get('total_amount', 0), data.get('total_amount', 0)))
            
            # Add bank details if provided
            if any([data.get('account_number'), data.get('ifsc_code'), 
                   data.get('bank_name'), data.get('upi_id')]):
                cursor.execute("""
                    INSERT INTO bank_details (
                        invoice_id, account_number, ifsc_code, 
                        bank_name, upi_id
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (
                    invoice_id, data.get('account_number'),
                    data.get('ifsc_code'), data.get('bank_name'), 
                    data.get('upi_id')
                ))
                print("DEBUG: Added bank details")
            
            connection.commit()
            print("DEBUG: Database transaction committed")
        
        except Exception as db_error:
            print(f"DEBUG: Database error: {db_error}")
            connection.rollback()
            cursor.close()
            connection.close()
            return jsonify({'error': f'Database error: {str(db_error)}'}), 500
        
        cursor.close()
        connection.close()
        
        # Generate PDF using pdftemp.html template only
        filename = f"manual_invoice_{invoice_number}.pdf"
        filepath = os.path.join(app.config['EXPORT_FOLDER'], filename)
        print(f"DEBUG: Generating PDF at: {filepath}")
        
        # Create invoice data structure for PDF generation
        invoice_data = {
            'id': invoice_id,
            'invoice_number': invoice_number,
            'client_name': data.get('client_name'),
            'billing_company_name': data.get('billing_company_name'),
            'billing_address': data.get('billing_address'),
            'gstin_number': data.get('gstin_number'),
            'pan_number': data.get('pan_number', ''),
            'billing_state': data.get('billing_state', ''),
            'billing_pin': data.get('billing_pin', ''),
            'invoice_date': data.get('invoice_date'),
            'due_date': data.get('due_date'),
            'subtotal': data.get('subtotal', 0),
            'cgst_amount': data.get('cgst_amount', 0),
            'sgst_amount': data.get('sgst_amount', 0),
            'tax_amount': data.get('tax_amount', 0),
            'total_amount': data.get('total_amount', 0),
            'status': 'manual'
        }
        
        # Company data
        company_data = {
            'company_name': data.get('company_name', 'Your Company'),
            'company_address': data.get('company_address', 'Your Address'),
            'company_phone': data.get('company_phone', 'Your Phone'),
            'company_email': 'info@company.com',
            'tax_number': data.get('company_gstin', 'Your GSTIN')
        }
        
        # Bank details
        bank_data = {
            'account_number': data.get('account_number', ''),
            'ifsc_code': data.get('ifsc_code', ''),
            'bank_name': data.get('bank_name', ''),
            'upi_id': data.get('upi_id', '')
        }
        
        # Items (just one for manual entry)
        items_data = [{
            'description': 'Manual PDF Entry - See PDF for details',
            'quantity': 1,
            'unit_price': data.get('total_amount', 0),
            'total_price': data.get('total_amount', 0),
            'sac_code': '998313'
        }]
        
        print(f"DEBUG: Using pdftemp.html template for manual invoice")
        
        # Use pdftemp.html template for generation
        try:
            result = generate_pdftemp_invoice(invoice_data, items_data, company_data, bank_data, filepath, filename)
            
            # Check if PDF was generated successfully
            if os.path.exists(filepath):
                print(f"DEBUG: PDF generated successfully at {filepath}")
                success = True
            else:
                print("DEBUG: PDF file was not created")
                success = False
                
        except Exception as pdf_error:
            print(f"DEBUG: PDF generation error: {pdf_error}")
            success = False
        
        print(f"DEBUG: PDF generation result: {success}")
        
        if success:
            # Track the manual invoice entry (without template)
            try:
                connection = get_db_connection()
                if connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        "INSERT INTO pdf_download_history (invoice_id, user_id, download_time) VALUES (%s, %s, %s)",
                        (invoice_id, session['user_id'], datetime.now())
                    )
                    connection.commit()
                    cursor.close()
                    connection.close()
                    print("DEBUG: Manual invoice entry tracked in database")
            except Exception as track_error:
                print(f"DEBUG: Warning - Could not track manual invoice entry: {track_error}")
            
            # Return success with download URL
            pdf_url = f"/api/manual-pdf-download/{invoice_id}"
            print(f"DEBUG: Success! PDF URL: {pdf_url}")
            return jsonify({
                'success': True,
                'message': 'Manual PDF invoice created successfully',
                'invoice_number': invoice_number,
                'invoice_id': invoice_id,
                'pdf_url': pdf_url
            })
        else:
            print("DEBUG: PDF generation failed")
            return jsonify({'error': 'Failed to generate PDF'}), 500
            
    except Exception as e:
        print(f"DEBUG: Exception in manual invoice creation: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/invoices/<int:invoice_id>/pdf')
@login_required
def generate_invoice_pdf(invoice_id):
    """Generate and download a PDF for an invoice"""
    try:
        print(f"DEBUG: Generating PDF for invoice {invoice_id}")
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Get invoice data with user_id filter
        cursor.execute("SELECT * FROM invoices WHERE id=%s AND user_id=%s", (invoice_id, session['user_id']))
        invoice = cursor.fetchone()
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Debug invoice data and ensure invoice_type is set
        print(f"DEBUG: Invoice type retrieved from database: {invoice.get('invoice_type', 'none')}")
        
        # Ensure invoice_type is set correctly
        if 'invoice_type' not in invoice or invoice['invoice_type'] is None:
            invoice['invoice_type'] = 'out'
            print("DEBUG: Setting default invoice_type to 'out'")
        else:
            print(f"DEBUG: Using existing invoice_type: {invoice['invoice_type']}")
        
        # Get invoice items
        cursor.execute("SELECT * FROM invoice_items WHERE invoice_id=%s", (invoice_id,))
        items = cursor.fetchall()
        
        # Get company settings for current user
        cursor.execute("SELECT * FROM company_settings WHERE user_id = %s LIMIT 1", (session['user_id'],))
        company = cursor.fetchone()
        
        # Get bank details
        cursor.execute("SELECT * FROM bank_details WHERE invoice_id = %s", (invoice_id,))
        bank_details = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        # Generate PDF
        filename = f"invoice_{invoice['invoice_number']}.pdf"
        filepath = os.path.join(app.config['EXPORT_FOLDER'], filename)
        
        # Ensure exports directory exists
        os.makedirs(app.config['EXPORT_FOLDER'], exist_ok=True)
        
        # Generate the PDF using pdftemp.html template
        result = generate_pdftemp_invoice(invoice, items, company, bank_details, filepath, filename)
        
        # Check if result is a file path (success) or error tuple
        if isinstance(result, str) and os.path.exists(result):
            print(f"DEBUG: PDF generated successfully at {result}")
            
            # Track download in history (if table exists)
            try:
                connection = get_db_connection()
                if connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        "INSERT INTO pdf_download_history (invoice_id, user_id, download_time) VALUES (%s, %s, %s)",
                        (invoice_id, session['user_id'], datetime.now())
                    )
                    connection.commit()
                    cursor.close()
                    connection.close()
            except Exception as track_error:
                print(f"DEBUG: Warning - Could not track invoice download: {track_error}")
            
            return send_file(result, as_attachment=True, download_name=filename)
        else:
            # Handle error case
            error_msg = result[0]['error'] if isinstance(result, tuple) else str(result)
            print(f"DEBUG: PDF generation failed: {error_msg}")
            return jsonify({'error': error_msg}), 500
        
    except Exception as e:
        print(f"DEBUG: Error generating invoice PDF: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/invoices/<int:invoice_id>/expense-file')
@login_required
def download_expense_invoice_file(invoice_id):
    """Download the original uploaded file for expense-generated invoices"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Get invoice data with user_id filter and check if it's expense-generated
        cursor.execute("""
            SELECT i.*, e.bill_file 
            FROM invoices i 
            LEFT JOIN expenses e ON i.expense_id = e.id 
            WHERE i.id = %s AND i.user_id = %s AND i.source_type = 'expense'
        """, (invoice_id, session['user_id']))
        
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if not result:
            return jsonify({'error': 'Expense invoice not found'}), 404
        
        if not result['bill_file']:
            return jsonify({'error': 'No file attached to this expense'}), 404
        
        # Get the file path
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], result['bill_file'])
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found on server'}), 404
        
        # Determine the original filename (remove UUID prefix)
        original_filename = result['bill_file']
        if '_' in original_filename:
            original_filename = '_'.join(original_filename.split('_')[1:])
        
        return send_file(file_path, as_attachment=True, download_name=original_filename)
        
    except Exception as e:
        print(f"Error downloading expense invoice file: {e}")
        return jsonify({'error': str(e)}), 500

# User Bank Management API Endpoints
@app.route('/api/user-banks', methods=['GET'])
@login_required
def get_user_banks():
    """Get all banks for the current user"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM bank_accounts WHERE user_id = %s ORDER BY bank_name", (session['user_id'],))
        banks = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return jsonify(banks)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user-banks', methods=['POST'])
@login_required
def create_user_bank():
    """Create a new bank for the current user"""
    try:
        data = request.get_json()
        
        if not data.get('bank_name') or not data.get('account_number') or not data.get('ifsc_code'):
            return jsonify({'error': 'Bank name, account number, and IFSC code are required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Check if bank account already exists for this user
        cursor.execute("""
            SELECT id FROM bank_accounts 
            WHERE user_id = %s AND bank_name = %s AND account_number = %s
        """, (session['user_id'], data['bank_name'], data['account_number']))
        
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'error': 'A bank account with this name and account number already exists for you'}), 400
        
        # Check if this should be the default bank
        is_default = data.get('is_default', False)
        
        # If setting as default, unset other default banks first
        if is_default:
            cursor.execute("UPDATE bank_accounts SET is_default = FALSE WHERE user_id = %s", (session['user_id'],))
        
        # Create new bank account
        cursor.execute("""
            INSERT INTO bank_accounts (user_id, bank_name, account_number, ifsc_code, upi_id, initial_balance, current_balance, is_default)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            session['user_id'],
            data['bank_name'],
            data['account_number'],
            data['ifsc_code'],
            data.get('upi_id', ''),
            data.get('initial_balance', 0.00),
            data.get('initial_balance', 0.00),
            is_default
        ))
        
        bank_id = cursor.lastrowid
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'id': bank_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user-banks/<int:bank_id>', methods=['PUT'])
@login_required
def update_user_bank(bank_id):
    """Update an existing bank for the current user"""
    try:
        data = request.get_json()
        
        if not data.get('bank_name') or not data.get('account_number') or not data.get('ifsc_code'):
            return jsonify({'error': 'Bank name, account number, and IFSC code are required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Check if updating to an existing bank account's details (excluding current bank)
        cursor.execute("""
            SELECT id FROM bank_accounts 
            WHERE user_id = %s AND bank_name = %s AND account_number = %s AND id != %s
        """, (session['user_id'], data['bank_name'], data['account_number'], bank_id))
        
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'error': 'A bank account with this name and account number already exists for you'}), 400
        
        # Check if this should be the default bank
        is_default = data.get('is_default', False)
        
        # If setting as default, unset other default banks first
        if is_default:
            cursor.execute("UPDATE bank_accounts SET is_default = FALSE WHERE user_id = %s AND id != %s", (session['user_id'], bank_id))
        
        # Update bank account
        cursor.execute("""
            UPDATE bank_accounts 
            SET bank_name = %s, account_number = %s, ifsc_code = %s, upi_id = %s, initial_balance = %s, current_balance = %s, is_default = %s
            WHERE id = %s AND user_id = %s
        """, (
            data['bank_name'],
            data['account_number'],
            data['ifsc_code'],
            data.get('upi_id', ''),
            data.get('initial_balance', 0.00),
            data.get('current_balance', 0.00),
            is_default,
            bank_id,
            session['user_id']
        ))
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Bank not found or not authorized'}), 404
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user-banks/<int:bank_id>', methods=['DELETE'])
@login_required
def delete_user_bank(bank_id):
    """Delete a bank for the current user"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        cursor.execute("DELETE FROM bank_accounts WHERE id = %s AND user_id = %s", (bank_id, session['user_id']))
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Bank not found or not authorized'}), 404
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user-banks/<int:bank_id>/set-default', methods=['POST'])
@login_required
def set_default_bank(bank_id):
    """Set a bank as the default bank for the current user"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # First, unset all other default banks for this user
        cursor.execute("UPDATE bank_accounts SET is_default = FALSE WHERE user_id = %s", (session['user_id'],))
        
        # Set the specified bank as default
        cursor.execute("""
            UPDATE bank_accounts 
            SET is_default = TRUE 
            WHERE id = %s AND user_id = %s
        """, (bank_id, session['user_id']))
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Bank not found or not authorized'}), 404
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Default bank updated successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500









@app.route('/api/manual-pdf-download/<int:invoice_id>')
@login_required
def download_manual_pdf(invoice_id):
    """Download manually generated PDF invoice"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT invoice_number FROM invoices WHERE id = %s AND user_id = %s",
            (invoice_id, session['user_id'])
        )
        invoice = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        filename = f"manual_invoice_{invoice['invoice_number']}.pdf"
        filepath = os.path.join(app.config['EXPORT_FOLDER'], filename)
        
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True, download_name=filename)
        else:
            return jsonify({'error': 'PDF file not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500





# Dashboard API
@dashboard_ns.route('/stats')
class DashboardStats(Resource):
    @api.doc('get_dashboard_stats', security='Bearer')
    @api.response(200, 'Dashboard statistics retrieved successfully')
    @api.response(401, 'Authentication required')
    @api.response(500, 'Database connection failed')
    def get(self):
        """Get dashboard statistics including expenses, transactions, and invoices"""
        if 'user_id' not in session:
            return {'error': 'Authentication required'}, 401
        return get_dashboard_stats()

# Keep the original route for backward compatibility
@app.route('/api/dashboard/stats')
@login_required
def get_dashboard_stats():
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Get expense stats for current user (for display only, NOT used in balance calculation)
        cursor.execute("""
            SELECT 
                COUNT(*) as total_expenses,
                COALESCE(SUM(amount), 0) as total_expense_amount,
                COALESCE(SUM(CASE WHEN expense_type = 'upcoming' THEN amount ELSE 0 END), 0) as upcoming_expenses
            FROM expenses
            WHERE user_id = %s
        """, (session['user_id'],))
        expense_stats = cursor.fetchone()
        
        # Get transaction stats for current user (THIS IS WHAT DETERMINES THE BALANCE)
        cursor.execute("""
            SELECT 
                COUNT(*) as total_transactions,
                COALESCE(SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END), 0) as total_debits,
                COALESCE(SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END), 0) as total_credits,
                COALESCE(SUM(CASE WHEN transaction_type = 'credit' AND (payment_method = 'cash' OR payment_method IS NULL) THEN amount ELSE 0 END), 0) as cash_credits,
                COALESCE(SUM(CASE WHEN transaction_type = 'credit' AND payment_method = 'online' THEN amount ELSE 0 END), 0) as bank_credits,
                COALESCE(SUM(CASE WHEN transaction_type = 'debit' AND (payment_method = 'cash' OR payment_method IS NULL) THEN amount ELSE 0 END), 0) as cash_debits,
                COALESCE(SUM(CASE WHEN transaction_type = 'debit' AND payment_method = 'online' THEN amount ELSE 0 END), 0) as bank_debits
            FROM transactions
            WHERE user_id = %s
        """, (session['user_id'],))
        transaction_stats = cursor.fetchone()
        
        # Get invoice stats for current user
        cursor.execute("""
            SELECT 
                COUNT(*) as total_invoices,
                COALESCE(SUM(total_amount), 0) as total_invoice_amount,
                COALESCE(SUM(CASE WHEN status = 'paid' THEN total_amount ELSE 0 END), 0) as paid_amount,
                COALESCE(SUM(CASE WHEN invoice_type = 'in' THEN total_amount ELSE 0 END), 0) as in_invoice_amount,
                COALESCE(SUM(CASE WHEN invoice_type = 'out' THEN total_amount ELSE 0 END), 0) as out_invoice_amount
            FROM invoices
            WHERE user_id = %s
        """, (session['user_id'],))
        invoice_stats = cursor.fetchone()
        
        # Get recent expenses
        cursor.execute("""
            SELECT title, amount, expense_date, expense_type 
            FROM expenses 
            WHERE user_id = %s
            ORDER BY created_at DESC 
            LIMIT 5
        """, (session['user_id'],))
        recent_expenses = cursor.fetchall()
        
        # Get overdue invoices details
        cursor.execute("""
            SELECT invoice_number, client_name, total_amount, due_date
            FROM invoices 
            WHERE user_id = %s AND status = 'overdue'
            ORDER BY due_date ASC
            LIMIT 10
        """, (session['user_id'],))
        overdue_invoices = cursor.fetchall()
        
        # Get upcoming expenses details
        cursor.execute("""
            SELECT title, amount, expense_date, category
            FROM expenses 
            WHERE user_id = %s AND expense_type = 'upcoming'
            ORDER BY expense_date ASC
            LIMIT 10
        """, (session['user_id'],))
        upcoming_expenses = cursor.fetchall()
        
        # Calculate overdue amounts with detailed statistics
        # Incoming overdue: Invoices that are overdue (money we should receive)
        cursor.execute("""
            SELECT 
                COALESCE(SUM(total_amount), 0) as incoming_overdue,
                COUNT(*) as overdue_invoice_count
            FROM invoices 
            WHERE user_id = %s AND status = 'overdue'
        """, (session['user_id'],))
        incoming_overdue_data = cursor.fetchone()
        incoming_overdue = incoming_overdue_data['incoming_overdue']
        overdue_invoice_count = incoming_overdue_data['overdue_invoice_count']
        
        # Outgoing overdue: Upcoming expenses (money we need to pay out)
        cursor.execute("""
            SELECT 
                COALESCE(SUM(amount), 0) as outgoing_overdue,
                COUNT(*) as upcoming_expense_count
            FROM expenses 
            WHERE user_id = %s AND expense_type = 'upcoming'
        """, (session['user_id'],))
        outgoing_overdue_data = cursor.fetchone()
        outgoing_overdue = outgoing_overdue_data['outgoing_overdue']
        upcoming_expense_count = outgoing_overdue_data['upcoming_expense_count']
        
        # Get stored bank account balances and default bank info BEFORE closing connection
        cursor.execute("""
            SELECT 
                SUM(current_balance) as total_bank_balance,
                SUM(CASE WHEN is_default = TRUE THEN current_balance ELSE 0 END) as default_bank_balance,
                SUM(CASE WHEN is_default = TRUE THEN 1 ELSE 0 END) as has_default_bank
            FROM bank_accounts 
            WHERE user_id = %s
        """, (session['user_id'],))
        bank_result = cursor.fetchone()
        stored_bank_balance = float(bank_result['total_bank_balance'] or 0)
        default_bank_balance = float(bank_result['default_bank_balance'] or 0)
        has_default_bank = bool(bank_result['has_default_bank'])
        
        # Get actual cash balance from users table
        cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (session['user_id'],))
        user_result = cursor.fetchone()
        cash_balance = float(user_result['cash_balance'] or 0) if user_result else 0.0
        
        # Bank balance is the stored balance from bank_accounts table
        # This represents the actual current balance in all bank accounts
        bank_balance = stored_bank_balance
        
        cursor.close()
        connection.close()
        
        # Convert dates to strings for JSON serialization
        for expense in recent_expenses:
            if expense['expense_date']:
                expense['expense_date'] = expense['expense_date'].isoformat()
        
        for invoice in overdue_invoices:
            if invoice['due_date']:
                invoice['due_date'] = invoice['due_date'].isoformat()
        
        for expense in upcoming_expenses:
            if expense['expense_date']:
                expense['expense_date'] = expense['expense_date'].isoformat()
        
        return jsonify({
            'expenses': expense_stats,
            'transactions': transaction_stats,
            'invoices': invoice_stats,
            'recent_expenses': recent_expenses,
            'overdue_invoices': overdue_invoices,
            'upcoming_expenses': upcoming_expenses,
            'overdue': {
                'incoming_overdue': float(incoming_overdue),
                'outgoing_overdue': float(outgoing_overdue),
                'overdue_invoice_count': int(overdue_invoice_count),
                'upcoming_expense_count': int(upcoming_expense_count)
            },
            'balance': cash_balance + bank_balance,  # Simple sum of cash + bank balances
            'cash_balance': cash_balance,
            'bank_balance': bank_balance,
            'default_bank': {
                'has_default': has_default_bank,
                'balance': default_bank_balance
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Profile and Settings API Routes
@app.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, username, email, first_name, last_name, created_at, updated_at
            FROM users 
            WHERE id = %s
        """, (session['user_id'],))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            connection.close()
            return jsonify({'error': 'User not found'}), 404
        
        cursor.close()
        connection.close()
        
        return jsonify(user)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/profile/update', methods=['POST'])
@login_required
def update_profile():
    try:
        data = request.get_json()
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        username = data.get('username')
        email = data.get('email')
        
        if not all([first_name, last_name, username, email]):
            return jsonify({'error': 'All fields are required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Check if username or email already exists for other users
        cursor.execute("""
            SELECT id FROM users 
            WHERE (username = %s OR email = %s) AND id != %s
        """, (username, email, session['user_id']))
        
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'error': 'Username or email already exists'}), 400
        
        # Update user profile
        cursor.execute("""
            UPDATE users 
            SET first_name = %s, last_name = %s, username = %s, email = %s, updated_at = NOW()
            WHERE id = %s
        """, (first_name, last_name, username, email, session['user_id']))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'message': 'Profile updated successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/settings/change-password', methods=['POST'])
@login_required
def change_password():
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not all([current_password, new_password]):
            return jsonify({'error': 'Both current and new passwords are required'}), 400
        
        if len(new_password) < 8:
            return jsonify({'error': 'New password must be at least 8 characters long'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Get current user's password hash
        cursor.execute("SELECT password_hash FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            connection.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Verify current password
        if not check_password_hash(user['password_hash'], current_password):
            cursor.close()
            connection.close()
            return jsonify({'error': 'Current password is incorrect'}), 400
        
        # Hash new password
        new_password_hash = generate_password_hash(new_password)
        
        # Update password
        cursor.execute("""
            UPDATE users 
            SET password_hash = %s, updated_at = NOW()
            WHERE id = %s
        """, (new_password_hash, session['user_id']))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'message': 'Password changed successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT currency, date_format, theme, email_notifications, two_factor_auth
            FROM user_settings 
            WHERE user_id = %s
        """, (session['user_id'],))
        settings = cursor.fetchone()
        
        if not settings:
            # Create default settings if none exist
            cursor.execute("""
                INSERT INTO user_settings (user_id, currency, date_format, theme, email_notifications, two_factor_auth)
                VALUES (%s, 'INR', 'DD/MM/YYYY', 'light', TRUE, FALSE)
            """, (session['user_id'],))
            connection.commit()
            
            settings = {
                'currency': 'INR',
                'date_format': 'DD/MM/YYYY',
                'theme': 'light',
                'email_notifications': True,
                'two_factor_auth': False
            }
        
        cursor.close()
        connection.close()
        
        return jsonify(settings)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/settings/update', methods=['POST'])
@login_required
def update_settings():
    try:
        data = request.get_json()
        currency = data.get('currency', 'INR')
        date_format = data.get('date_format', 'DD/MM/YYYY')
        theme = data.get('theme', 'light')
        email_notifications = data.get('email_notifications', True)
        two_factor_auth = data.get('two_factor_auth', False)
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Check if user settings exist
        cursor.execute("SELECT id FROM user_settings WHERE user_id = %s", (session['user_id'],))
        if cursor.fetchone():
            # Update existing settings
            cursor.execute("""
                UPDATE user_settings 
                SET currency = %s, date_format = %s, theme = %s, email_notifications = %s, two_factor_auth = %s, updated_at = NOW()
                WHERE user_id = %s
            """, (currency, date_format, theme, email_notifications, two_factor_auth, session['user_id']))
        else:
            # Create new settings
            cursor.execute("""
                INSERT INTO user_settings (user_id, currency, date_format, theme, email_notifications, two_factor_auth)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (session['user_id'], currency, date_format, theme, email_notifications, two_factor_auth))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'message': 'Settings updated successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/export/all', methods=['GET'])
@login_required
def export_all_user_data():
    try:
        format_type = request.args.get('format', 'json')
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Get all user data
        data = {
            'user_info': {},
            'expenses': [],
            'transactions': [],
            'invoices': [],
            'invoice_items': [],
            'company_settings': {},
            'exported_at': datetime.now().isoformat()
        }
        
        # Get user info
        cursor.execute("SELECT id, username, email, first_name, last_name, created_at FROM users WHERE id = %s", (session['user_id'],))
        data['user_info'] = cursor.fetchone()
        
        # Get expenses
        cursor.execute("SELECT * FROM expenses WHERE user_id = %s", (session['user_id'],))
        expenses = cursor.fetchall()
        for expense in expenses:
            if expense['expense_date']:
                expense['expense_date'] = expense['expense_date'].isoformat()
            if expense['created_at']:
                expense['created_at'] = expense['created_at'].isoformat()
            if expense['updated_at']:
                expense['updated_at'] = expense['updated_at'].isoformat()
        data['expenses'] = expenses
        
        # Get transactions
        cursor.execute("SELECT * FROM transactions WHERE user_id = %s", (session['user_id'],))
        transactions = cursor.fetchall()
        for transaction in transactions:
            if transaction['transaction_date']:
                transaction['transaction_date'] = transaction['transaction_date'].isoformat()
            if transaction['created_at']:
                transaction['created_at'] = transaction['created_at'].isoformat()
            if transaction['updated_at']:
                transaction['updated_at'] = transaction['updated_at'].isoformat()
        data['transactions'] = transactions
        
        # Get invoices
        cursor.execute("SELECT * FROM invoices WHERE user_id = %s", (session['user_id'],))
        invoices = cursor.fetchall()
        for invoice in invoices:
            if invoice['invoice_date']:
                invoice['invoice_date'] = invoice['invoice_date'].isoformat()
            if invoice['due_date']:
                invoice['due_date'] = invoice['due_date'].isoformat()
            if invoice['created_at']:
                invoice['created_at'] = invoice['created_at'].isoformat()
            if invoice['updated_at']:
                invoice['updated_at'] = invoice['updated_at'].isoformat()
        data['invoices'] = invoices
        
        # Get invoice items
        cursor.execute("""
            SELECT ii.* FROM invoice_items ii 
            JOIN invoices i ON ii.invoice_id = i.id 
            WHERE i.user_id = %s
        """, (session['user_id'],))
        data['invoice_items'] = cursor.fetchall()
        
        # Get company settings
        cursor.execute("SELECT * FROM company_settings WHERE user_id = %s", (session['user_id'],))
        company_settings = cursor.fetchone()
        if company_settings:
            if company_settings['created_at']:
                company_settings['created_at'] = company_settings['created_at'].isoformat()
            if company_settings['updated_at']:
                company_settings['updated_at'] = company_settings['updated_at'].isoformat()
        data['company_settings'] = company_settings
        
        cursor.close()
        connection.close()
        
        if format_type == 'json':
            return jsonify(data)
        elif format_type == 'csv':
            # Convert to CSV format (simplified)
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write expenses
            writer.writerow(['Type', 'Description', 'Amount', 'Date'])
            for expense in data['expenses']:
                writer.writerow(['Expense', expense['title'], expense['amount'], expense['expense_date']])
            
            for transaction in data['transactions']:
                writer.writerow(['Transaction', transaction['description'], transaction['amount'], transaction['transaction_date']])
            
            output.seek(0)
            return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=expense_data.csv'})
        else:
            return jsonify({'error': 'Unsupported format'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/settings/delete-account', methods=['DELETE'])
@login_required
def delete_account():
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Delete all user data (cascade delete would be better in production)
        # Check if tables exist before deleting
        tables_to_clean = [
            ('expenses', 'user_id'),
            ('transactions', 'user_id'),
            ('invoice_items', 'invoice_id IN (SELECT id FROM invoices WHERE user_id = %s)'),
            ('invoices', 'user_id'),
            ('company_settings', 'user_id'),
            ('invoice_templates', 'user_id'),
            ('user_settings', 'user_id')
        ]
        
        for table_name, where_clause in tables_to_clean:
            try:
                if where_clause == 'invoice_id IN (SELECT id FROM invoices WHERE user_id = %s)':
                    cursor.execute(f"DELETE FROM {table_name} WHERE {where_clause}", (session['user_id'],))
                else:
                    cursor.execute(f"DELETE FROM {table_name} WHERE {where_clause} = %s", (session['user_id'],))
            except Exception as e:
                print(f"Warning: Could not delete from {table_name}: {e}")
                # Continue with other tables
        
        # Try to delete from file_uploads if it exists
        try:
            cursor.execute("DELETE FROM file_uploads WHERE user_id = %s", (session['user_id'],))
        except Exception as e:
            print(f"Warning: Could not delete from file_uploads: {e}")
        
        # Finally delete the user
        cursor.execute("DELETE FROM users WHERE id = %s", (session['user_id'],))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        # Clear session
        session.clear()
        
        return jsonify({'message': 'Account deleted successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# Invoice Template API Routes
@app.route('/api/templates', methods=['GET'])
@login_required
def get_templates():
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, name, description, template_type, is_default, created_at, updated_at
            FROM invoice_templates 
            WHERE user_id = %s
            ORDER BY is_default DESC, created_at DESC
        """, (session['user_id'],))
        templates = cursor.fetchall()
        
        # Convert date objects to strings
        for template in templates:
            if template['created_at']:
                template['created_at'] = template['created_at'].isoformat()
            if template['updated_at']:
                template['updated_at'] = template['updated_at'].isoformat()
        
        cursor.close()
        connection.close()
        return jsonify(templates)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/templates/upload', methods=['POST'])
@login_required
def upload_template():
    try:
        print("DEBUG: Template upload request received")
        print("DEBUG: Form data:", request.form)
        print("DEBUG: Files:", request.files)
        
        template_name = request.form.get('template_name')
        template_description = request.form.get('template_description', '')
        template_type = request.form.get('template_type', 'html')
        
        print(f"DEBUG: Template type: {template_type}")
        print(f"DEBUG: Template name: {template_name}")
        
        if not template_name:
            return jsonify({'error': 'Template name is required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # If this is the first template, make it default
        cursor.execute("SELECT COUNT(*) as count FROM invoice_templates WHERE user_id = %s", (session['user_id'],))
        is_first_template = cursor.fetchone()[0] == 0
        
        if template_type == 'html':
            # Handle HTML template upload
            if 'template_file' not in request.files:
                return jsonify({'error': 'No HTML file uploaded'}), 400
            
            file = request.files['template_file']
            if not file or file.filename == '':
                return jsonify({'error': 'No HTML file selected'}), 400
            
            # Check file extension
            if not file.filename.lower().endswith(('.html', '.htm')):
                return jsonify({'error': 'Only HTML files are allowed for HTML templates'}), 400
            
            # Read file content
            html_content = file.read().decode('utf-8')
            
            # Basic validation - check if it contains some basic HTML structure
            if '<html' not in html_content.lower() and '<body' not in html_content.lower():
                return jsonify({'error': 'Invalid HTML file. Please upload a valid HTML template.'}), 400
            
            # Insert HTML template
            cursor.execute("""
                INSERT INTO invoice_templates (user_id, name, description, template_type, html_content, is_default)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                session['user_id'],
                template_name,
                template_description,
                template_type,
                html_content,
                is_first_template
            ))
            
        elif template_type == 'pdf':
            print("DEBUG: Processing PDF template upload")
            # Handle PDF template upload
            if 'pdf_template_file' not in request.files:
                print("DEBUG: No pdf_template_file in request.files")
                return jsonify({'error': 'No PDF file uploaded'}), 400
            
            file = request.files['pdf_template_file']
            print(f"DEBUG: PDF file: {file}")
            print(f"DEBUG: PDF filename: {file.filename}")
            
            if not file or file.filename == '':
                print("DEBUG: No PDF file selected")
                return jsonify({'error': 'No PDF file selected'}), 400
            
            # Check file extension
            if not file.filename.lower().endswith('.pdf'):
                print(f"DEBUG: Invalid file extension: {file.filename}")
                return jsonify({'error': 'Only PDF files are allowed for PDF templates'}), 400
            
            # Save PDF file
            filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename)
            pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'templates', filename)
            
            print(f"DEBUG: Saving PDF to: {pdf_path}")
            
            # Create templates directory if it doesn't exist
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            
            file.save(pdf_path)
            print("DEBUG: PDF file saved successfully")
            
            # Insert PDF template
            cursor.execute("""
                INSERT INTO invoice_templates (user_id, name, description, template_type, pdf_file_path, is_default)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                session['user_id'],
                template_name,
                template_description,
                template_type,
                filename,
                is_first_template
            ))
        
        else:
            return jsonify({'error': 'Invalid template type'}), 400
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'message': 'Template uploaded successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/test-pdf-upload')
def test_pdf_upload():
    """Test page for PDF upload functionality"""
    return send_file('test_pdf_upload.html')

@app.route('/api/templates/<int:template_id>/preview', methods=['GET'])
@login_required
def preview_template(template_id):
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT template_type, html_content, pdf_file_path FROM invoice_templates 
            WHERE id = %s AND user_id = %s
        """, (template_id, session['user_id']))
        template = cursor.fetchone()
        
        if not template:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Template not found'}), 404
        
        cursor.close()
        connection.close()
        
        if template['template_type'] == 'html':
            return jsonify({
                'template_type': 'html',
                'html_content': template['html_content']
            })
        elif template['template_type'] == 'pdf':
            # For PDF templates, return the file path for download/preview
            pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'templates', template['pdf_file_path'])
            if os.path.exists(pdf_path):
                return send_file(pdf_path, as_attachment=False, download_name=template['pdf_file_path'])
            else:
                return jsonify({'error': 'PDF file not found'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>/set-default', methods=['POST'])
@login_required
def set_default_template(template_id):
    print(f"DEBUG: Setting template {template_id} as default for user {session['user_id']}")
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # First, unset all default templates for this user
        cursor.execute("""
            UPDATE invoice_templates 
            SET is_default = FALSE 
            WHERE user_id = %s
        """, (session['user_id'],))
        print(f"DEBUG: Unset {cursor.rowcount} default templates")
        
        # Then set the selected template as default
        cursor.execute("""
            UPDATE invoice_templates 
            SET is_default = TRUE 
            WHERE id = %s AND user_id = %s
        """, (template_id, session['user_id']))
        print(f"DEBUG: Set template {template_id} as default, affected rows: {cursor.rowcount}")
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Template not found'}), 404
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'message': 'Default template updated successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/templates/<int:template_id>', methods=['DELETE'])
@login_required
def delete_template(template_id):
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Check if template exists and belongs to user
        cursor.execute("""
            SELECT is_default FROM invoice_templates 
            WHERE id = %s AND user_id = %s
        """, (template_id, session['user_id']))
        template = cursor.fetchone()
        
        if not template:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Template not found'}), 404
        
        # Delete the template
        cursor.execute("""
            DELETE FROM invoice_templates 
            WHERE id = %s AND user_id = %s
        """, (template_id, session['user_id']))
        
        # If the deleted template was default, set another template as default
        if template[0]:  # was default
            cursor.execute("""
                SELECT id FROM invoice_templates 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT 1
            """, (session['user_id'],))
            new_default = cursor.fetchone()
            
            if new_default:
                cursor.execute("""
                    UPDATE invoice_templates 
                    SET is_default = TRUE 
                    WHERE id = %s
                """, (new_default[0],))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'message': 'Template deleted successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/test-input')
def test_input():
    """Test page for input functionality"""
    try:
        with open('test_input.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "Test file not found", 404

# Admin Routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')
        
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM admin_users WHERE username = %s AND is_active = TRUE", (username,))
            admin = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if admin and check_password_hash(admin['password_hash'], password):
                session['admin_id'] = admin['id']
                session['admin_username'] = admin['username']
                session['admin_role'] = admin['role']
                
                if remember:
                    session.permanent = True
                
                update_admin_last_login(admin['id'])
                log_audit_event(admin_id=admin['id'], action='ADMIN_LOGIN', table_name='admin_users')
                
                flash('Successfully logged in as admin!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid username or password.', 'error')
        else:
            flash('Database connection error.', 'error')
    
    return redirect(url_for('login'))

@app.route('/admin/logout')
def admin_logout():
    if 'admin_id' in session:
        log_audit_event(admin_id=session['admin_id'], action='ADMIN_LOGOUT', table_name='admin_users')
        session.pop('admin_id', None)
        session.pop('admin_username', None)
        session.pop('admin_role', None)
    
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    admin_user = get_current_admin()
    
    # Get statistics
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Total users
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()['count']
        
        # Active users
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_active = TRUE")
        active_users = cursor.fetchone()['count']
        
        # Active sessions
        cursor.execute("SELECT COUNT(*) as count FROM user_sessions WHERE is_active = TRUE")
        active_sessions = cursor.fetchone()['count']
        
        # Today's logins (India time)
        india_today = get_india_time().date()
        cursor.execute("SELECT COUNT(*) as count FROM audit_logs WHERE action = 'LOGIN' AND DATE(created_at) = %s", (india_today,))
        today_logins = cursor.fetchone()['count']
        
        cursor.close()
        connection.close()
        
        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'active_sessions': active_sessions,
            'today_logins': today_logins
        }
        
        return render_template('admin_dashboard.html', admin_user=admin_user, stats=stats)
    
    flash('Database connection error.', 'error')
    return redirect(url_for('admin_login'))

# Admin API Routes
@app.route('/admin/api/users')
@admin_required
def admin_api_users():
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, username, email, first_name, last_name, is_active, is_admin, 
                   last_login, created_at, updated_at
            FROM users 
            ORDER BY created_at DESC
        """)
        users = cursor.fetchall()
        
        # Convert datetime objects to India timezone strings
        for user in users:
            if user['last_login']:
                user['last_login'] = format_india_time(user['last_login'])
            if user['created_at']:
                user['created_at'] = format_india_time(user['created_at'])
            if user['updated_at']:
                user['updated_at'] = format_india_time(user['updated_at'])
        
        cursor.close()
        connection.close()
        
        print(f"Returning {len(users)} users from API")
        for user in users:
            print(f"User {user['id']}: {user['username']} - Active: {user['is_active']}, Admin: {user['is_admin']}")
        
        cursor.close()
        connection.close()
        
        return jsonify(users)
    
    return jsonify({'error': 'Database connection failed'}), 500

@app.route('/admin/api/users', methods=['POST'])
@admin_required
def admin_create_user():
    try:
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        is_admin = request.form.get('is_admin') == 'on'
        
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            
            # Check if username or email already exists
            cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
            existing_user = cursor.fetchone()
            
            if existing_user:
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': 'Username or email already exists'})
            
            # Create new user
            password_hash = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, first_name, last_name, is_admin)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (username, email, password_hash, first_name, last_name, is_admin))
            
            user_id = cursor.lastrowid
            
            # Create default company settings for the user
            cursor.execute("""
                INSERT INTO company_settings (user_id, company_name, company_address, company_phone, company_email, tax_number)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, 'Your Company Name', 'Your Company Address', '+1-234-567-8900', 'info@company.com', 'TAX123456789'))
            
            connection.commit()
            cursor.close()
            connection.close()
            
            log_audit_event(admin_id=session['admin_id'], action='CREATE_USER', table_name='users', record_id=user_id)
            
            return jsonify({'success': True, 'message': 'User created successfully'})
        
        return jsonify({'success': False, 'message': 'Database connection failed'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/api/users/<int:user_id>')
@admin_required
def admin_get_user(user_id):
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # Get user details
        cursor.execute("""
            SELECT id, username, email, first_name, last_name, is_active, is_admin, 
                   last_login, created_at, updated_at
            FROM users 
            WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()
        
        if user:
            # Convert datetime objects to India timezone strings
            if user['last_login']:
                user['last_login'] = format_india_time(user['last_login'])
            if user['created_at']:
                user['created_at'] = format_india_time(user['created_at'])
            if user['updated_at']:
                user['updated_at'] = format_india_time(user['updated_at'])
            
            # Get user statistics
            # Get expenses count
            cursor.execute("SELECT COUNT(*) as count FROM expenses WHERE user_id = %s", (user_id,))
            expenses_count = cursor.fetchone()['count']
            
            # Get transactions count
            cursor.execute("SELECT COUNT(*) as count FROM transactions WHERE user_id = %s", (user_id,))
            transactions_count = cursor.fetchone()['count']
            
            # Get invoices count
            cursor.execute("SELECT COUNT(*) as count FROM invoices WHERE user_id = %s", (user_id,))
            invoices_count = cursor.fetchone()['count']
            
            # Set files count to 0 since file_uploads table may not exist
            files_count = 0
            
            # Get recent expenses (last 5)
            cursor.execute("""
                SELECT id, expense_type, category, amount, title, expense_date 
                FROM expenses 
                WHERE user_id = %s 
                ORDER BY expense_date DESC 
                LIMIT 5
            """, (user_id,))
            recent_expenses = cursor.fetchall()
            
            # Get recent transactions (last 5)
            cursor.execute("""
                SELECT id, transaction_type, amount, title, transaction_date 
                FROM transactions 
                WHERE user_id = %s 
                ORDER BY transaction_date DESC 
                LIMIT 5
            """, (user_id,))
            recent_transactions = cursor.fetchall()
            
            # Get recent invoices (last 5)
            cursor.execute("""
                SELECT id, invoice_number, client_name, total_amount, status, invoice_date 
                FROM invoices 
                WHERE user_id = %s 
                ORDER BY invoice_date DESC 
                LIMIT 5
            """, (user_id,))
            recent_invoices = cursor.fetchall()
            
            user['stats'] = {
                'expenses_count': expenses_count,
                'transactions_count': transactions_count,
                'invoices_count': invoices_count,
                'files_count': files_count
            }
            
            # Add recent data
            user['recent_data'] = {
                'expenses': recent_expenses,
                'transactions': recent_transactions,
                'invoices': recent_invoices
            }
        
        cursor.close()
        connection.close()
        return jsonify(user)
    
    return jsonify({'error': 'Database connection failed'}), 500

@app.route('/admin/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            
            # Check if user exists
            cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': 'User not found'})
            
            # Delete user (cascade will handle related data)
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            connection.commit()
            cursor.close()
            connection.close()
            
            log_audit_event(admin_id=session['admin_id'], action='DELETE_USER', table_name='users', record_id=user_id)
            
            return jsonify({'success': True, 'message': 'User deleted successfully'})
        
        return jsonify({'success': False, 'message': 'Database connection failed'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/api/users/<int:user_id>/export-data')
@admin_required
def admin_export_user_data(user_id):
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            
            # Get user details
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                cursor.close()
                connection.close()
                return jsonify({'error': 'User not found'}), 404
            
            # Get user's expenses with detailed information
            cursor.execute("""
                SELECT 
                    id, expense_type, category, amount, title, description, 
                    expense_date, bill_file, created_at, updated_at
                FROM expenses 
                WHERE user_id = %s 
                ORDER BY expense_date DESC
            """, (user_id,))
            expenses = cursor.fetchall()
            
            # Get user's transactions with detailed information
            cursor.execute("""
                SELECT 
                    id, transaction_type, amount, title, description, purpose, utr_number,
                    transaction_date, category, receipt_file, created_at, updated_at
                FROM transactions 
                WHERE user_id = %s 
                ORDER BY transaction_date DESC
            """, (user_id,))
            transactions = cursor.fetchall()
            
            # Get user's invoices with detailed information
            cursor.execute("""
                SELECT 
                    id, invoice_number, client_name, client_email, client_address, client_phone,
                    invoice_date, due_date, subtotal, tax_rate, tax_amount, 
                    total_amount, status, notes, created_at, updated_at
                FROM invoices 
                WHERE user_id = %s 
                ORDER BY invoice_date DESC
            """, (user_id,))
            invoices = cursor.fetchall()
            
            # Get invoice items if they exist
            invoice_items = []
            if invoices:
                invoice_ids = [invoice['id'] for invoice in invoices]
                placeholders = ','.join(['%s'] * len(invoice_ids))
                cursor.execute(f"""
                    SELECT 
                        id, invoice_id, description, quantity, 
                        unit_price, total_price
                    FROM invoice_items 
                    WHERE invoice_id IN ({placeholders})
                    ORDER BY invoice_id, id
                """, invoice_ids)
                invoice_items = cursor.fetchall()
            
            cursor.close()
            connection.close()
            
            # Create Excel file
            timestamp = get_india_time().strftime('%Y%m%d_%H%M%S')
            filename = f'user_data_{user["username"]}_{timestamp}.xlsx'
            filepath = os.path.join(EXPORT_FOLDER, filename)
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # User details sheet
                user_details = {
                    'User ID': user['id'],
                    'Username': user['username'],
                    'Email': user['email'],
                    'First Name': user['first_name'],
                    'Last Name': user['last_name'],
                    'Is Active': 'Yes' if user['is_active'] else 'No',
                    'Is Admin': 'Yes' if user['is_admin'] else 'No',
                    'Created At': format_india_time(user['created_at']),
                    'Last Login': format_india_time(user['last_login']) if user['last_login'] else 'Never',
                    'Updated At': format_india_time(user['updated_at'])
                }
                user_df = pd.DataFrame([user_details])
                user_df.to_excel(writer, sheet_name='User_Details', index=False)
                
                # Expenses sheet
                if expenses:
                    # Format dates for better readability
                    for expense in expenses:
                        if expense['expense_date']:
                            expense['expense_date'] = format_india_time(expense['expense_date'])
                        if expense['created_at']:
                            expense['created_at'] = format_india_time(expense['created_at'])
                        if expense['updated_at']:
                            expense['updated_at'] = format_india_time(expense['updated_at'])
                    
                    expenses_df = pd.DataFrame(expenses)
                    expenses_df.to_excel(writer, sheet_name='Expenses', index=False)
                else:
                    pd.DataFrame(columns=['No expenses found for this user']).to_excel(writer, sheet_name='Expenses', index=False)
                
                # Transactions sheet
                if transactions:
                    # Format dates for better readability
                    for transaction in transactions:
                        if transaction['transaction_date']:
                            transaction['transaction_date'] = format_india_time(transaction['transaction_date'])
                        if transaction['created_at']:
                            transaction['created_at'] = format_india_time(transaction['created_at'])
                        if transaction['updated_at']:
                            transaction['updated_at'] = format_india_time(transaction['updated_at'])
                    
                    transactions_df = pd.DataFrame(transactions)
                    transactions_df.to_excel(writer, sheet_name='Transactions', index=False)
                else:
                    pd.DataFrame(columns=['No transactions found for this user']).to_excel(writer, sheet_name='Transactions', index=False)
                
                # Invoices sheet
                if invoices:
                    # Format dates for better readability
                    for invoice in invoices:
                        if invoice['invoice_date']:
                            invoice['invoice_date'] = format_india_time(invoice['invoice_date'])
                        if invoice['due_date']:
                            invoice['due_date'] = format_india_time(invoice['due_date'])
                        if invoice['created_at']:
                            invoice['created_at'] = format_india_time(invoice['created_at'])
                        if invoice['updated_at']:
                            invoice['updated_at'] = format_india_time(invoice['updated_at'])
                    
                    invoices_df = pd.DataFrame(invoices)
                    invoices_df.to_excel(writer, sheet_name='Invoices', index=False)
                else:
                    pd.DataFrame(columns=['No invoices found for this user']).to_excel(writer, sheet_name='Invoices', index=False)
                
                # Invoice Items sheet (if any invoices exist)
                if invoice_items:
                    invoice_items_df = pd.DataFrame(invoice_items)
                    invoice_items_df.to_excel(writer, sheet_name='Invoice_Items', index=False)
                elif invoices:
                    pd.DataFrame(columns=['No invoice items found']).to_excel(writer, sheet_name='Invoice_Items', index=False)
            
            log_audit_event(admin_id=session['admin_id'], action='EXPORT_USER_DATA', table_name='users', record_id=user_id)
            
            return send_file(filepath, as_attachment=True, download_name=filename)
            
            # Get user's invoices with detailed information
            cursor.execute("""
                SELECT 
                    id, invoice_number, client_name, client_email, client_address, client_phone,
                    invoice_date, due_date, subtotal, tax_rate, tax_amount, 
                    total_amount, status, notes, created_at, updated_at
                FROM invoices 
                WHERE user_id = %s 
                ORDER BY invoice_date DESC
            """, (user_id,))
            invoices = cursor.fetchall()
            
            # Get invoice items if they exist
            invoice_items = []
            if invoices:
                invoice_ids = [invoice['id'] for invoice in invoices]
                placeholders = ','.join(['%s'] * len(invoice_ids))
                cursor.execute(f"""
                    SELECT 
                        id, invoice_id, description, quantity, 
                        unit_price, total_price
                    FROM invoice_items 
                    WHERE invoice_id IN ({placeholders})
                    ORDER BY invoice_id, id
                """, invoice_ids)
                invoice_items = cursor.fetchall()
            
            cursor.close()
            connection.close()
            
            # Create Excel file
            timestamp = get_india_time().strftime('%Y%m%d_%H%M%S')
            filename = f'user_data_{user["username"]}_{timestamp}.xlsx'
            filepath = os.path.join(EXPORT_FOLDER, filename)
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # User details sheet
                user_details = {
                    'User ID': user['id'],
                    'Username': user['username'],
                    'Email': user['email'],
                    'First Name': user['first_name'],
                    'Last Name': user['last_name'],
                    'Is Active': 'Yes' if user['is_active'] else 'No',
                    'Is Admin': 'Yes' if user['is_admin'] else 'No',
                    'Created At': format_india_time(user['created_at']),
                    'Last Login': format_india_time(user['last_login']) if user['last_login'] else 'Never',
                    'Updated At': format_india_time(user['updated_at'])
                }
                user_df = pd.DataFrame([user_details])
                user_df.to_excel(writer, sheet_name='User_Details', index=False)
                
                # Expenses sheet
                if expenses:
                    # Format dates for better readability
                    for expense in expenses:
                        if expense['expense_date']:
                            expense['expense_date'] = format_india_time(expense['expense_date'])
                        if expense['created_at']:
                            expense['created_at'] = format_india_time(expense['created_at'])
                        if expense['updated_at']:
                            expense['updated_at'] = format_india_time(expense['updated_at'])
                    
                    expenses_df = pd.DataFrame(expenses)
                    expenses_df.to_excel(writer, sheet_name='Expenses', index=False)
                else:
                    pd.DataFrame(columns=['No expenses found for this user']).to_excel(writer, sheet_name='Expenses', index=False)
                
                # Transactions sheet
                if transactions:
                    # Format dates for better readability
                    for transaction in transactions:
                        if transaction['transaction_date']:
                            transaction['transaction_date'] = format_india_time(transaction['transaction_date'])
                        if transaction['created_at']:
                            transaction['created_at'] = format_india_time(transaction['created_at'])
                        if transaction['updated_at']:
                            transaction['updated_at'] = format_india_time(transaction['updated_at'])
                    
                    transactions_df = pd.DataFrame(transactions)
                    transactions_df.to_excel(writer, sheet_name='Transactions', index=False)
                else:
                    pd.DataFrame(columns=['No transactions found for this user']).to_excel(writer, sheet_name='Transactions', index=False)
                
                # Invoices sheet
                if invoices:
                    # Format dates for better readability
                    for invoice in invoices:
                        if invoice['invoice_date']:
                            invoice['invoice_date'] = format_india_time(invoice['invoice_date'])
                        if invoice['due_date']:
                            invoice['due_date'] = format_india_time(invoice['due_date'])
                        if invoice['created_at']:
                            invoice['created_at'] = format_india_time(invoice['created_at'])
                        if invoice['updated_at']:
                            invoice['updated_at'] = format_india_time(invoice['updated_at'])
                    
                    invoices_df = pd.DataFrame(invoices)
                    invoices_df.to_excel(writer, sheet_name='Invoices', index=False)
                else:
                    pd.DataFrame(columns=['No invoices found for this user']).to_excel(writer, sheet_name='Invoices', index=False)
                
                # Invoice Items sheet (if any invoices exist)
                if invoice_items:
                    invoice_items_df = pd.DataFrame(invoice_items)
                    invoice_items_df.to_excel(writer, sheet_name='Invoice_Items', index=False)
                elif invoices:
                    pd.DataFrame(columns=['No invoice items found']).to_excel(writer, sheet_name='Invoice_Items', index=False)
            
            log_audit_event(admin_id=session['admin_id'], action='EXPORT_USER_DATA', table_name='users', record_id=user_id)
            
            return send_file(filepath, as_attachment=True, download_name=filename)
        
        return jsonify({'error': 'Database connection failed'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def admin_update_user(user_id):
    try:
        data = request.get_json()
        
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            
            # Check if user exists
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': 'User not found'})
            
            # Update user fields
            update_fields = []
            update_values = []
            
            if 'username' in data and data['username']:
                update_fields.append("username = %s")
                update_values.append(data['username'])
            
            if 'email' in data and data['email']:
                update_fields.append("email = %s")
                update_values.append(data['email'])
            
            if 'first_name' in data and data['first_name']:
                update_fields.append("first_name = %s")
                update_values.append(data['first_name'])
            
            if 'last_name' in data and data['last_name']:
                update_fields.append("last_name = %s")
                update_values.append(data['last_name'])
            
            if 'is_active' in data:
                update_fields.append("is_active = %s")
                # Convert to integer for MySQL BOOLEAN
                is_active_value = 1 if data['is_active'] else 0
                update_values.append(is_active_value)
                print(f"Setting is_active to: {is_active_value} (original: {data['is_active']})")
            
            if 'is_admin' in data:
                update_fields.append("is_admin = %s")
                # Convert to integer for MySQL BOOLEAN
                is_admin_value = 1 if data['is_admin'] else 0
                update_values.append(is_admin_value)
                print(f"Setting is_admin to: {is_admin_value} (original: {data['is_admin']})")
            
            if update_fields:
                update_values.append(user_id)
                query = f"UPDATE users SET {', '.join(update_fields)}, updated_at = %s WHERE id = %s"
                update_values.append(get_india_time())
                
                print(f"Executing query: {query}")
                print(f"Update values: {update_values}")
                
                cursor.execute(query, update_values)
                connection.commit()
                
                # Verify the update was successful
                cursor.execute("SELECT is_active, is_admin FROM users WHERE id = %s", (user_id,))
                result = cursor.fetchone()
                print(f"After update verification - User {user_id}: Active={result[0]}, Admin={result[1]}")
                
                # Convert datetime objects to strings for JSON serialization
                old_values = {}
                for key, value in user.items():
                    if isinstance(value, datetime):
                        old_values[key] = format_india_time(value)
                    else:
                        old_values[key] = value
                
                log_audit_event(
                    admin_id=session['admin_id'], 
                    action='UPDATE_USER', 
                    table_name='users', 
                    record_id=user_id,
                    old_values=old_values,
                    new_values=data
                )
            
            cursor.close()
            connection.close()
            
            return jsonify({'success': True, 'message': 'User updated successfully'})
        
        return jsonify({'success': False, 'message': 'Database connection failed'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/api/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def admin_reset_user_password(user_id):
    try:
        import secrets
        import string
        
        # Generate random password
        alphabet = string.ascii_letters + string.digits
        new_password = ''.join(secrets.choice(alphabet) for i in range(12))
        password_hash = generate_password_hash(new_password)
        
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            
            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))
            connection.commit()
            cursor.close()
            connection.close()
            
            log_audit_event(admin_id=session['admin_id'], action='RESET_PASSWORD', table_name='users', record_id=user_id)
            
            return jsonify({'success': True, 'new_password': new_password})
        
        return jsonify({'success': False, 'message': 'Database connection failed'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/api/audit-logs')
@admin_required
def admin_audit_logs():
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT al.id, al.action, al.table_name, al.record_id, al.ip_address, al.created_at,
                   u.username as user_name, au.username as admin_name
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            LEFT JOIN admin_users au ON al.admin_id = au.id
            ORDER BY al.created_at DESC
            LIMIT 1000
        """)
        logs = cursor.fetchall()
        
        # Convert datetime objects to India timezone strings
        for log in logs:
            if log['created_at']:
                log['created_at'] = format_india_time(log['created_at'])
        
        cursor.close()
        connection.close()
        return jsonify(logs)
    
    return jsonify({'error': 'Database connection failed'}), 500

@app.route('/admin/api/active-sessions')
@admin_required
def admin_active_sessions():
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT us.id, us.session_id, us.ip_address, us.user_agent, 
                   us.login_time, us.last_activity, u.username
            FROM user_sessions us
            JOIN users u ON us.user_id = u.id
            WHERE us.is_active = TRUE
            ORDER BY us.last_activity DESC
        """)
        sessions = cursor.fetchall()
        
        # Convert datetime objects to India timezone strings
        for session in sessions:
            if session['login_time']:
                session['login_time'] = format_india_time(session['login_time'])
            if session['last_activity']:
                session['last_activity'] = format_india_time(session['last_activity'])
        
        cursor.close()
        connection.close()
        return jsonify(sessions)
    
    return jsonify({'error': 'Database connection failed'}), 500

@app.route('/admin/api/sessions/<int:session_id>/terminate', methods=['POST'])
@admin_required
def admin_terminate_session(session_id):
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            
            # Check if session exists
            cursor.execute("SELECT user_id FROM user_sessions WHERE id = %s", (session_id,))
            session_data = cursor.fetchone()
            
            if not session_data:
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': 'Session not found'})
            
            cursor.execute("UPDATE user_sessions SET is_active = FALSE WHERE id = %s", (session_id,))
            connection.commit()
            cursor.close()
            connection.close()
            
            log_audit_event(admin_id=session['admin_id'], action='TERMINATE_SESSION', table_name='user_sessions', record_id=session_id)
            
            return jsonify({'success': True, 'message': 'Session terminated successfully'})
        
        return jsonify({'success': False, 'message': 'Database connection failed'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/api/sessions/terminate-all', methods=['POST'])
@admin_required
def admin_terminate_all_sessions():
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("UPDATE user_sessions SET is_active = FALSE WHERE is_active = TRUE")
            connection.commit()
            cursor.close()
            connection.close()
            
            log_audit_event(admin_id=session['admin_id'], action='TERMINATE_ALL_SESSIONS', table_name='user_sessions')
            
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'message': 'Database connection failed'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/api/recent-activity')
@admin_required
def admin_recent_activity():
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT al.action, al.table_name, al.ip_address, al.created_at,
                   u.username as user_name, au.username as admin_name
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            LEFT JOIN admin_users au ON al.admin_id = au.id
            ORDER BY al.created_at DESC
            LIMIT 20
        """)
        activities = cursor.fetchall()
        
        # Convert datetime objects to India timezone strings
        for activity in activities:
            if activity['created_at']:
                activity['created_at'] = format_india_time(activity['created_at'])
        
        cursor.close()
        connection.close()
        return jsonify(activities)
    
    return jsonify({'error': 'Database connection failed'}), 500

@app.route('/admin/api/chart-data')
@admin_required
def admin_chart_data():
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        
        # User statistics
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_active = TRUE")
        active_users = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_active = FALSE")
        inactive_users = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_admin = TRUE")
        admin_users = cursor.fetchone()['count']
        
        # Activity trends (last 7 days) - India time
        india_today = get_india_time().date()
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM audit_logs 
            WHERE action = 'LOGIN' AND created_at >= DATE_SUB(%s, INTERVAL 7 DAY)
            GROUP BY DATE(created_at)
            ORDER BY date
        """, (india_today,))
        activity_data = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        # Prepare chart data
        activity_labels = []
        activity_counts = []
        for item in activity_data:
            activity_labels.append(item['date'].strftime('%m/%d'))
            activity_counts.append(item['count'])
        
        return jsonify({
            'active_users': active_users,
            'inactive_users': inactive_users,
            'admin_users': admin_users,
            'activity_labels': activity_labels,
            'activity_data': activity_counts
        })
    
    return jsonify({'error': 'Database connection failed'}), 500

@app.route('/admin/api/export-all-data')
@admin_required
def admin_export_all_data():
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            
            # Get all users data
            cursor.execute("""
                SELECT u.*, 
                       COUNT(DISTINCT e.id) as expenses_count,
                       COUNT(DISTINCT t.id) as transactions_count,
                       COUNT(DISTINCT i.id) as invoices_count
                FROM users u
                LEFT JOIN expenses e ON u.id = e.user_id
                LEFT JOIN transactions t ON u.id = t.user_id
                LEFT JOIN invoices i ON u.id = i.user_id
                GROUP BY u.id
                ORDER BY u.created_at DESC
            """)
            users_data = cursor.fetchall()
            
            # Get audit logs data
            cursor.execute("""
                SELECT al.*, u.username as user_name, au.username as admin_name
                FROM audit_logs al
                LEFT JOIN users u ON al.user_id = u.id
                LEFT JOIN admin_users au ON al.admin_id = au.id
                ORDER BY al.created_at DESC
            """)
            audit_data = cursor.fetchall()
            
            cursor.close()
            connection.close()
            
            # Create Excel file
            timestamp = get_india_time().strftime('%Y%m%d_%H%M%S')
            filename = f'admin_export_all_data_{timestamp}.xlsx'
            filepath = os.path.join(EXPORT_FOLDER, filename)
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Users sheet
                users_df = pd.DataFrame(users_data)
                users_df.to_excel(writer, sheet_name='Users', index=False)
                
                # Audit logs sheet
                audit_df = pd.DataFrame(audit_data)
                audit_df.to_excel(writer, sheet_name='Audit_Logs', index=False)
            
            log_audit_event(admin_id=session['admin_id'], action='EXPORT_ALL_DATA', table_name='system')
            
            return send_file(filepath, as_attachment=True, download_name=filename)
        
        return jsonify({'error': 'Database connection failed'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/export-audit-logs')
@admin_required
def admin_export_audit_logs():
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT al.*, u.username as user_name, au.username as admin_name
                FROM audit_logs al
                LEFT JOIN users u ON al.user_id = u.id
                LEFT JOIN admin_users au ON al.admin_id = au.id
                ORDER BY al.created_at DESC
            """)
            audit_data = cursor.fetchall()
            cursor.close()
            connection.close()
            
            # Create CSV file
            timestamp = get_india_time().strftime('%Y%m%d_%H%M%S')
            filename = f'audit_logs_{timestamp}.csv'
            filepath = os.path.join(EXPORT_FOLDER, filename)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                if audit_data:
                    fieldnames = audit_data[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(audit_data)
            
            log_audit_event(admin_id=session['admin_id'], action='EXPORT_AUDIT_LOGS', table_name='audit_logs')
            
            return send_file(filepath, as_attachment=True, download_name=filename)
        
        return jsonify({'error': 'Database connection failed'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/generate-report')
@admin_required
def admin_generate_report():
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            
            # Generate comprehensive report
            report_data = {}
            
            # User statistics
            cursor.execute("SELECT COUNT(*) as total FROM users")
            report_data['total_users'] = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as active FROM users WHERE is_active = TRUE")
            report_data['active_users'] = cursor.fetchone()['active']
            
            cursor.execute("SELECT COUNT(*) as admin FROM users WHERE is_admin = TRUE")
            report_data['admin_users'] = cursor.fetchone()['admin']
            
            # Activity statistics
            cursor.execute("SELECT COUNT(*) as total FROM audit_logs")
            report_data['total_audit_logs'] = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as today FROM audit_logs WHERE DATE(created_at) = CURDATE()")
            report_data['today_audit_logs'] = cursor.fetchone()['today']
            
            # Data statistics
            cursor.execute("SELECT COUNT(*) as total FROM expenses")
            report_data['total_expenses'] = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM transactions")
            report_data['total_transactions'] = cursor.fetchone()['total']
            
            cursor.execute("SELECT COUNT(*) as total FROM invoices")
            report_data['total_invoices'] = cursor.fetchone()['total']
            
            cursor.close()
            connection.close()
            
            # Create PDF report
            timestamp = get_india_time().strftime('%Y%m%d_%H%M%S')
            filename = f'admin_report_{timestamp}.pdf'
            filepath = os.path.join(EXPORT_FOLDER, filename)
            
            doc = SimpleDocTemplate(filepath, pagesize=letter)
            elements = []
            
            # Title
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                alignment=1
            )
            elements.append(Paragraph("Admin System Report", title_style))
            elements.append(Spacer(1, 20))
            
            # Report data
            data = [
                ['Metric', 'Value'],
                ['Total Users', str(report_data['total_users'])],
                ['Active Users', str(report_data['active_users'])],
                ['Admin Users', str(report_data['admin_users'])],
                ['Total Audit Logs', str(report_data['total_audit_logs'])],
                ['Today\'s Audit Logs', str(report_data['today_audit_logs'])],
                ['Total Expenses', str(report_data['total_expenses'])],
                ['Total Transactions', str(report_data['total_transactions'])],
                ['Total Invoices', str(report_data['total_invoices'])]
            ]
            
            table = Table(data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 14),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            elements.append(table)
            doc.build(elements)
            
            log_audit_event(admin_id=session['admin_id'], action='GENERATE_REPORT', table_name='system')
            
            return send_file(filepath, as_attachment=True, download_name=filename)
        
        return jsonify({'error': 'Database connection failed'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/system-report')
@admin_required
def admin_system_report():
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            
            # Get system statistics
            stats = {}
            
            # User statistics
            cursor.execute("SELECT COUNT(*) as count FROM users")
            stats['total_users'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_active = TRUE")
            stats['active_users'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_admin = TRUE")
            stats['admin_users'] = cursor.fetchone()['count']
            
            # Data statistics
            cursor.execute("SELECT COUNT(*) as count FROM expenses")
            stats['total_expenses'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM transactions")
            stats['total_transactions'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM invoices")
            stats['total_invoices'] = cursor.fetchone()['count']
            
            # Set files count to 0 since file_uploads table may not exist
            stats['total_files'] = 0
            
            # Recent activity
            cursor.execute("""
                SELECT al.action, al.table_name, al.created_at, u.username as user_name
                FROM audit_logs al
                LEFT JOIN users u ON al.user_id = u.id
                ORDER BY al.created_at DESC
                LIMIT 50
            """)
            recent_activity = cursor.fetchall()
            
            cursor.close()
            connection.close()
            
            return render_template('system_report.html', stats=stats, recent_activity=recent_activity)
        
        return jsonify({'error': 'Database connection failed'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/clear-old-logs', methods=['POST'])
@admin_required
def admin_clear_old_logs():
    try:
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            
            # Delete logs older than 30 days
            cursor.execute("DELETE FROM audit_logs WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY)")
            deleted_count = cursor.rowcount
            
            connection.commit()
            cursor.close()
            connection.close()
            
            log_audit_event(admin_id=session['admin_id'], action='CLEAR_OLD_LOGS', table_name='audit_logs')
            
            return jsonify({'success': True, 'message': f'Deleted {deleted_count} old logs'})
        
        return jsonify({'success': False, 'message': 'Database connection failed'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    # Ensure upload and export directories exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(EXPORT_FOLDER, exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # Get port from environment variable (for production) or use 5000 for development
# Cash Balance Management API Endpoints
@app.route('/api/cash-balance', methods=['GET'])
@login_required
def get_cash_balance():
    """Get the current cash balance for the user"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Get cash balance from users table
        cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (session['user_id'],))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if result:
            return jsonify({'cash_balance': result[0] or 0})
        else:
            return jsonify({'cash_balance': 0})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/cash-balance', methods=['POST'])
@login_required
def update_cash_balance():
    """Update the cash balance for the user"""
    try:
        data = request.get_json()
        cash_amount = data.get('cash_amount')
        notes = data.get('notes', '')
        
        if cash_amount is None:
            return jsonify({'error': 'Cash amount is required'}), 400
        
        if not isinstance(cash_amount, (int, float)) or cash_amount < 0:
            return jsonify({'error': 'Cash amount must be a positive number'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Update cash balance in users table
        cursor.execute("""
            UPDATE users 
            SET cash_balance = %s 
            WHERE id = %s
        """, (cash_amount, session['user_id']))
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({'error': 'User not found'}), 404
        
        # Log the cash balance update
        cursor.execute("""
            INSERT INTO cash_balance_history (user_id, amount, notes, created_at)
            VALUES (%s, %s, %s, NOW())
        """, (session['user_id'], cash_amount, notes))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Cash balance updated successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def update_cash_balance_transaction(amount, transaction_type, user_id):
    """Update cash balance when a cash transaction is made"""
    try:
        connection = get_db_connection()
        if not connection:
            print("Database connection failed for cash balance update")
            return False
        
        cursor = connection.cursor()
        
        if transaction_type == 'credit':
            cursor.execute("""
                UPDATE users 
                SET cash_balance = cash_balance + %s 
                WHERE id = %s
            """, (amount, user_id))
            print(f"Added ₹{amount} to cash balance for user {user_id}")
        else:  # debit
            cursor.execute("""
                UPDATE users 
                SET cash_balance = cash_balance - %s 
                WHERE id = %s
            """, (amount, user_id))
            print(f"Deducted ₹{amount} from cash balance for user {user_id}")
        
        if cursor.rowcount == 0:
            print(f"Warning: Could not update cash balance for user {user_id}")
            return False
        
        connection.commit()
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        print(f"Error updating cash balance: {e}")
        return False


# Payment Receipt Generation
@app.route('/api/receipt/<transaction_type>/<int:transaction_id>')
@login_required
def generate_payment_receipt(transaction_type, transaction_id):
    """Generate payment receipt for any transaction type"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Get transaction details based on type
        if transaction_type == 'expense':
            cursor.execute("""
                SELECT e.*, ba.bank_name, ba.account_number
                FROM expenses e
                LEFT JOIN bank_accounts ba ON e.bank_account_id = ba.id
                WHERE e.id = %s AND e.user_id = %s
            """, (transaction_id, session['user_id']))
            transaction = cursor.fetchone()
            
            if not transaction:
                return jsonify({'error': 'Expense not found'}), 404
            
            # Prepare receipt data
            receipt_data = {
                'receipt_number': f"EXP-{transaction_id:06d}",
                'unique_id': transaction.get('unique_id', 'N/A'),
                'transaction_date': transaction.get('expense_date', 'N/A'),
                'transaction_type': 'Expense',
                'transaction_type_display': 'EXPENSE',
                'transaction_type_class': 'debit',
                'payment_method': transaction.get('payment_method', 'N/A'),
                'bank_account': f"{transaction.get('bank_name', 'Cash')} - {transaction.get('account_number', '')}" if transaction.get('bank_name') else 'Cash',
                'category': transaction.get('category', 'N/A'),
                'status': 'Completed',
                'title': transaction.get('purpose', 'N/A'),
                'purpose': transaction.get('purpose', 'N/A'),
                'amount': f"{transaction.get('amount', 0):,.2f}",
                'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        elif transaction_type == 'invoice':
            cursor.execute("""
                SELECT i.*, ba.bank_name, ba.account_number
                FROM invoices i
                LEFT JOIN bank_accounts ba ON i.bank_account_id = ba.id
                WHERE i.id = %s AND i.user_id = %s
            """, (transaction_id, session['user_id']))
            transaction = cursor.fetchone()
            
            if not transaction:
                return jsonify({'error': 'Invoice not found'}), 404
            
            # Prepare receipt data
            receipt_data = {
                'receipt_number': f"INV-{transaction_id:06d}",
                'unique_id': transaction.get('unique_id', 'N/A'),
                'transaction_date': transaction.get('invoice_date', 'N/A'),
                'transaction_type': 'Invoice',
                'transaction_type_display': 'INVOICE',
                'transaction_type_class': 'credit' if transaction.get('invoice_type') == 'in' else 'debit',
                'payment_method': 'Invoice Payment',
                'bank_account': f"{transaction.get('bank_name', 'Cash')} - {transaction.get('account_number', '')}" if transaction.get('bank_name') else 'Cash',
                'category': 'Invoice',
                'status': transaction.get('status', 'N/A'),
                'title': f"Invoice {transaction.get('invoice_number', 'N/A')}",
                'purpose': f"{transaction.get('invoice_type', 'out').upper()} Invoice",
                'client_name': transaction.get('client_name', 'N/A'),
                'invoice_number': transaction.get('invoice_number', 'N/A'),
                'amount': f"{transaction.get('total_amount', 0):,.2f}",
                'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        elif transaction_type == 'transaction':
            cursor.execute("""
                SELECT t.*, ba.bank_name, ba.account_number
                FROM transactions t
                LEFT JOIN bank_accounts ba ON t.bank_account_id = ba.id
                WHERE t.id = %s AND t.user_id = %s
            """, (transaction_id, session['user_id']))
            transaction = cursor.fetchone()
            
            if not transaction:
                return jsonify({'error': 'Transaction not found'}), 404
            
            # Prepare receipt data
            receipt_data = {
                'receipt_number': f"TXN-{transaction_id:06d}",
                'unique_id': transaction.get('unique_id', 'N/A'),
                'transaction_date': transaction.get('transaction_date', 'N/A'),
                'transaction_type': 'Transaction',
                'transaction_type_display': transaction.get('transaction_type', 'TRANSACTION').upper(),
                'transaction_type_class': transaction.get('transaction_type', 'credit'),
                'payment_method': transaction.get('payment_method', 'N/A'),
                'bank_account': f"{transaction.get('bank_name', 'Cash')} - {transaction.get('account_number', '')}" if transaction.get('bank_name') else 'Cash',
                'category': transaction.get('category', 'N/A'),
                'status': 'Completed',
                'title': transaction.get('title', 'N/A'),
                'purpose': transaction.get('purpose', 'N/A'),
                'amount': f"{transaction.get('amount', 0):,.2f}",
                'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        else:
            return jsonify({'error': 'Invalid transaction type'}), 400
        
        cursor.close()
        connection.close()
        
        # Render the receipt template
        return render_template('payment_receipt_template.html', **receipt_data)
        
    except Exception as e:
        print(f"Error generating receipt: {e}")
        return jsonify({'error': str(e)}), 500

# API Routes for Sub Users
@app.route('/api/sub-users', methods=['GET'])
@login_required
def get_sub_users():
    """Get all sub users for the current user"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, sub_user_id, first_name, last_name, email, created_at, is_active
            FROM sub_users 
            WHERE created_by = %s 
            ORDER BY created_at DESC
        """, (session['user_id'],))
        
        sub_users = cursor.fetchall()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'sub_users': sub_users})
    except Exception as e:
        print(f"Get sub users error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-users', methods=['POST'])
@login_required
def create_sub_user():
    """Create a new sub user"""
    try:
        data = request.get_json()
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        email = data.get('email', '')
        
        if not first_name or not last_name:
            return jsonify({'success': False, 'message': 'First name and last name are required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Generate unique sub user ID
        sub_user_id = f"SUB{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
        
        # Generate random password
        password = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=12))
        password_hash = generate_password_hash(password)
        
        # Insert sub user
        cursor.execute("""
            INSERT INTO sub_users (sub_user_id, password_hash, first_name, last_name, email, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (sub_user_id, password_hash, first_name, last_name, email, session['user_id']))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True, 
            'message': 'Sub user created successfully',
            'sub_user_id': sub_user_id,
            'password': password
        })
    except Exception as e:
        print(f"Create sub user error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-users/<int:sub_user_id>', methods=['DELETE'])
@login_required
def delete_sub_user(sub_user_id):
    """Delete a sub user"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Check if sub user belongs to current user
        cursor.execute("SELECT id FROM sub_users WHERE id = %s AND created_by = %s", (sub_user_id, session['user_id']))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Sub user not found'}), 404
        
        # Delete sub user (cascade will handle related records)
        cursor.execute("DELETE FROM sub_users WHERE id = %s AND created_by = %s", (sub_user_id, session['user_id']))
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Sub user deleted successfully'})
    except Exception as e:
        print(f"Delete sub user error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-users/stats', methods=['GET'])
@login_required
def get_sub_user_stats():
    """Get sub user statistics for the current user"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Get total sub users
        cursor.execute("""
            SELECT COUNT(*) as total_sub_users
            FROM sub_users 
            WHERE created_by = %s
        """, (user_id,))
        total_sub_users = cursor.fetchone()['total_sub_users']
        
        # Get active sub users
        cursor.execute("""
            SELECT COUNT(*) as active_sub_users
            FROM sub_users 
            WHERE created_by = %s AND is_active = 1
        """, (user_id,))
        active_sub_users = cursor.fetchone()['active_sub_users']
        
        # Get inactive sub users
        cursor.execute("""
            SELECT COUNT(*) as inactive_sub_users
            FROM sub_users 
            WHERE created_by = %s AND is_active = 0
        """, (user_id,))
        inactive_sub_users = cursor.fetchone()['inactive_sub_users']
        
        # Get pending requests
        cursor.execute("""
            SELECT COUNT(*) as pending_requests
            FROM sub_user_requests sur
            JOIN sub_users su ON sur.sub_user_id = su.id
            WHERE su.created_by = %s AND sur.status = 'pending'
        """, (user_id,))
        pending_requests = cursor.fetchone()['pending_requests']
        
        connection.close()
        
        stats = {
            'total_sub_users': total_sub_users,
            'active_sub_users': active_sub_users,
            'inactive_sub_users': inactive_sub_users,
            'pending_requests': pending_requests
        }
        
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        print(f"Error getting sub user stats: {e}")
        return jsonify({'success': False, 'message': 'Failed to get sub user statistics'}), 500

@app.route('/api/sub-users/<int:sub_user_id>/report', methods=['GET'])
@login_required
def download_sub_user_report(sub_user_id):
    """Download comprehensive report for a sub user"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Get sub user details
        cursor.execute("""
            SELECT su.*, u.username as created_by_name
            FROM sub_users su
            JOIN users u ON su.created_by = u.id
            WHERE su.id = %s AND su.created_by = %s
        """, (sub_user_id, user_id))
        
        sub_user = cursor.fetchone()
        if not sub_user:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Sub user not found'}), 404
        
        # Get all requests made by this sub user
        cursor.execute("""
            SELECT sur.*, 
                   CASE WHEN sur.status = 'approved' AND sur.notes LIKE 'Approved - Unique ID:%' 
                        THEN TRIM(SUBSTRING(sur.notes, 25)) 
                        ELSE NULL END as unique_id
            FROM sub_user_requests sur
            WHERE sur.sub_user_id = %s
            ORDER BY sur.created_at DESC
        """, (sub_user_id,))
        
        requests = cursor.fetchall()
        
        # Get approved transactions from main user's account
        cursor.execute("""
            SELECT t.*, 'transaction' as source_type
            FROM transactions t
            WHERE t.created_by_sub_user = %s
            ORDER BY t.transaction_date DESC
        """, (sub_user_id,))
        
        approved_transactions = cursor.fetchall()
        
        # Get approved expenses from main user's account
        cursor.execute("""
            SELECT e.*, 'expense' as source_type
            FROM expenses e
            WHERE e.created_by_sub_user = %s
            ORDER BY e.expense_date DESC
        """, (sub_user_id,))
        
        approved_expenses = cursor.fetchall()
        
        # Calculate summary statistics
        total_requests = len(requests)
        approved_requests = len([r for r in requests if r['status'] == 'approved'])
        rejected_requests = len([r for r in requests if r['status'] == 'rejected'])
        pending_requests = len([r for r in requests if r['status'] == 'pending'])
        
        total_approved_amount = sum([float(t['amount']) for t in approved_transactions + approved_expenses])
        
        cursor.close()
        connection.close()
        
        # Create report data
        report_data = {
            'sub_user_info': {
                'sub_user_id': sub_user['sub_user_id'],
                'name': f"{sub_user['first_name']} {sub_user['last_name']}",
                'email': sub_user['email'],
                'created_at': sub_user['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'is_active': sub_user['is_active'],
                'created_by': sub_user['created_by_name']
            },
            'summary': {
                'total_requests': total_requests,
                'approved_requests': approved_requests,
                'rejected_requests': rejected_requests,
                'pending_requests': pending_requests,
                'total_approved_amount': total_approved_amount
            },
            'requests': requests,
            'approved_transactions': approved_transactions,
            'approved_expenses': approved_expenses
        }
        
        return jsonify({'success': True, 'report': report_data})
        
    except Exception as e:
        print(f"Download report error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-users/<int:sub_user_id>/reset-password', methods=['PUT'])
@login_required
def reset_sub_user_password(sub_user_id):
    """Reset sub user password"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Check if sub user belongs to current user
        cursor.execute("""
            SELECT id, sub_user_id, first_name, last_name FROM sub_users 
            WHERE id = %s AND created_by = %s
        """, (sub_user_id, user_id))
        
        sub_user = cursor.fetchone()
        if not sub_user:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Sub user not found'}), 404
        
        # Generate new password
        new_password = generate_password()
        password_hash = generate_password_hash(new_password)
        
        # Update password
        cursor.execute("""
            UPDATE sub_users 
            SET password_hash = %s, updated_at = NOW()
            WHERE id = %s
        """, (password_hash, sub_user_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True, 
            'message': 'Password reset successfully',
            'new_password': new_password,
            'sub_user_name': f"{sub_user['first_name']} {sub_user['last_name']}"
        })
        
    except Exception as e:
        print(f"Reset password error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-users/<int:sub_user_id>/toggle-status', methods=['PUT'])
@login_required
def toggle_sub_user_status(sub_user_id):
    """Toggle sub user active status"""
    try:
        data = request.get_json()
        is_active = data.get('is_active', True)
        user_id = session['user_id']
        
        print(f"Toggle status request: sub_user_id={sub_user_id}, is_active={is_active}, user_id={user_id}")
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Check if sub user belongs to current user
        cursor.execute("SELECT id FROM sub_users WHERE id = %s AND created_by = %s", (sub_user_id, user_id))
        sub_user = cursor.fetchone()
        print(f"Sub user found: {sub_user}")
        
        if not sub_user:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Sub user not found'}), 404
        
        # Update status
        cursor.execute("UPDATE sub_users SET is_active = %s WHERE id = %s AND created_by = %s", 
                      (is_active, sub_user_id, user_id))
        rows_affected = cursor.rowcount
        print(f"Rows affected: {rows_affected}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Sub user status updated successfully'})
    except Exception as e:
        print(f"Toggle sub user status error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Sub User Authentication
@app.route('/sub-user-login', methods=['POST'])
def sub_user_login():
    """Handle sub user login"""
    try:
        sub_user_id = request.form.get('sub_user_id')
        password = request.form.get('password')
        remember = request.form.get('remember')
        
        if not sub_user_id or not password:
            flash('Sub User ID and password are required.', 'error')
            return redirect(url_for('login'))
        
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("""
                SELECT su.*, u.username as created_by_username 
                FROM sub_users su 
                JOIN users u ON su.created_by = u.id 
                WHERE su.sub_user_id = %s
            """, (sub_user_id,))
            sub_user = cursor.fetchone()
            
            if sub_user:
                if not sub_user['is_active']:
                    flash('Your account is currently deactivated. Please contact your administrator.', 'error')
                    cursor.close()
                    connection.close()
                    return redirect(url_for('login'))
                
                if check_password_hash(sub_user['password_hash'], password):
                    session['sub_user_id'] = sub_user['id']
                    session['sub_user_name'] = f"{sub_user['first_name']} {sub_user['last_name']}"
                    session['sub_user_id_display'] = sub_user['sub_user_id']
                    session['created_by'] = sub_user['created_by']
                    session['created_by_username'] = sub_user['created_by_username']
                    
                    if remember:
                        session.permanent = True
                    
                    flash(f'Welcome back, {sub_user["first_name"]}!', 'success')
                    return redirect(url_for('sub_user_dashboard'))
                else:
                    flash('Invalid Sub User ID or password.', 'error')
            else:
                flash('Invalid Sub User ID or password.', 'error')
            
            cursor.close()
            connection.close()
        else:
            flash('Database connection error.', 'error')
    except Exception as e:
        print(f"Sub-user login error: {e}")
        flash('An error occurred during login. Please try again.', 'error')
    
    return redirect(url_for('login'))

@app.route('/sub-user-dashboard')
def sub_user_dashboard():
    """Sub user dashboard"""
    if 'sub_user_id' not in session:
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('login'))
    
    return render_template('sub_user_dashboard.html', 
                         sub_user_name=session.get('sub_user_name'),
                         sub_user_id=session.get('sub_user_id_display'))

@app.route('/sub-user-expenses')
def sub_user_expenses():
    """Sub user expenses page"""
    if 'sub_user_id' not in session:
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('login'))
    
    return render_template('sub_user_expenses.html', 
                         sub_user_name=session.get('sub_user_name'),
                         sub_user_id=session.get('sub_user_id_display'))

@app.route('/sub-user-transactions')
def sub_user_transactions():
    """Sub user transactions page"""
    if 'sub_user_id' not in session:
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('login'))
    
    return render_template('sub_user_transactions.html', 
                         sub_user_name=session.get('sub_user_name'),
                         sub_user_id=session.get('sub_user_id_display'))

@app.route('/sub-user-invoices')
def sub_user_invoices():
    """Sub user invoices page"""
    print(f"DEBUG: sub-user-invoices route accessed")
    print(f"DEBUG: Session keys: {list(session.keys())}")
    print(f"DEBUG: Session data: {dict(session)}")
    
    if 'sub_user_id' not in session:
        print("DEBUG: sub_user_id not in session, redirecting to login")
        flash('Please log in as a sub-user to access this page.', 'error')
        return redirect(url_for('login'))
    
    print(f"DEBUG: Sub-user authenticated: {session.get('sub_user_name')}")
    return render_template('sub_user_invoices.html', 
                         sub_user_name=session.get('sub_user_name'),
                         sub_user_id=session.get('sub_user_id_display'))

@app.route('/sub-user-settings')
def sub_user_settings():
    """Sub user settings page"""
    if 'sub_user_id' not in session:
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('login'))
    
    return render_template('sub_user_settings.html', 
                         sub_user_name=session.get('sub_user_name'),
                         sub_user_id=session.get('sub_user_id_display'))

@app.route('/sub-user-logout')
def sub_user_logout():
    """Sub user logout"""
    session.pop('sub_user_id', None)
    session.pop('sub_user_name', None)
    session.pop('sub_user_id_display', None)
    session.pop('created_by', None)
    session.pop('created_by_username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Sub User API Routes
@app.route('/api/sub-user/dashboard-data')
def get_sub_user_dashboard_data():
    """Get sub user dashboard metrics"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get net credit (approved transactions with credit type) from main user's transactions
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as net_credit
            FROM transactions 
            WHERE created_by_sub_user = %s AND transaction_type = 'credit'
        """, (sub_user_id,))
        net_credit = cursor.fetchone()['net_credit']
        
        # Get net debit (approved transactions with debit type) from main user's transactions
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as net_debit
            FROM transactions 
            WHERE created_by_sub_user = %s AND transaction_type = 'debit'
        """, (sub_user_id,))
        net_debit = cursor.fetchone()['net_debit']
        
        # Get IN invoice amounts (approved IN invoices - money received)
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as in_invoice_amount
            FROM invoices 
            WHERE created_by_sub_user = %s AND invoice_type = 'in' AND status = 'approved'
        """, (sub_user_id,))
        in_invoice_amount = cursor.fetchone()['in_invoice_amount']
        
        # Get OUT invoice amounts (approved OUT invoices - money paid)
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as out_invoice_amount
            FROM invoices 
            WHERE created_by_sub_user = %s AND invoice_type = 'out' AND status = 'approved'
        """, (sub_user_id,))
        out_invoice_amount = cursor.fetchone()['out_invoice_amount']
        
        # Get pending OUT invoice amounts (waiting for approval)
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as pending_out_invoice_amount
            FROM invoices 
            WHERE created_by_sub_user = %s AND invoice_type = 'out' AND status = 'pending'
        """, (sub_user_id,))
        pending_out_invoice_amount = cursor.fetchone()['pending_out_invoice_amount']
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'net_credit': float(net_credit or 0),
            'net_debit': float(net_debit or 0),
            'in_invoice_amount': float(in_invoice_amount or 0),
            'out_invoice_amount': float(out_invoice_amount or 0),
            'pending_out_invoice_amount': float(pending_out_invoice_amount or 0),
            'invoice_revenue': float(in_invoice_amount or 0)  # Keep for backward compatibility
        })
    except Exception as e:
        print(f"Dashboard data error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/recent-activity')
def get_sub_user_recent_activity():
    """Get sub user recent activity"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get recent requests with unique IDs for approved ones
        cursor.execute("""
            SELECT 
                sur.request_type as type, 
                sur.status, 
                sur.created_at,
                JSON_EXTRACT(sur.request_data, '$.title') as title,
                JSON_EXTRACT(sur.request_data, '$.description') as description,
                JSON_EXTRACT(sur.request_data, '$.amount') as amount,
                CASE 
                    WHEN sur.status = 'approved' AND sur.notes LIKE 'Approved - Unique ID:%' 
                    THEN TRIM(SUBSTRING(sur.notes, 25))  -- Extract unique ID from notes
                    ELSE NULL 
                END as unique_id
            FROM sub_user_requests sur
            WHERE sur.sub_user_id = %s 
            ORDER BY sur.created_at DESC 
            LIMIT 10
        """, (sub_user_id,))
        
        activities = cursor.fetchall()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'activities': activities})
    except Exception as e:
        print(f"Recent activity error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Sub User Expense Request API Routes
@app.route('/api/sub-user/expense-requests', methods=['GET'])
def get_sub_user_expense_requests():
    """Get sub user expense requests"""
    print(f"DEBUG: get_sub_user_expense_requests called, session keys: {list(session.keys())}")
    print(f"DEBUG: session data: {dict(session)}")
    if 'sub_user_id' not in session:
        print("DEBUG: sub_user_id not in session")
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            print("DEBUG: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        print(f"DEBUG: Fetching expense requests for sub_user_id: {sub_user_id}")
        
        # Test if sub_user_requests table exists
        cursor.execute("SHOW TABLES LIKE 'sub_user_requests'")
        table_exists = cursor.fetchone()
        print(f"DEBUG: sub_user_requests table exists: {table_exists is not None}")
        
        if not table_exists:
            print("DEBUG: sub_user_requests table does not exist, creating it...")
            create_sub_users_table()
        
        cursor.execute("""
            SELECT id, status, created_at, updated_at, notes,
                   JSON_EXTRACT(request_data, '$.title') as title,
                   JSON_EXTRACT(request_data, '$.description') as description,
                   JSON_EXTRACT(request_data, '$.amount') as amount,
                   JSON_EXTRACT(request_data, '$.category') as category,
                   JSON_EXTRACT(request_data, '$.expense_date') as expense_date,
                   JSON_EXTRACT(request_data, '$.payment_method') as payment_method,
                   CASE 
                       WHEN status = 'approved' AND notes LIKE 'Approved - Unique ID:%' 
                       THEN TRIM(SUBSTRING(notes, 25))  -- Extract unique ID from notes
                       ELSE NULL 
                   END as unique_id
            FROM sub_user_requests 
            WHERE sub_user_id = %s AND request_type = 'expense'
            ORDER BY created_at DESC
        """, (sub_user_id,))
        
        requests = cursor.fetchall()
        print(f"DEBUG: Found {len(requests)} expense requests")
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'requests': requests})
    except Exception as e:
        print(f"Expense requests error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/expense-requests', methods=['POST'])
def create_sub_user_expense_request():
    """Create sub user expense request"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        sub_user_id = session['sub_user_id']
        
        # Validate required fields
        required_fields = ['title', 'amount', 'expense_date', 'payment_method']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        # Optional fields with defaults
        if not data.get('description'):
            data['description'] = ''
        if not data.get('category'):
            data['category'] = 'General'
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Create request data JSON
        # Generate a single unique_id for the entire lifecycle (sub-user request → main user expense → main user transaction)
        try:
            expense_unique_id = generate_unique_id('EXP')
        except Exception:
            expense_unique_id = None
        request_data = {
            'title': data['title'],
            'description': data['description'],
            'amount': float(data['amount']),
            'category': data['category'],
            'expense_date': data['expense_date'],
            'payment_method': data['payment_method'],
            'payment_type': data.get('payment_type', 'non_invoice'),
            'bank_account_type': data.get('bank_account_type'),
            'bank_account_id': data.get('bank_account_id'),
            'unique_id': expense_unique_id
        }
        
        # Add vendor bank details if provided
        if data.get('vendor_bank_details'):
            request_data['vendor_bank_details'] = data['vendor_bank_details']
        
        # Insert expense request
        cursor.execute("""
            INSERT INTO sub_user_requests (sub_user_id, request_type, request_data, status)
            VALUES (%s, 'expense', %s, 'pending')
        """, (sub_user_id, json.dumps(request_data)))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Expense request submitted successfully'})
    except Exception as e:
        print(f"Create expense request error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/expense-requests/<int:expense_id>', methods=['DELETE'])
def delete_sub_user_expense_request(expense_id):
    """Delete sub user expense request and adjust financial balances"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get the expense request details and main user info
        cursor.execute("""
            SELECT sur.id, sur.request_data, sur.status, sur.notes,
                   JSON_EXTRACT(sur.request_data, '$.amount') as amount,
                   JSON_EXTRACT(sur.request_data, '$.payment_method') as payment_method,
                   JSON_EXTRACT(sur.request_data, '$.title') as title,
                   su.created_by as main_user_id
            FROM sub_user_requests sur
            JOIN sub_users su ON sur.sub_user_id = su.id
            WHERE sur.id = %s AND sur.sub_user_id = %s AND sur.request_type = 'expense'
        """, (expense_id, sub_user_id))
        
        expense_request = cursor.fetchone()
        
        if not expense_request:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Expense request not found or access denied'}), 404
        
        # Only adjust balances if the expense was approved (had financial impact)
        if expense_request['status'] == 'approved':
            amount = float(expense_request['amount']) if expense_request['amount'] else 0
            main_user_id = expense_request['main_user_id']
            
            print(f"DEBUG: Processing expense refund - amount: {amount}, main_user_id: {main_user_id}")
            
            if amount > 0:
                # Validate that the main user exists
                cursor.execute("SELECT id FROM users WHERE id = %s", (main_user_id,))
                if not cursor.fetchone():
                    print(f"Warning: Main user {main_user_id} not found, skipping refund")
                else:
                    # Get the original approval payment details from request_data
                    request_data_json = json.loads(expense_request['request_data'])
                    approved_payment_method = request_data_json.get('approved_payment_method', 'cash')
                    approved_bank_account_id = request_data_json.get('approved_bank_account_id')
                    
                    print(f"DEBUG: Original payment method: {approved_payment_method}, bank_account_id: {approved_bank_account_id}")
                    
                    # Refund to the original payment method
                    refund_payment_method = 'CASH'
                    
                    if approved_payment_method == 'bank' and approved_bank_account_id:
                        # Refund to the original bank account
                        cursor.execute("""
                            SELECT bank_name FROM bank_accounts 
                            WHERE id = %s AND user_id = %s
                        """, (approved_bank_account_id, main_user_id))
                        
                        bank_account = cursor.fetchone()
                        if bank_account:
                            cursor.execute("""
                                UPDATE bank_accounts 
                                SET current_balance = current_balance + %s 
                                WHERE id = %s AND user_id = %s
                            """, (amount, approved_bank_account_id, main_user_id))
                            refund_payment_method = bank_account['bank_name']
                            print(f"DEBUG: Refunded {amount} to original bank account {approved_bank_account_id} ({refund_payment_method})")
                        else:
                            # Original bank account not found, refund to cash
                            cursor.execute("""
                                UPDATE users 
                                SET cash_balance = cash_balance + %s 
                                WHERE id = %s
                            """, (amount, main_user_id))
                            print(f"DEBUG: Original bank account not found, refunded {amount} to cash balance")
                    else:
                        # Refund to cash balance (original payment was cash)
                        cursor.execute("""
                            UPDATE users 
                            SET cash_balance = cash_balance + %s 
                            WHERE id = %s
                        """, (amount, main_user_id))
                        print(f"DEBUG: Refunded {amount} to cash balance (original payment was cash)")
                    
                    # Delete the original debit transaction
                    expense_title = expense_request['title'].strip('"') if expense_request['title'] else 'Unknown'
                    cursor.execute("""
                        DELETE FROM transactions 
                        WHERE user_id = %s 
                        AND transaction_type = 'debit' 
                        AND amount = %s 
                        AND description LIKE %s
                        LIMIT 1
                    """, (main_user_id, amount, f"%{expense_title}%"))
                    
                    deleted_transactions = cursor.rowcount
                    print(f"DEBUG: Deleted {deleted_transactions} original debit transaction(s)")
                    
                    # Add a credit refund transaction to log the refund
                    refund_unique_id = generate_unique_id('REF')
                    cursor.execute("""
                        INSERT INTO transactions (
                            user_id, unique_id, title, description, amount, transaction_type, 
                            transaction_date, payment_method, created_by_sub_user
                        ) VALUES (
                            %s, %s, %s, %s, %s, 'credit',
                            NOW(), %s, %s
                        )
                    """, (
                        main_user_id,
                        refund_unique_id,
                        f"Expense Refund: {expense_title}",
                        f"Refund for deleted approved expense - {expense_title}",
                        amount,
                        refund_payment_method,
                        sub_user_id
                    ))
                    print(f"DEBUG: Added refund transaction with payment method: {refund_payment_method}")
        
        # Delete the expense request
        cursor.execute("""
            DELETE FROM sub_user_requests 
            WHERE id = %s AND sub_user_id = %s AND request_type = 'expense'
        """, (expense_id, sub_user_id))
        
        # Get updated balance for verification before closing connection
        if expense_request['status'] == 'approved' and expense_request['main_user_id']:
            cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (expense_request['main_user_id'],))
            updated_cash_balance = cursor.fetchone()
            if updated_cash_balance:
                print(f"DEBUG: Updated cash balance for main user {expense_request['main_user_id']}: {updated_cash_balance[0]}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Expense request deleted successfully and balances adjusted'})
    except Exception as e:
        print(f"Delete expense request error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/approved-expenses', methods=['GET'])
def get_sub_user_approved_expenses():
    """Get approved expenses for sub user that have been converted to transactions"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get approved expenses that have been converted to transactions
        cursor.execute("""
            SELECT e.*, t.unique_id as transaction_unique_id
            FROM expenses e
            LEFT JOIN transactions t ON e.unique_id = t.unique_id
            WHERE e.created_by_sub_user = %s
            ORDER BY e.expense_date DESC
        """, (sub_user_id,))
        
        approved_expenses = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'expenses': approved_expenses
        })
        
    except Exception as e:
        print(f"Error getting approved expenses: {e}")
        return jsonify({'success': False, 'message': 'Failed to get approved expenses'}), 500

@app.route('/api/sub-user/expense-requests/<int:expense_id>/approve', methods=['POST'])
def approve_sub_user_expense_request(expense_id):
    """Approve sub user expense request and convert to transaction"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get the expense request details
        cursor.execute("""
            SELECT sur.id, sur.request_data, sur.status, sur.notes,
                   JSON_EXTRACT(sur.request_data, '$.amount') as amount,
                   JSON_EXTRACT(sur.request_data, '$.payment_method') as payment_method,
                   JSON_EXTRACT(sur.request_data, '$.title') as title,
                   JSON_EXTRACT(sur.request_data, '$.category') as category,
                   JSON_EXTRACT(sur.request_data, '$.expense_date') as expense_date,
                   JSON_EXTRACT(sur.request_data, '$.description') as description,
                   su.created_by as main_user_id
            FROM sub_user_requests sur
            JOIN sub_users su ON sur.sub_user_id = su.id
            WHERE sur.id = %s AND sur.sub_user_id = %s AND sur.request_type = 'expense'
        """, (expense_id, sub_user_id))
        
        expense_request = cursor.fetchone()
        
        if not expense_request:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Expense request not found or access denied'}), 404
        
        if expense_request['status'] != 'pending':
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Expense request is not pending approval'}), 400
        
        # Generate or retrieve unique ID for the expense (preserve sub-user request unique_id if present)
        try:
            req_json = json.loads(expense_request['request_data']) if expense_request.get('request_data') else {}
        except Exception:
            req_json = {}
        unique_id = req_json.get('unique_id') or generate_unique_id('EXP')
        
        # Get main user's default account
        main_user_id = expense_request['main_user_id']
        cursor.execute("""
            SELECT id FROM bank_accounts 
            WHERE user_id = %s
            ORDER BY id LIMIT 1
        """, (main_user_id,))
        
        default_account = cursor.fetchone()
        bank_account_id = default_account['id'] if default_account else None
        
        # If no default account, get the first active account
        if not bank_account_id:
            cursor.execute("""
                SELECT id FROM bank_accounts 
                WHERE user_id = %s
                ORDER BY id LIMIT 1
            """, (main_user_id,))
            
            first_account = cursor.fetchone()
            bank_account_id = first_account['id'] if first_account else None
        
        # Create the expense record
        amount = float(expense_request['amount'])
        title = expense_request['title'] or 'Sub User Expense'
        category = expense_request['category'] or ''
        payment_method = expense_request['payment_method'] or 'cash'
        expense_date = expense_request['expense_date']
        description = expense_request['description'] or ''
        
        cursor.execute("""
            INSERT INTO expenses (
                user_id, unique_id, title, purpose, description, amount, 
                category, payment_method, payment_type, expense_type, 
                expense_date, bank_account_id, created_by_sub_user
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            main_user_id, unique_id, title, title, description, amount,
            category, payment_method, 'non_invoice', 'completed',
            expense_date, bank_account_id, sub_user_id
        ))
        
        expense_db_id = cursor.lastrowid
        
        # Create the transaction record using the SAME unique_id
        transaction_unique_id = unique_id
        cursor.execute("""
            INSERT INTO transactions (
                user_id, unique_id, title, description, purpose, amount,
                transaction_type, category, payment_method, transaction_date,
                source, source_id, created_by_sub_user, bank_account_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            main_user_id, transaction_unique_id, title, description, title, amount,
            'debit', category, payment_method, expense_date,
            'expense', expense_db_id, sub_user_id, bank_account_id
        ))
        
        # Update account balance
        if payment_method == 'online' and bank_account_id:
            cursor.execute("""
                UPDATE bank_accounts 
                SET current_balance = current_balance - %s 
                WHERE id = %s AND user_id = %s
            """, (amount, bank_account_id, main_user_id))
        else:
            # For cash payments, deduct from cash balance
            cursor.execute("""
                UPDATE users 
                SET cash_balance = cash_balance - %s 
                WHERE id = %s
            """, (amount, main_user_id))
        
        # Update the expense request status
        cursor.execute("""
            UPDATE sub_user_requests 
            SET status = 'approved', 
                notes = CONCAT(COALESCE(notes, ''), '\\nApproved - Unique ID: ', %s),
                updated_at = NOW()
            WHERE id = %s
        """, (unique_id, expense_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': f'Expense request approved successfully. Unique ID: {unique_id}',
            'unique_id': unique_id
        })
        
    except Exception as e:
        print(f"Error approving expense request: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/expense-requests/bulk-delete', methods=['POST'])
def bulk_delete_sub_user_expense_requests():
    """Bulk delete sub user expense requests and adjust financial balances"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        expense_ids = data.get('expense_ids', [])
        
        if not expense_ids:
            return jsonify({'success': False, 'message': 'No expense IDs provided'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get all expense requests to be deleted
        placeholders = ','.join(['%s'] * len(expense_ids))
        cursor.execute(f"""
            SELECT sur.id, sur.request_data, sur.status, sur.notes,
                   JSON_EXTRACT(sur.request_data, '$.amount') as amount,
                   JSON_EXTRACT(sur.request_data, '$.payment_method') as payment_method,
                   JSON_EXTRACT(sur.request_data, '$.title') as title,
                   su.created_by as main_user_id
            FROM sub_user_requests sur
            JOIN sub_users su ON sur.sub_user_id = su.id
            WHERE sur.id IN ({placeholders}) AND sur.sub_user_id = %s AND sur.request_type = 'expense'
        """, expense_ids + [sub_user_id])
        
        expense_requests = cursor.fetchall()
        
        if not expense_requests:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'No expense requests found or access denied'}), 404
        
        total_adjustment = 0
        adjustments_made = 0
        
        # Process each expense request for financial adjustments
        for expense_request in expense_requests:
            if expense_request['status'] == 'approved':
                amount = float(expense_request['amount']) if expense_request['amount'] else 0
                payment_method = expense_request['payment_method']
                main_user_id = expense_request['main_user_id']
                
                print(f"DEBUG: Bulk delete - processing expense {expense_request['id']}, amount: {amount}, payment_method: {payment_method}, main_user_id: {main_user_id}")
                
                if amount > 0:
                    # Validate that the main user exists
                    cursor.execute("SELECT id FROM users WHERE id = %s", (main_user_id,))
                    if not cursor.fetchone():
                        print(f"Warning: Main user {main_user_id} not found, skipping balance adjustment for expense {expense_request['id']}")
                        continue
                    
                    # Adjust the main user's account balance
                    if payment_method == 'online':
                        # For online payments, add back to bank account balance
                        cursor.execute("""
                            SELECT id FROM bank_accounts 
                            WHERE user_id = %s 
                            ORDER BY id LIMIT 1
                        """, (main_user_id,))
                        
                        bank_account = cursor.fetchone()
                        if bank_account:
                            cursor.execute("""
                                UPDATE bank_accounts 
                                SET current_balance = current_balance + %s 
                                WHERE id = %s AND user_id = %s
                            """, (amount, bank_account['id'], main_user_id))
                        else:
                            # No bank account found, add to cash balance
                            cursor.execute("""
                                UPDATE users 
                                SET cash_balance = cash_balance + %s 
                                WHERE id = %s
                            """, (amount, main_user_id))
                            
                    elif payment_method == 'cash':
                        # For cash payments, add back to cash balance
                        cursor.execute("""
                            UPDATE users 
                            SET cash_balance = cash_balance + %s 
                            WHERE id = %s
                        """, (amount, main_user_id))
                    
                    # Add a credit transaction to log the adjustment
                    cursor.execute("""
                        INSERT INTO transactions (
                            user_id, transaction_type, amount, description, 
                            transaction_date, payment_method, created_by_sub_user
                        ) VALUES (
                            %s, 'credit', %s, %s, 
                            NOW(), %s, %s
                        )
                    """, (
                        main_user_id, 
                        amount, 
                        f"Bulk expense deletion adjustment - {expense_request['title'] or 'Unknown'}", 
                        payment_method,
                        sub_user_id
                    ))
                    
                    total_adjustment += amount
                    adjustments_made += 1
        
        # Delete all expense requests
        cursor.execute(f"""
            DELETE FROM sub_user_requests 
            WHERE id IN ({placeholders}) AND sub_user_id = %s AND request_type = 'expense'
        """, expense_ids + [sub_user_id])
        
        deleted_count = cursor.rowcount
        
        connection.commit()
        cursor.close()
        connection.close()
        
        message = f"Successfully deleted {deleted_count} expense request(s)"
        if adjustments_made > 0:
            message += f" and adjusted balances by ₹{total_adjustment:.2f} across {adjustments_made} approved expenses"
        
        return jsonify({
            'success': True, 
            'message': message,
            'deleted_count': deleted_count,
            'adjustments_made': adjustments_made,
            'total_adjustment': total_adjustment
        })
        
    except Exception as e:
        print(f"Bulk delete expense requests error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/transaction-requests/<int:transaction_id>', methods=['DELETE'])
def delete_sub_user_transaction_request(transaction_id):
    """Delete sub user transaction request"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Check if the transaction request belongs to the current sub user
        cursor.execute("""
            SELECT id FROM sub_user_requests 
            WHERE id = %s AND sub_user_id = %s AND request_type = 'transaction'
        """, (transaction_id, sub_user_id))
        
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Transaction request not found or access denied'}), 404
        
        # Delete the transaction request
        cursor.execute("""
            DELETE FROM sub_user_requests 
            WHERE id = %s AND sub_user_id = %s AND request_type = 'transaction'
        """, (transaction_id, sub_user_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Transaction request deleted successfully'})
    except Exception as e:
        print(f"Delete transaction request error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/transaction-requests/bulk-delete', methods=['POST'])
def bulk_delete_sub_user_transaction_requests():
    """Bulk delete sub user transaction requests"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        transaction_ids = data.get('transaction_ids', [])
        
        if not transaction_ids:
            return jsonify({'success': False, 'message': 'No transaction IDs provided'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get all transaction requests to be deleted
        placeholders = ','.join(['%s'] * len(transaction_ids))
        cursor.execute(f"""
            SELECT id FROM sub_user_requests 
            WHERE id IN ({placeholders}) AND sub_user_id = %s AND request_type = 'transaction'
        """, transaction_ids + [sub_user_id])
        
        transaction_requests = cursor.fetchall()
        
        if not transaction_requests:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'No transaction requests found or access denied'}), 404
        
        # Delete all transaction requests
        cursor.execute(f"""
            DELETE FROM sub_user_requests 
            WHERE id IN ({placeholders}) AND sub_user_id = %s AND request_type = 'transaction'
        """, transaction_ids + [sub_user_id])
        
        deleted_count = cursor.rowcount
        
        connection.commit()
        cursor.close()
        connection.close()
        
        message = f"Successfully deleted {deleted_count} transaction request(s)"
        
        return jsonify({
            'success': True, 
            'message': message,
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        print(f"Bulk delete transaction requests error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/transactions/export', methods=['POST'])
def export_sub_user_transactions():
    """Export selected sub user transactions as PDF"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        transaction_ids = request.form.getlist('transaction_ids')
        if not transaction_ids:
            return jsonify({'success': False, 'message': 'No transactions selected'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get selected transactions
        placeholders = ','.join(['%s'] * len(transaction_ids))
        cursor.execute(f"""
            SELECT id, status, created_at, updated_at, notes,
                   JSON_EXTRACT(request_data, '$.title') as title,
                   JSON_EXTRACT(request_data, '$.description') as description,
                   JSON_EXTRACT(request_data, '$.amount') as amount,
                   JSON_EXTRACT(request_data, '$.category') as category,
                   JSON_EXTRACT(request_data, '$.transaction_date') as transaction_date,
                   JSON_EXTRACT(request_data, '$.payment_method') as payment_method,
                   JSON_EXTRACT(request_data, '$.transaction_type') as transaction_type
            FROM sub_user_requests 
            WHERE id IN ({placeholders}) AND sub_user_id = %s AND request_type = 'transaction'
            ORDER BY created_at DESC
        """, transaction_ids + [sub_user_id])
        
        transactions = cursor.fetchall()
        cursor.close()
        connection.close()
        
        if not transactions:
            return jsonify({'success': False, 'message': 'No transactions found'}), 404
        
        # Generate proper PDF using reportlab
        from flask import make_response
        import io
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        except ImportError as e:
            print(f"ReportLab import error: {e}")
            return jsonify({'success': False, 'message': 'PDF generation library not available'}), 500
        
        # Create a BytesIO buffer to hold the PDF
        buffer = io.BytesIO()
        
        try:
            # Create the PDF document
            doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
        except Exception as e:
            print(f"Error creating PDF document: {e}")
            return jsonify({'success': False, 'message': 'Error creating PDF document'}), 500
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )
        
        # Build the PDF content
        story = []
        
        # Title
        title = Paragraph("TRANSACTION REQUESTS EXPORT", title_style)
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Export info
        export_info = f"""
        <b>Generated on:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>
        <b>Total Transactions:</b> {len(transactions)}<br/>
        <b>Sub User ID:</b> {sub_user_id}
        """
        info_para = Paragraph(export_info, styles['Normal'])
        story.append(info_para)
        story.append(Spacer(1, 20))
        
        # Create table data
        table_data = [['ID', 'Title', 'Amount', 'Type', 'Category', 'Date', 'Status']]
        
        for transaction in transactions:
            # Safely handle potential None values and format data
            try:
                amount = float(transaction['amount']) if transaction['amount'] else 0
                amount_str = f"₹{amount:.2f}" if amount > 0 else 'N/A'
            except (ValueError, TypeError):
                amount_str = 'N/A'
            
            row = [
                str(transaction['id']) if transaction['id'] else 'N/A',
                str(transaction['title'])[:30] + '...' if transaction['title'] and len(str(transaction['title'])) > 30 else (transaction['title'] or 'N/A'),
                amount_str,
                str(transaction['transaction_type'])[:15] + '...' if transaction['transaction_type'] and len(str(transaction['transaction_type'])) > 15 else (transaction['transaction_type'] or 'N/A'),
                str(transaction['category'])[:20] + '...' if transaction['category'] and len(str(transaction['category'])) > 20 else (transaction['category'] or 'N/A'),
                transaction['transaction_date'] or 'N/A',
                transaction['status'].upper() if transaction['status'] else 'N/A'
            ]
            table_data.append(row)
        
        # Create table
        table = Table(table_data, colWidths=[0.5*inch, 1.5*inch, 0.8*inch, 0.8*inch, 1*inch, 0.8*inch, 0.8*inch])
        
        # Style the table
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])
        
        table.setStyle(table_style)
        story.append(table)
        
        try:
            # Build PDF
            doc.build(story)
            
            # Get the PDF content
            pdf_content = buffer.getvalue()
            buffer.close()
            
            if not pdf_content:
                return jsonify({'success': False, 'message': 'Generated PDF is empty'}), 500
                
        except Exception as e:
            print(f"Error building PDF: {e}")
            buffer.close()
            return jsonify({'success': False, 'message': 'Error building PDF document'}), 500
        
        # Create response
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=transactions_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        return response
        
    except Exception as e:
        print(f"Export transactions error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/expenses/export', methods=['POST'])
def export_sub_user_expenses():
    """Export selected sub user expenses as PDF"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        expense_ids = request.form.getlist('expense_ids')
        if not expense_ids:
            return jsonify({'success': False, 'message': 'No expenses selected'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get selected expenses
        placeholders = ','.join(['%s'] * len(expense_ids))
        cursor.execute(f"""
            SELECT id, status, created_at, updated_at, notes,
                   JSON_EXTRACT(request_data, '$.title') as title,
                   JSON_EXTRACT(request_data, '$.description') as description,
                   JSON_EXTRACT(request_data, '$.amount') as amount,
                   JSON_EXTRACT(request_data, '$.category') as category,
                   JSON_EXTRACT(request_data, '$.expense_date') as expense_date,
                   JSON_EXTRACT(request_data, '$.payment_method') as payment_method,
                   CASE 
                       WHEN status = 'approved' AND notes LIKE 'Approved - Unique ID:%' 
                       THEN TRIM(SUBSTRING(notes, 25))
                       ELSE NULL 
                   END as unique_id
            FROM sub_user_requests 
            WHERE id IN ({placeholders}) AND sub_user_id = %s AND request_type = 'expense'
            ORDER BY created_at DESC
        """, expense_ids + [sub_user_id])
        
        expenses = cursor.fetchall()
        cursor.close()
        connection.close()
        
        if not expenses:
            return jsonify({'success': False, 'message': 'No expenses found'}), 404
        
        # Generate proper PDF using reportlab
        from flask import make_response
        import io
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        except ImportError as e:
            print(f"ReportLab import error: {e}")
            return jsonify({'success': False, 'message': 'PDF generation library not available'}), 500
        
        # Create a BytesIO buffer to hold the PDF
        buffer = io.BytesIO()
        
        try:
            # Create the PDF document
            doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch, bottomMargin=1*inch)
        except Exception as e:
            print(f"Error creating PDF document: {e}")
            return jsonify({'success': False, 'message': 'Error creating PDF document'}), 500
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )
        
        # Build the PDF content
        story = []
        
        # Title
        title = Paragraph("EXPENSE REQUESTS EXPORT", title_style)
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Export info
        export_info = f"""
        <b>Generated on:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>
        <b>Total Expenses:</b> {len(expenses)}<br/>
        <b>Sub User ID:</b> {sub_user_id}
        """
        info_para = Paragraph(export_info, styles['Normal'])
        story.append(info_para)
        story.append(Spacer(1, 20))
        
        # Create table data
        table_data = [['ID', 'Title', 'Amount', 'Category', 'Date', 'Status', 'Unique ID']]
        
        for expense in expenses:
            # Safely handle potential None values and format data
            try:
                amount = float(expense['amount']) if expense['amount'] else 0
                amount_str = f"₹{amount:.2f}" if amount > 0 else 'N/A'
            except (ValueError, TypeError):
                amount_str = 'N/A'
            
            row = [
                str(expense['id']) if expense['id'] else 'N/A',
                str(expense['title'])[:30] + '...' if expense['title'] and len(str(expense['title'])) > 30 else (expense['title'] or 'N/A'),
                amount_str,
                str(expense['category'])[:20] + '...' if expense['category'] and len(str(expense['category'])) > 20 else (expense['category'] or 'N/A'),
                expense['expense_date'] or 'N/A',
                expense['status'].upper() if expense['status'] else 'N/A',
                str(expense['unique_id'])[:15] + '...' if expense['unique_id'] and len(str(expense['unique_id'])) > 15 else (expense['unique_id'] or 'N/A')
            ]
            table_data.append(row)
        
        # Create table
        table = Table(table_data, colWidths=[0.5*inch, 1.5*inch, 0.8*inch, 1*inch, 0.8*inch, 0.8*inch, 1*inch])
        
        # Style the table
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ])
        
        table.setStyle(table_style)
        story.append(table)
        
        try:
            # Build PDF
            doc.build(story)
            
            # Get the PDF content
            pdf_content = buffer.getvalue()
            buffer.close()
            
            if not pdf_content:
                return jsonify({'success': False, 'message': 'Generated PDF is empty'}), 500
                
        except Exception as e:
            print(f"Error building PDF: {e}")
            buffer.close()
            return jsonify({'success': False, 'message': 'Error building PDF document'}), 500
        
        # Create response
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=expenses_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        return response
        
    except Exception as e:
        print(f"Export expenses error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Sub User Transaction Request API Routes
@app.route('/api/sub-user/transaction-requests', methods=['GET'])
def get_sub_user_transaction_requests():
    """Get sub user transaction requests"""
    print(f"DEBUG: get_sub_user_transaction_requests called, session keys: {list(session.keys())}")
    print(f"DEBUG: session data: {dict(session)}")
    if 'sub_user_id' not in session:
        print("DEBUG: sub_user_id not in session")
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            print("DEBUG: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        print(f"DEBUG: Fetching transaction requests for sub_user_id: {sub_user_id}")
        
        # Test if sub_user_requests table exists
        cursor.execute("SHOW TABLES LIKE 'sub_user_requests'")
        table_exists = cursor.fetchone()
        print(f"DEBUG: sub_user_requests table exists: {table_exists is not None}")
        
        if not table_exists:
            print("DEBUG: sub_user_requests table does not exist, creating it...")
            create_sub_users_table()
        
        cursor.execute("""
            SELECT id, status, created_at, updated_at, notes,
                   JSON_EXTRACT(request_data, '$.title') as title,
                   JSON_EXTRACT(request_data, '$.description') as description,
                   JSON_EXTRACT(request_data, '$.amount') as amount,
                   JSON_EXTRACT(request_data, '$.transaction_type') as transaction_type,
                   JSON_EXTRACT(request_data, '$.transaction_date') as transaction_date,
                   JSON_EXTRACT(request_data, '$.payment_method') as payment_method,
                   JSON_EXTRACT(request_data, '$.category') as category,
                   CASE 
                       WHEN status = 'approved' AND notes LIKE 'Approved - Unique ID:%' 
                       THEN TRIM(SUBSTRING(notes, 25))  -- Extract unique ID from notes
                       ELSE NULL 
                   END as unique_id
            FROM sub_user_requests 
            WHERE sub_user_id = %s AND request_type = 'transaction'
            ORDER BY created_at DESC
        """, (sub_user_id,))
        
        requests = cursor.fetchall()
        print(f"DEBUG: Found {len(requests)} transaction requests")
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'requests': requests})
    except Exception as e:
        print(f"Transaction requests error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/transaction-requests', methods=['POST'])
def create_sub_user_transaction_request():
    """Create sub user transaction request"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        sub_user_id = session['sub_user_id']
        
        # Validate required fields
        required_fields = ['title', 'description', 'amount', 'transaction_type', 'transaction_date', 'payment_method']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        
        # Map frontend transaction types to backend types
        transaction_type_mapping = {
            'income': 'credit',
            'expense': 'debit'
        }
        backend_transaction_type = transaction_type_mapping.get(data['transaction_type'], data['transaction_type'])
        
        # Create request data JSON
        request_data = {
            'title': data['title'],
            'description': data['description'],
            'amount': float(data['amount']),
            'transaction_type': backend_transaction_type,
            'transaction_date': data['transaction_date'],
            'payment_method': data['payment_method'],
            'category': data.get('category', ''),
            'bank_account_id': data.get('bank_account_id')
        }
        
        # Insert transaction request
        cursor.execute("""
            INSERT INTO sub_user_requests (sub_user_id, request_type, request_data, status)
            VALUES (%s, 'transaction', %s, 'pending')
        """, (sub_user_id, json.dumps(request_data)))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Transaction request submitted successfully'})
    except Exception as e:
        print(f"Create transaction request error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Test endpoint for debugging
@app.route('/api/sub-user/test', methods=['GET'])
def test_sub_user_api():
    """Test endpoint to debug session and database issues"""
    print(f"DEBUG: test_sub_user_api called, session keys: {list(session.keys())}")
    print(f"DEBUG: session data: {dict(session)}")
    
    try:
        connection = get_db_connection()
        if not connection:
            print("DEBUG: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Test if sub_user_requests table exists
        cursor.execute("SHOW TABLES LIKE 'sub_user_requests'")
        table_exists = cursor.fetchone()
        print(f"DEBUG: sub_user_requests table exists: {table_exists is not None}")
        
        # Test if sub_users table exists
        cursor.execute("SHOW TABLES LIKE 'sub_users'")
        sub_users_table_exists = cursor.fetchone()
        print(f"DEBUG: sub_users table exists: {sub_users_table_exists is not None}")
        
        # Test if we can query the sub_user_requests table
        try:
            cursor.execute("SELECT COUNT(*) as count FROM sub_user_requests")
            count_result = cursor.fetchone()
            print(f"DEBUG: sub_user_requests table has {count_result['count']} records")
        except Exception as e:
            print(f"DEBUG: Error querying sub_user_requests table: {e}")
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Test API working',
            'session_keys': list(session.keys()),
            'session_data': dict(session),
            'sub_user_requests_table_exists': table_exists is not None,
            'sub_users_table_exists': sub_users_table_exists is not None,
            'has_sub_user_id': 'sub_user_id' in session
        })
    except Exception as e:
        print(f"Test endpoint error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

# Sub User Bank Accounts API Route
@app.route('/api/sub-user/banks', methods=['GET'])
def get_sub_user_banks():
    """Get bank accounts for sub user's main user"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get the main user ID who created this sub user
        cursor.execute("SELECT created_by FROM sub_users WHERE id = %s", (sub_user_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': 'Sub user not found'}), 404
        
        main_user_id = result['created_by']
        
        # Get bank accounts for the main user
        cursor.execute("""
            SELECT id, bank_name, account_number, ifsc_code, current_balance
            FROM bank_accounts 
            WHERE user_id = %s 
            ORDER BY bank_name
        """, (main_user_id,))
        
        banks = cursor.fetchall()
        print(f"DEBUG: Found {len(banks)} bank accounts for main user {main_user_id}")
        for bank in banks:
            print(f"DEBUG: Bank - {bank}")
        
        cursor.close()
        connection.close()
        
        return jsonify(banks)
    except Exception as e:
        print(f"Sub user banks error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Sub User Bank Account Management API Routes
@app.route('/api/sub-user/bank-account', methods=['GET'])
def get_sub_user_bank_account():
    """Get sub user's own bank account details"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get sub user's bank account
        cursor.execute("""
            SELECT id, bank_name, account_number, ifsc_code, account_holder_name, upi_id, phone_number, notes, created_at, updated_at
            FROM sub_user_bank_accounts 
            WHERE sub_user_id = %s
        """, (sub_user_id,))
        
        bank_account = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if bank_account:
            return jsonify({'success': True, 'bank_account': bank_account})
        else:
            return jsonify({'success': False, 'message': 'No bank account found'}), 404
            
    except Exception as e:
        print(f"Get sub user bank account error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/bank-account', methods=['POST'])
def create_sub_user_bank_account():
    """Create sub user's bank account"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['bank_name', 'account_number', 'ifsc_code', 'account_holder_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field.replace("_", " ").title()} is required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        sub_user_id = session['sub_user_id']
        
        # Check if bank account already exists for this sub user
        cursor.execute("SELECT id FROM sub_user_bank_accounts WHERE sub_user_id = %s", (sub_user_id,))
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Bank account already exists for this sub user'}), 400
        
        # Create bank account
        cursor.execute("""
            INSERT INTO sub_user_bank_accounts (sub_user_id, bank_name, account_number, ifsc_code, account_holder_name, upi_id, phone_number, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            sub_user_id,
            data['bank_name'],
            data['account_number'],
            data['ifsc_code'],
            data['account_holder_name'],
            data.get('upi_id', ''),
            data.get('phone_number', ''),
            data.get('notes', '')
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Bank account created successfully'})
        
    except Exception as e:
        print(f"Create sub user bank account error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/bank-account/<int:bank_account_id>', methods=['PUT'])
def update_sub_user_bank_account(bank_account_id):
    """Update sub user's bank account"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['bank_name', 'account_number', 'ifsc_code', 'account_holder_name']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field.replace("_", " ").title()} is required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        sub_user_id = session['sub_user_id']
        
        # Check if bank account belongs to this sub user
        cursor.execute("SELECT id FROM sub_user_bank_accounts WHERE id = %s AND sub_user_id = %s", (bank_account_id, sub_user_id))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Bank account not found or access denied'}), 404
        
        # Update bank account
        cursor.execute("""
            UPDATE sub_user_bank_accounts 
            SET bank_name = %s, account_number = %s, ifsc_code = %s, account_holder_name = %s, 
                upi_id = %s, phone_number = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND sub_user_id = %s
        """, (
            data['bank_name'],
            data['account_number'],
            data['ifsc_code'],
            data['account_holder_name'],
            data.get('upi_id', ''),
            data.get('phone_number', ''),
            data.get('notes', ''),
            bank_account_id,
            sub_user_id
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Bank account updated successfully'})
        
    except Exception as e:
        print(f"Update sub user bank account error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/bank-account/<int:bank_account_id>', methods=['DELETE'])
def delete_sub_user_bank_account(bank_account_id):
    """Delete sub user's bank account"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        sub_user_id = session['sub_user_id']
        
        # Check if bank account belongs to this sub user
        cursor.execute("SELECT id FROM sub_user_bank_accounts WHERE id = %s AND sub_user_id = %s", (bank_account_id, sub_user_id))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Bank account not found or access denied'}), 404
        
        # Delete bank account
        cursor.execute("DELETE FROM sub_user_bank_accounts WHERE id = %s AND sub_user_id = %s", (bank_account_id, sub_user_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Bank account deleted successfully'})
        
    except Exception as e:
        print(f"Delete sub user bank account error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Get Sub User Bank Details for Main User
@app.route('/api/sub-user-bank-details/<sub_user_id>', methods=['GET'])
@login_required
def get_sub_user_bank_details_for_main_user(sub_user_id):
    """Get sub user's bank account details for main user approval"""
    try:
        print(f"Getting bank details for sub_user_id: {sub_user_id}")
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        print(f"Current user_id: {user_id}")
        
        # Verify that this sub user belongs to the main user
        cursor.execute("""
            SELECT su.id, su.sub_user_id, CONCAT(su.first_name, ' ', su.last_name) as sub_user_name
            FROM sub_users su
            WHERE su.sub_user_id = %s AND su.created_by = %s
        """, (sub_user_id, user_id))
        
        sub_user = cursor.fetchone()
        print(f"Sub user found: {sub_user}")
        if not sub_user:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Sub user not found or access denied'}), 404
        
        # Get sub user's bank account details
        cursor.execute("""
            SELECT bank_name, account_number, ifsc_code, account_holder_name, upi_id, phone_number, notes
            FROM sub_user_bank_accounts 
            WHERE sub_user_id = %s
        """, (sub_user['id'],))
        
        bank_account = cursor.fetchone()
        print(f"Bank account found: {bank_account}")
        cursor.close()
        connection.close()
        
        if bank_account:
            return jsonify({'success': True, 'bank_account': bank_account, 'sub_user': sub_user})
        else:
            return jsonify({'success': False, 'message': 'No bank account found for this sub user'}), 404
            
    except Exception as e:
        print(f"Get sub user bank details error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Sub User Notifications API Route
@app.route('/api/sub-user/notifications', methods=['GET'])
def get_sub_user_notifications():
    """Get recent notifications for sub user (approved/rejected requests)"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get recent approved/rejected requests (last 24 hours)
        cursor.execute("""
            SELECT 
                id,
                request_type,
                status,
                created_at,
                updated_at,
                notes,
                JSON_EXTRACT(request_data, '$.title') as title,
                JSON_EXTRACT(request_data, '$.amount') as amount
            FROM sub_user_requests 
            WHERE sub_user_id = %s 
            AND status IN ('approved', 'rejected')
            AND updated_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            ORDER BY updated_at DESC
            LIMIT 10
        """, (sub_user_id,))
        
        notifications = cursor.fetchall()
        
        # Format notifications
        formatted_notifications = []
        for notif in notifications:
            if notif['status'] == 'approved':
                message = f"Your {notif['request_type']} request '{notif['title']}' (₹{notif['amount']}) has been approved!"
                type = 'success'
            else:  # rejected
                message = f"Your {notif['request_type']} request '{notif['title']}' (₹{notif['amount']}) has been rejected."
                type = 'warning'
                if notif['notes']:
                    message += f" Reason: {notif['notes']}"
            
            formatted_notifications.append({
                'id': notif['id'],
                'message': message,
                'type': type,
                'timestamp': notif['updated_at'],
                'request_type': notif['request_type'],
                'title': notif['title'],
                'amount': notif['amount']
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'notifications': formatted_notifications})
    except Exception as e:
        print(f"Sub user notifications error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Sub User Invoice Metrics API Route
@app.route('/api/sub-user/invoice-metrics')
def get_sub_user_invoice_metrics():
    """Get sub user invoice metrics for summary cards"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get total invoices and amounts by type
        cursor.execute("""
            SELECT 
                COUNT(*) as total_invoices,
                SUM(CASE WHEN JSON_EXTRACT(request_data, '$.invoice_type') = 'in' THEN 1 ELSE 0 END) as in_invoices,
                SUM(CASE WHEN JSON_EXTRACT(request_data, '$.invoice_type') = 'out' THEN 1 ELSE 0 END) as out_invoices,
                SUM(CASE WHEN JSON_EXTRACT(request_data, '$.invoice_type') = 'in' THEN JSON_EXTRACT(request_data, '$.total_amount') ELSE 0 END) as total_in_amount,
                SUM(CASE WHEN JSON_EXTRACT(request_data, '$.invoice_type') = 'out' THEN JSON_EXTRACT(request_data, '$.total_amount') ELSE 0 END) as total_out_amount
            FROM sub_user_requests 
            WHERE sub_user_id = %s AND request_type = 'invoice'
        """, (sub_user_id,))
        
        totals = cursor.fetchone()
        
        # Get paid invoices
        cursor.execute("""
            SELECT 
                COUNT(*) as paid_invoices,
                SUM(JSON_EXTRACT(request_data, '$.total_amount')) as paid_amount
            FROM sub_user_requests 
            WHERE sub_user_id = %s AND request_type = 'invoice' 
            AND JSON_EXTRACT(request_data, '$.status') = 'paid'
        """, (sub_user_id,))
        
        paid = cursor.fetchone()
        
        # Get pending invoices
        cursor.execute("""
            SELECT 
                COUNT(*) as pending_invoices,
                SUM(JSON_EXTRACT(request_data, '$.total_amount')) as pending_amount
            FROM sub_user_requests 
            WHERE sub_user_id = %s AND request_type = 'invoice' 
            AND JSON_EXTRACT(request_data, '$.status') IN ('draft', 'sent')
        """, (sub_user_id,))
        
        pending = cursor.fetchone()
        
        # Get overdue invoices
        cursor.execute("""
            SELECT 
                COUNT(*) as overdue_invoices,
                SUM(JSON_EXTRACT(request_data, '$.total_amount')) as overdue_amount
            FROM sub_user_requests 
            WHERE sub_user_id = %s AND request_type = 'invoice' 
            AND JSON_EXTRACT(request_data, '$.status') = 'overdue'
        """, (sub_user_id,))
        
        overdue = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        metrics = {
            'total_invoices': totals['total_invoices'] or 0,
            'total_in_amount': float(totals['total_in_amount'] or 0),
            'total_out_amount': float(totals['total_out_amount'] or 0),
            'paid_invoices': paid['paid_invoices'] or 0,
            'paid_amount': float(paid['paid_amount'] or 0),
            'pending_invoices': pending['pending_invoices'] or 0,
            'pending_amount': float(pending['pending_amount'] or 0),
            'overdue_invoices': overdue['overdue_invoices'] or 0,
            'overdue_amount': float(overdue['overdue_amount'] or 0)
        }
        
        return jsonify({'success': True, 'metrics': metrics})
        
    except Exception as e:
        print(f"Error getting invoice metrics: {e}")
        return jsonify({'success': False, 'message': 'Error loading metrics'}), 500

# Sub User Invoice Revenue API Route
@app.route('/api/sub-user/invoice-revenue')
def get_sub_user_invoice_revenue():
    """Get sub user invoice revenue (approved invoices)"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get approved invoice requests
        cursor.execute("""
            SELECT JSON_EXTRACT(request_data, '$.invoice_number') as invoice_number,
                   JSON_EXTRACT(request_data, '$.client_name') as client_name,
                   JSON_EXTRACT(request_data, '$.total_amount') as total_amount,
                   JSON_EXTRACT(request_data, '$.invoice_type') as invoice_type,
                   JSON_EXTRACT(request_data, '$.invoice_date') as invoice_date
            FROM sub_user_requests 
            WHERE sub_user_id = %s AND request_type = 'invoice' AND status = 'approved'
            ORDER BY created_at DESC
        """, (sub_user_id,))
        
        invoices = cursor.fetchall()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'invoices': invoices})
    except Exception as e:
        print(f"Invoice revenue error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Sub User Invoice Request API Routes
@app.route('/api/sub-user/invoice-requests', methods=['GET', 'POST'])
def handle_sub_user_invoice_requests():
    """Handle sub user invoice requests (GET and POST)"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    if request.method == 'GET':
        return get_sub_user_invoice_requests()
    elif request.method == 'POST':
        return create_sub_user_invoice_request()

def get_sub_user_invoice_requests():
    """Get sub user invoice requests"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get invoice requests for this sub user
        cursor.execute("""
            SELECT id, status, created_at, updated_at, notes,
                   JSON_EXTRACT(request_data, '$.invoice_number') as invoice_number,
                   JSON_EXTRACT(request_data, '$.client_name') as client_name,
                   JSON_EXTRACT(request_data, '$.client_email') as client_email,
                   JSON_EXTRACT(request_data, '$.total_amount') as total_amount,
                   JSON_EXTRACT(request_data, '$.tax_amount') as tax_amount,
                   JSON_EXTRACT(request_data, '$.invoice_type') as invoice_type,
                   JSON_EXTRACT(request_data, '$.invoice_date') as invoice_date,
                   JSON_EXTRACT(request_data, '$.due_date') as due_date,
                   JSON_EXTRACT(request_data, '$.description') as description
            FROM sub_user_requests 
            WHERE sub_user_id = %s AND request_type = 'invoice'
            ORDER BY created_at DESC
        """, (sub_user_id,))
        
        invoices = cursor.fetchall()
        
        # Convert date objects to strings
        for invoice in invoices:
            if invoice['invoice_date']:
                invoice['invoice_date'] = invoice['invoice_date'].isoformat()
            if invoice['due_date']:
                invoice['due_date'] = invoice['due_date'].isoformat()
            if invoice['created_at']:
                invoice['created_at'] = invoice['created_at'].isoformat()
            if invoice['updated_at']:
                invoice['updated_at'] = invoice['updated_at'].isoformat()
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'invoices': invoices})
        
    except Exception as e:
        print(f"Error getting sub user invoice requests: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

def create_sub_user_invoice_request():
    """Create a new sub user invoice request"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['invoice_type', 'client_name', 'invoice_number', 'invoice_date', 'total_amount']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Generate unique ID
        unique_id = generate_unique_id('INV')
        
        # Prepare request data
        request_data = {
            'invoice_type': data['invoice_type'],
            'client_name': data['client_name'],
            'client_email': data.get('client_email', ''),
            'client_phone': data.get('client_phone', ''),
            'invoice_number': data['invoice_number'],
            'invoice_date': data['invoice_date'],
            'due_date': data.get('due_date', ''),
            'total_amount': float(data['total_amount']),
            'tax_amount': float(data.get('tax_amount', 0)),
            'status': data.get('status', 'draft'),
            'description': data.get('description', '')
        }
        
        # Insert invoice request
        cursor.execute("""
            INSERT INTO sub_user_requests (
                sub_user_id, request_type, unique_id, status, request_data, created_at, updated_at
            ) VALUES (
                %s, 'invoice', %s, 'pending', %s, NOW(), NOW()
            )
        """, (sub_user_id, unique_id, json.dumps(request_data)))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Invoice request created successfully', 'unique_id': unique_id})
        
    except Exception as e:
        print(f"Error creating invoice request: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/invoice-requests/<int:invoice_id>', methods=['GET'])
def get_sub_user_invoice_request(invoice_id):
    """Get specific sub user invoice request"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get specific invoice request
        cursor.execute("""
            SELECT id, status, created_at, updated_at, notes,
                   JSON_EXTRACT(request_data, '$.invoice_number') as invoice_number,
                   JSON_EXTRACT(request_data, '$.client_name') as client_name,
                   JSON_EXTRACT(request_data, '$.client_email') as client_email,
                   JSON_EXTRACT(request_data, '$.total_amount') as total_amount,
                   JSON_EXTRACT(request_data, '$.tax_amount') as tax_amount,
                   JSON_EXTRACT(request_data, '$.invoice_type') as invoice_type,
                   JSON_EXTRACT(request_data, '$.invoice_date') as invoice_date,
                   JSON_EXTRACT(request_data, '$.due_date') as due_date,
                   JSON_EXTRACT(request_data, '$.description') as description
            FROM sub_user_requests 
            WHERE id = %s AND sub_user_id = %s AND request_type = 'invoice'
        """, (invoice_id, sub_user_id))
        
        invoice = cursor.fetchone()
        
        if not invoice:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Invoice not found'}), 404
        
        # Convert date objects to strings
        if invoice['invoice_date']:
            invoice['invoice_date'] = invoice['invoice_date'].isoformat()
        if invoice['due_date']:
            invoice['due_date'] = invoice['due_date'].isoformat()
        if invoice['created_at']:
            invoice['created_at'] = invoice['created_at'].isoformat()
        if invoice['updated_at']:
            invoice['updated_at'] = invoice['updated_at'].isoformat()
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'invoice': invoice})
        
    except Exception as e:
        print(f"Error getting sub user invoice request: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/invoice-requests/<int:invoice_id>', methods=['DELETE'])
def delete_sub_user_invoice_request(invoice_id):
    """Delete sub user invoice request"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        sub_user_id = session['sub_user_id']
        
        # Delete the invoice request
        cursor.execute("""
            DELETE FROM sub_user_requests 
            WHERE id = %s AND sub_user_id = %s AND request_type = 'invoice'
        """, (invoice_id, sub_user_id))
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Invoice not found'}), 404
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Invoice deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting sub user invoice request: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/invoice-requests/bulk-delete', methods=['POST'])
def bulk_delete_sub_user_invoice_requests():
    """Bulk delete sub user invoice requests"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        invoice_ids = data.get('invoice_ids', [])
        
        if not invoice_ids:
            return jsonify({'success': False, 'message': 'No invoice IDs provided'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        sub_user_id = session['sub_user_id']
        
        # Create placeholders for the IN clause
        placeholders = ','.join(['%s'] * len(invoice_ids))
        
        # Delete all selected invoice requests
        cursor.execute(f"""
            DELETE FROM sub_user_requests 
            WHERE id IN ({placeholders}) AND sub_user_id = %s AND request_type = 'invoice'
        """, invoice_ids + [sub_user_id])
        
        deleted_count = cursor.rowcount
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True, 
            'message': f'Successfully deleted {deleted_count} invoice request(s)'
        })
        
    except Exception as e:
        print(f"Error bulk deleting sub user invoice requests: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/invoice-requests/export', methods=['POST'])
def export_sub_user_invoice_requests():
    """Export selected sub user invoice requests as PDF"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        invoice_ids = data.get('invoice_ids', [])
        
        if not invoice_ids:
            return jsonify({'success': False, 'message': 'No invoice IDs provided'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Create placeholders for the IN clause
        placeholders = ','.join(['%s'] * len(invoice_ids))
        
        # Get selected invoice requests
        cursor.execute(f"""
            SELECT id, status, created_at, notes,
                   JSON_EXTRACT(request_data, '$.invoice_number') as invoice_number,
                   JSON_EXTRACT(request_data, '$.client_name') as client_name,
                   JSON_EXTRACT(request_data, '$.client_email') as client_email,
                   JSON_EXTRACT(request_data, '$.total_amount') as total_amount,
                   JSON_EXTRACT(request_data, '$.tax_amount') as tax_amount,
                   JSON_EXTRACT(request_data, '$.invoice_type') as invoice_type,
                   JSON_EXTRACT(request_data, '$.invoice_date') as invoice_date,
                   JSON_EXTRACT(request_data, '$.due_date') as due_date,
                   JSON_EXTRACT(request_data, '$.description') as description
            FROM sub_user_requests 
            WHERE id IN ({placeholders}) AND sub_user_id = %s AND request_type = 'invoice'
            ORDER BY created_at DESC
        """, invoice_ids + [sub_user_id])
        
        invoices = cursor.fetchall()
        
        if not invoices:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'No invoices found'}), 404
        
        cursor.close()
        connection.close()
        
        # Generate PDF using ReportLab
        try:
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
            import io
            
            # Create PDF in memory
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=(8.5*inch, 11*inch))
            
            # Get styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.darkblue
            )
            
            # Build PDF content
            story = []
            
            # Title
            story.append(Paragraph("Sub-User Invoice Requests Export", title_style))
            story.append(Spacer(1, 20))
            
            # Export info
            export_info = f"""
            <b>Export Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>
            <b>Total Invoices:</b> {len(invoices)}<br/>
            <b>Sub-User ID:</b> {session.get('sub_user_id_display', 'N/A')}<br/>
            <b>Sub-User Name:</b> {session.get('sub_user_name', 'N/A')}
            """
            story.append(Paragraph(export_info, styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Create table data
            table_data = [['ID', 'Invoice #', 'Client', 'Amount', 'Type', 'Status', 'Date']]
            
            for invoice in invoices:
                table_data.append([
                    str(invoice['id']),
                    invoice['invoice_number'] or '-',
                    (invoice['client_name'] or '-')[:20] + ('...' if len(invoice['client_name'] or '') > 20 else ''),
                    f"₹{float(invoice['total_amount']):,.2f}",
                    'IN' if invoice['invoice_type'] == 'in' else 'OUT',
                    invoice['status'] or 'Pending',
                    invoice['invoice_date'].strftime('%Y-%m-%d') if invoice['invoice_date'] else '-'
                ])
            
            # Create table
            table = Table(table_data, colWidths=[0.5*inch, 1*inch, 1.5*inch, 1*inch, 0.5*inch, 0.8*inch, 1*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(table)
            
            # Build PDF
            doc.build(story)
            
            # Get PDF content
            pdf_content = buffer.getvalue()
            buffer.close()
            
            if not pdf_content:
                return jsonify({'success': False, 'message': 'Failed to generate PDF content'}), 500
            
            # Return PDF as response
            response = make_response(pdf_content)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=sub_user_invoices_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            
            return response
            
        except ImportError:
            return jsonify({'success': False, 'message': 'ReportLab library not available for PDF generation'}), 500
        except Exception as pdf_error:
            print(f"Error generating PDF: {pdf_error}")
            return jsonify({'success': False, 'message': f'Error generating PDF: {str(pdf_error)}'}), 500
        
    except Exception as e:
        print(f"Error exporting sub user invoice requests: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/invoice-requests/<int:invoice_id>/pdf')
def generate_sub_user_invoice_pdf(invoice_id):
    """Generate PDF for a specific sub user invoice request"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get specific invoice request
        cursor.execute("""
            SELECT id, status, created_at, notes,
                   JSON_EXTRACT(request_data, '$.invoice_number') as invoice_number,
                   JSON_EXTRACT(request_data, '$.client_name') as client_name,
                   JSON_EXTRACT(request_data, '$.client_email') as client_email,
                   JSON_EXTRACT(request_data, '$.total_amount') as total_amount,
                   JSON_EXTRACT(request_data, '$.tax_amount') as tax_amount,
                   JSON_EXTRACT(request_data, '$.invoice_type') as invoice_type,
                   JSON_EXTRACT(request_data, '$.invoice_date') as invoice_date,
                   JSON_EXTRACT(request_data, '$.due_date') as due_date,
                   JSON_EXTRACT(request_data, '$.description') as description
            FROM sub_user_requests 
            WHERE id = %s AND sub_user_id = %s AND request_type = 'invoice'
        """, (invoice_id, sub_user_id))
        
        invoice = cursor.fetchone()
        
        if not invoice:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Invoice not found'}), 404
        
        cursor.close()
        connection.close()
        
        # Generate PDF using the same template as main user
        try:
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
            import io
            
            # Create PDF in memory
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=(8.5*inch, 11*inch))
            
            # Get styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.darkblue
            )
            
            # Build PDF content
            story = []
            
            # Title
            story.append(Paragraph("INVOICE", title_style))
            story.append(Spacer(1, 20))
            
            # Invoice details
            invoice_details = f"""
            <b>Invoice Number:</b> {invoice['invoice_number'] or 'N/A'}<br/>
            <b>Date:</b> {invoice['invoice_date'].strftime('%Y-%m-%d') if invoice['invoice_date'] else 'N/A'}<br/>
            <b>Due Date:</b> {invoice['due_date'].strftime('%Y-%m-%d') if invoice['due_date'] else 'N/A'}<br/>
            <b>Status:</b> {invoice['status'] or 'Pending'}<br/>
            <b>Type:</b> {'Invoice IN' if invoice['invoice_type'] == 'in' else 'Invoice OUT'}
            """
            story.append(Paragraph(invoice_details, styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Client details
            client_details = f"""
            <b>Bill To:</b><br/>
            {invoice['client_name'] or 'N/A'}<br/>
            {invoice['client_email'] or 'N/A'}
            """
            story.append(Paragraph(client_details, styles['Normal']))
            story.append(Spacer(1, 20))
            
            # Description
            if invoice['description']:
                story.append(Paragraph(f"<b>Description:</b><br/>{invoice['description']}", styles['Normal']))
                story.append(Spacer(1, 20))
            
            # Amount table
            amount_data = [
                ['Item', 'Amount'],
                ['Subtotal', f"₹{float(invoice['total_amount']):,.2f}"],
                ['Tax', f"₹{float(invoice['tax_amount'] or 0):,.2f}"],
                ['Total', f"₹{float(invoice['total_amount']):,.2f}"]
            ]
            
            amount_table = Table(amount_data, colWidths=[3*inch, 1.5*inch])
            amount_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(amount_table)
            
            # Build PDF
            doc.build(story)
            
            # Get PDF content
            pdf_content = buffer.getvalue()
            buffer.close()
            
            if not pdf_content:
                return jsonify({'success': False, 'message': 'Failed to generate PDF content'}), 500
            
            # Return PDF as response
            response = make_response(pdf_content)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'attachment; filename=invoice_{invoice_id}.pdf'
            
            return response
            
        except ImportError:
            return jsonify({'success': False, 'message': 'ReportLab library not available for PDF generation'}), 500
        except Exception as pdf_error:
            print(f"Error generating PDF: {pdf_error}")
            return jsonify({'success': False, 'message': f'Error generating PDF: {str(pdf_error)}'}), 500
        
    except Exception as e:
        print(f"Error generating sub user invoice PDF: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Sub User Request Management API Routes
@app.route('/api/sub-user-requests/pending', methods=['GET'])
@login_required
def get_pending_sub_user_requests():
    """Get pending sub user requests for the current user"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        cursor.execute("""
            SELECT sur.id, sur.request_type, sur.status, sur.created_at,
                   JSON_EXTRACT(sur.request_data, '$.title') as title,
                   JSON_EXTRACT(sur.request_data, '$.amount') as amount,
                   sur.request_data,
                   su.sub_user_id, CONCAT(su.first_name, ' ', su.last_name) as sub_user_name
            FROM sub_user_requests sur
            JOIN sub_users su ON sur.sub_user_id = su.id
            WHERE su.created_by = %s AND sur.status = 'pending'
            ORDER BY sur.created_at DESC
        """, (user_id,))
        
        requests = cursor.fetchall()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'requests': requests})
    except Exception as e:
        print(f"Pending requests error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/pending-requests/<int:request_id>', methods=['GET'])
@login_required
def get_pending_request_details(request_id):
    """Get details of a specific pending request (expense/transaction or invoice download)"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        # First try to find in sub_user_requests (expense/transaction requests)
        cursor.execute("""
            SELECT sur.id, sur.request_type, sur.status, sur.created_at,
                   JSON_EXTRACT(sur.request_data, '$.title') as title,
                   JSON_EXTRACT(sur.request_data, '$.amount') as amount,
                   sur.request_data,
                   su.sub_user_id, CONCAT(su.first_name, ' ', su.last_name) as sub_user_name,
                   'expense' as request_category
            FROM sub_user_requests sur
            JOIN sub_users su ON sur.sub_user_id = su.id
            WHERE sur.id = %s AND su.created_by = %s
        """, (request_id, user_id))
        
        request_data = cursor.fetchone()
        
        # If not found in sub_user_requests, try invoice download approvals
        if not request_data:
            cursor.execute("""
                SELECT sda.id, sda.invoice_id, sda.status, sda.requested_at as created_at,
                       i.invoice_number, i.client_name, i.total_amount, i.invoice_type,
                       su.sub_user_id, CONCAT(su.first_name, ' ', su.last_name) as sub_user_name,
                       'invoice_download' as request_category,
                       'invoice_download' as request_type,
                       CONCAT('Download: ', i.invoice_number) as title,
                       i.total_amount as amount
                FROM sub_user_download_approvals sda
                JOIN invoices i ON sda.invoice_id = i.id
                JOIN sub_users su ON sda.sub_user_id = su.id
                WHERE sda.id = %s AND i.user_id = %s
            """, (request_id, user_id))
            
            request_data = cursor.fetchone()
            
            # For invoice download requests, create a fake request_data JSON
            if request_data:
                request_data['request_data'] = json.dumps({
                    'title': f"Download: {request_data['invoice_number']}",
                    'amount': float(request_data['total_amount']),
                    'invoice_id': request_data['invoice_id'],
                    'invoice_type': request_data['invoice_type'],
                    'client_name': request_data['client_name']
                })
        
        cursor.close()
        connection.close()
        
        if not request_data:
            return jsonify({'success': False, 'message': 'Request not found'}), 404
        
        # Convert datetime to string for JSON serialization
        if request_data.get('created_at'):
            request_data['created_at'] = request_data['created_at'].isoformat()
        
        return jsonify({'success': True, 'request': request_data})
        
    except Exception as e:
        print(f"Error getting request details for request_id {request_id}: {e}")
        print(f"User ID: {user_id}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/expense-requests/<int:request_id>/approve-with-payment', methods=['PUT'])
@login_required
def approve_sub_user_expense_with_payment(request_id):
    """Approve a sub user expense request with bank/cash selection and deduction"""
    try:
        data = request.get_json()
        bank_account_id = data.get('bank_account_id')  # Can be None for cash
        payment_method = data.get('payment_method', 'cash')  # 'bank' or 'cash'
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        # Start transaction
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        print(f"Starting expense approval process for request {request_id} by user {user_id}")
        print(f"Payment method: {payment_method}, Bank account ID: {bank_account_id}")
        
        # Get expense request details
        cursor.execute("""
            SELECT sur.*, su.sub_user_id, CONCAT(su.first_name, ' ', su.last_name) as sub_user_name, su.id as actual_sub_user_id
            FROM sub_user_requests sur
            JOIN sub_users su ON sur.sub_user_id = su.id
            WHERE sur.id = %s AND su.created_by = %s AND sur.status = 'pending' AND sur.request_type = 'expense'
        """, (request_id, user_id))
        
        request_data = cursor.fetchone()
        if not request_data:
            connection.rollback()
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Expense request not found or already processed'}), 404
        
        request_json = json.loads(request_data['request_data'])
        expense_amount = float(request_json['amount'])
        
        # Validate bank account if payment method is bank
        if payment_method == 'bank':
            if not bank_account_id:
                connection.rollback()
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': 'Bank account selection required for bank payment'}), 400
                
            # Verify bank account belongs to user and has sufficient balance
            cursor.execute("""
                SELECT id, bank_name, current_balance
                FROM bank_accounts
                WHERE id = %s AND user_id = %s
            """, (bank_account_id, user_id))
            
            bank_account = cursor.fetchone()
            if not bank_account:
                connection.rollback()
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': 'Invalid bank account selected'}), 400
            
            if float(bank_account['current_balance']) < expense_amount:
                connection.rollback()
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': f'Insufficient balance in {bank_account["bank_name"]}. Available: ₹{bank_account["current_balance"]}, Required: ₹{expense_amount}'}), 400
        
        else:  # Cash payment
            # Check cash balance
            cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (user_id,))
            user_data = cursor.fetchone()
            
            if not user_data or float(user_data['cash_balance']) < expense_amount:
                available_cash = user_data['cash_balance'] if user_data else 0
                connection.rollback()
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': f'Insufficient cash balance. Available: ₹{available_cash}, Required: ₹{expense_amount}'}), 400
        
        # Deduct amount from selected payment method
        if payment_method == 'bank' and bank_account_id:
            cursor.execute("""
                UPDATE bank_accounts 
                SET current_balance = current_balance - %s 
                WHERE id = %s AND user_id = %s
            """, (expense_amount, bank_account_id, user_id))
            print(f"Deducted ₹{expense_amount} from bank account {bank_account_id}")
        else:
            cursor.execute("""
                UPDATE users 
                SET cash_balance = cash_balance - %s 
                WHERE id = %s
            """, (expense_amount, user_id))
            print(f"Deducted ₹{expense_amount} from cash balance")
        
        # Update request status to approved and record approval details
        cursor.execute("""
            UPDATE sub_user_requests 
            SET status = 'approved', 
                reviewed_by = %s, 
                reviewed_at = NOW(),
                request_data = JSON_SET(request_data, '$.approved_payment_method', %s, '$.approved_bank_account_id', %s)
            WHERE id = %s
        """, (user_id, payment_method, bank_account_id, request_id))
        
        # Generate or propagate unique_id across request → expense → transaction
        request_json = json.loads(request_data['request_data'])
        unique_id = request_json.get('unique_id') or generate_unique_id('EXP')
        
        # Prepare description with bank account information
        description = request_json.get('description', '')
        bank_info = ""
        
        # Add bank account information to description
        if request_json.get('bank_account_type') == 'own':
            bank_info = "\n\nBank Account: Sub User's Own Account"
        elif request_json.get('bank_account_type') == 'vendor' and request_json.get('vendor_bank_details'):
            vendor_details = request_json['vendor_bank_details']
            bank_info = f"\n\nVendor Bank Details:\n"
            bank_info += f"Bank: {vendor_details.get('bank_name', 'N/A')}\n"
            bank_info += f"Account Number: {vendor_details.get('account_number', 'N/A')}\n"
            bank_info += f"IFSC Code: {vendor_details.get('ifsc_code', 'N/A')}\n"
            bank_info += f"Account Holder: {vendor_details.get('account_holder_name', 'N/A')}"
            if vendor_details.get('upi_id'):
                bank_info += f"\nUPI ID: {vendor_details.get('upi_id')}"
            if vendor_details.get('phone_number'):
                bank_info += f"\nPhone: {vendor_details.get('phone_number')}"
        
        full_description = description + bank_info
        
        # Add expense to main user's account
        cursor.execute("""
            INSERT INTO expenses (user_id, unique_id, title, purpose, description, amount, category, expense_date, payment_method, expense_type, created_by_sub_user)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            unique_id,
            f"{request_json['title']} (by {request_data['sub_user_name']})",
            request_json['title'],
            full_description,
            expense_amount,
            request_json.get('category', 'General'),
            request_json['expense_date'],
            request_json['payment_method'],
            'completed',
            request_data['actual_sub_user_id']
        ))
        
        # Create transaction record for the deduction
        transaction_unique_id = unique_id
        
        # Determine the payment method display name
        if payment_method == 'bank' and bank_account_id:
            # Get bank name for display
            cursor.execute("SELECT bank_name FROM bank_accounts WHERE id = %s", (bank_account_id,))
            bank_result = cursor.fetchone()
            transaction_payment_method = bank_result['bank_name'] if bank_result else 'Bank Account'
        else:
            transaction_payment_method = 'CASH'
        
        cursor.execute("""
            INSERT INTO transactions (user_id, unique_id, title, description, amount, transaction_type, transaction_date, payment_method, created_by_sub_user)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            transaction_unique_id,
            f"Expense: {request_json['title']} (by {request_data['sub_user_name']})",
            f"Approved expense payment - {full_description}",
            expense_amount,
            'debit',
            request_json['expense_date'],
            transaction_payment_method,
            request_data['actual_sub_user_id']
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': f'Expense "{request_json["title"]}" approved and payment processed successfully',
            'expense_title': request_json['title'],
            'amount': expense_amount,
            'payment_method': transaction_payment_method
        })
        
    except Exception as e:
        if connection:
            connection.rollback()
            connection.close()
        print(f"Error approving expense with payment: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user-requests/<int:request_id>/approve', methods=['PUT'])
@login_required
def approve_sub_user_request(request_id):
    """Approve a sub user request"""
    connection = None
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        # Start transaction
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        print(f"Starting approval process for request {request_id} by user {user_id}")
        
        # Set a timeout for the database operations
        cursor.execute("SET SESSION innodb_lock_wait_timeout = 10")
        
        # Get request details
        cursor.execute("""
            SELECT sur.*, su.sub_user_id, CONCAT(su.first_name, ' ', su.last_name) as sub_user_name, su.id as actual_sub_user_id
            FROM sub_user_requests sur
            JOIN sub_users su ON sur.sub_user_id = su.id
            WHERE sur.id = %s AND su.created_by = %s AND sur.status = 'pending'
        """, (request_id, user_id))
        
        request_data = cursor.fetchone()
        if not request_data:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Request not found or already processed'}), 404
        
        # Update request status
        cursor.execute("""
            UPDATE sub_user_requests 
            SET status = 'approved', reviewed_by = %s, reviewed_at = NOW()
            WHERE id = %s
        """, (user_id, request_id))
        
        # Add the approved request to main user's account
        request_json = json.loads(request_data['request_data'])
        
        # Generate unique ID for the transaction/expense
        unique_id = generate_unique_id('SUB')
        
        if request_data['request_type'] == 'expense':
            # Prepare description with bank account information
            description = request_json['description']
            bank_info = ""
            
            # Add bank account information to description
            if request_json.get('bank_account_type') == 'own':
                bank_info = "\n\nBank Account: Sub User's Own Account"
            elif request_json.get('bank_account_type') == 'vendor' and request_json.get('vendor_bank_details'):
                vendor_details = request_json['vendor_bank_details']
                bank_info = f"\n\nVendor Bank Details:\n"
                bank_info += f"Bank: {vendor_details.get('bank_name', 'N/A')}\n"
                bank_info += f"Account Number: {vendor_details.get('account_number', 'N/A')}\n"
                bank_info += f"IFSC Code: {vendor_details.get('ifsc_code', 'N/A')}\n"
                bank_info += f"Account Holder: {vendor_details.get('account_holder_name', 'N/A')}"
                if vendor_details.get('upi_id'):
                    bank_info += f"\nUPI ID: {vendor_details.get('upi_id')}"
                if vendor_details.get('phone_number'):
                    bank_info += f"\nPhone: {vendor_details.get('phone_number')}"
            
            full_description = description + bank_info
            
            # Add expense to main user's account
            try:
                cursor.execute("""
                    INSERT INTO expenses (user_id, unique_id, title, purpose, description, amount, category, expense_date, payment_method, expense_type, created_by_sub_user)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    unique_id,
                    f"{request_json['title']} (by {request_data['sub_user_name']})",
                    request_json['title'],  # Use title as purpose
                    full_description,
                    request_json['amount'],
                    request_json['category'],
                    request_json['expense_date'],
                    request_json['payment_method'],
                    'completed',  # Set as completed since it's approved
                    request_data['actual_sub_user_id']
                ))
                
                # Also add as a transaction (debit) so it appears in transaction history
                cursor.execute("""
                    INSERT INTO transactions (user_id, unique_id, title, description, amount, transaction_type, transaction_date, payment_method, created_by_sub_user)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    unique_id,
                    f"{request_json['title']} (by {request_data['sub_user_name']})",
                    f"Expense: {full_description}",
                    request_json['amount'],
                    'debit',  # Expenses are debit transactions
                    request_json['expense_date'],
                    request_json['payment_method'],
                    request_data['actual_sub_user_id']
                ))
                
                # Update balance based on payment method
                print(f"Updating balance: deducting {request_json['amount']} for user {user_id}")
                try:
                    balance_cursor = connection.cursor()
                    payment_method = request_json.get('payment_method', 'cash')
                    
                    # Get current balance before update for debugging
                    if payment_method == 'cash':
                        balance_cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (user_id,))
                        current_balance = balance_cursor.fetchone()
                        if current_balance:
                            print(f"Current cash balance before deduction: ₹{current_balance[0]}")
                    
                    if payment_method == 'online':
                        # For online payments, try to deduct from bank account first
                        # Get the first available bank account for the main user
                        balance_cursor.execute("""
                            SELECT id, current_balance FROM bank_accounts 
                            WHERE user_id = %s 
                            ORDER BY is_default DESC, id LIMIT 1
                        """, (user_id,))
                        
                        bank_account = balance_cursor.fetchone()
                        if bank_account:
                            print(f"Current bank balance before deduction: ₹{bank_account[1]}")
                            # Deduct from bank account
                            balance_cursor.execute("""
                                UPDATE bank_accounts 
                                SET current_balance = current_balance - %s 
                                WHERE id = %s AND user_id = %s
                            """, (request_json['amount'], bank_account[0], user_id))
                            print(f"Deducted ₹{request_json['amount']} from bank account {bank_account[0]} for user {user_id}")
                            
                            # Verify the update
                            balance_cursor.execute("SELECT current_balance FROM bank_accounts WHERE id = %s", (bank_account[0],))
                            new_balance = balance_cursor.fetchone()
                            if new_balance:
                                print(f"New bank balance after deduction: ₹{new_balance[0]}")
                        else:
                            # No bank account found, deduct from cash balance
                            balance_cursor.execute("""
                                UPDATE users 
                                SET cash_balance = cash_balance - %s 
                                WHERE id = %s
                            """, (request_json['amount'], user_id))
                            print(f"No bank account found, deducted ₹{request_json['amount']} from cash balance for user {user_id}")
                    else:
                        # For cash payments, deduct from cash balance
                        balance_cursor.execute("""
                            UPDATE users 
                            SET cash_balance = cash_balance - %s 
                            WHERE id = %s
                        """, (request_json['amount'], user_id))
                        print(f"Deducted ₹{request_json['amount']} from cash balance for user {user_id}")
                        
                        # Verify the update
                        balance_cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (user_id,))
                        new_balance = balance_cursor.fetchone()
                        if new_balance:
                            print(f"New cash balance after deduction: ₹{new_balance[0]}")
                    
                    balance_cursor.close()
                except Exception as balance_error:
                    print(f"Error updating balance: {balance_error}")
                    # Continue with the approval even if balance update fails
                
            except Exception as e:
                print(f"Error inserting expense with sub_user: {e}")
                # Fallback without created_by_sub_user column
                cursor.execute("""
                    INSERT INTO expenses (user_id, unique_id, title, purpose, description, amount, category, expense_date, payment_method, expense_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    unique_id,
                    f"{request_json['title']} (by {request_data['sub_user_name']})",
                    request_json['title'],  # Use title as purpose
                    full_description,
                    request_json['amount'],
                    request_json['category'],
                    request_json['expense_date'],
                    request_json['payment_method'],
                    'completed'  # Set as completed since it's approved
                ))
                
                # Also add as a transaction (debit) so it appears in transaction history
                cursor.execute("""
                    INSERT INTO transactions (user_id, unique_id, title, description, amount, transaction_type, transaction_date, payment_method)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    unique_id,
                    f"{request_json['title']} (by {request_data['sub_user_name']})",
                    f"Expense: {full_description}",
                    request_json['amount'],
                    'debit',  # Expenses are debit transactions
                    request_json['expense_date'],
                    request_json['payment_method']
                ))
                
                # Update balance based on payment method (fallback)
                print(f"Updating balance (fallback): deducting {request_json['amount']} for user {user_id}")
                try:
                    balance_cursor = connection.cursor()
                    payment_method = request_json.get('payment_method', 'cash')
                    
                    # Get current balance before update for debugging
                    if payment_method == 'cash':
                        balance_cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (user_id,))
                        current_balance = balance_cursor.fetchone()
                        if current_balance:
                            print(f"Current cash balance before deduction (fallback): ₹{current_balance[0]}")
                    
                    if payment_method == 'online':
                        # For online payments, try to deduct from bank account first
                        balance_cursor.execute("""
                            SELECT id, current_balance FROM bank_accounts 
                            WHERE user_id = %s 
                            ORDER BY is_default DESC, id LIMIT 1
                        """, (user_id,))
                        
                        bank_account = balance_cursor.fetchone()
                        if bank_account:
                            print(f"Current bank balance before deduction (fallback): ₹{bank_account[1]}")
                            # Deduct from bank account
                            balance_cursor.execute("""
                                UPDATE bank_accounts 
                                SET current_balance = current_balance - %s 
                                WHERE id = %s AND user_id = %s
                            """, (request_json['amount'], bank_account[0], user_id))
                            print(f"Deducted ₹{request_json['amount']} from bank account {bank_account[0]} for user {user_id} (fallback)")
                            
                            # Verify the update
                            balance_cursor.execute("SELECT current_balance FROM bank_accounts WHERE id = %s", (bank_account[0],))
                            new_balance = balance_cursor.fetchone()
                            if new_balance:
                                print(f"New bank balance after deduction (fallback): ₹{new_balance[0]}")
                        else:
                            # No bank account found, deduct from cash balance
                            balance_cursor.execute("""
                                UPDATE users 
                                SET cash_balance = cash_balance - %s 
                                WHERE id = %s
                            """, (request_json['amount'], user_id))
                            print(f"No bank account found, deducted ₹{request_json['amount']} from cash balance for user {user_id} (fallback)")
                    else:
                        # For cash payments, deduct from cash balance
                        balance_cursor.execute("""
                            UPDATE users 
                            SET cash_balance = cash_balance - %s 
                            WHERE id = %s
                        """, (request_json['amount'], user_id))
                        print(f"Deducted ₹{request_json['amount']} from cash balance for user {user_id} (fallback)")
                        
                        # Verify the update
                        balance_cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (user_id,))
                        new_balance = balance_cursor.fetchone()
                        if new_balance:
                            print(f"New cash balance after deduction (fallback): ₹{new_balance[0]}")
                    
                    balance_cursor.close()
                except Exception as balance_error:
                    print(f"Error updating balance: {balance_error}")
                    # Continue with the approval even if balance update fails
            
        elif request_data['request_type'] == 'transaction':
            # Add transaction to main user's account
            try:
                cursor.execute("""
                    INSERT INTO transactions (user_id, unique_id, title, description, amount, transaction_type, transaction_date, payment_method, created_by_sub_user)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    unique_id,
                    f"{request_json['title']} (by {request_data['sub_user_name']})",
                    request_json['description'],
                    request_json['amount'],
                    request_json['transaction_type'],
                    request_json['transaction_date'],
                    request_json['payment_method'],
                    request_data['actual_sub_user_id']
                ))
                
                # Update cash balance based on transaction type (simplified approach)
                print(f"Updating cash balance for transaction: {request_json['transaction_type']} {request_json['amount']} for user {user_id}")
                try:
                    # Use the same connection but after the main transaction
                    balance_cursor = connection.cursor()
                    if request_json['transaction_type'] == 'credit':
                        balance_cursor.execute("""
                            UPDATE users 
                            SET cash_balance = cash_balance + %s 
                            WHERE id = %s
                        """, (request_json['amount'], user_id))
                        print(f"Added ₹{request_json['amount']} to cash balance for user {user_id}")
                    else:  # debit
                        balance_cursor.execute("""
                            UPDATE users 
                            SET cash_balance = cash_balance - %s 
                            WHERE id = %s
                        """, (request_json['amount'], user_id))
                        print(f"Deducted ₹{request_json['amount']} from cash balance for user {user_id}")
                    balance_cursor.close()
                except Exception as balance_error:
                    print(f"Error updating cash balance: {balance_error}")
                    # Continue with the approval even if balance update fails
                
            except Exception as e:
                # Fallback without created_by_sub_user column
                cursor.execute("""
                    INSERT INTO transactions (user_id, unique_id, title, description, amount, transaction_type, transaction_date, payment_method)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    unique_id,
                    f"{request_json['title']} (by {request_data['sub_user_name']})",
                    request_json['description'],
                    request_json['amount'],
                    request_json['transaction_type'],
                    request_json['transaction_date'],
                    request_json['payment_method']
                ))
                
                # Update cash balance based on transaction type (simplified approach)
                print(f"Updating cash balance for transaction (fallback): {request_json['transaction_type']} {request_json['amount']} for user {user_id}")
                try:
                    # Use the same connection but after the main transaction
                    balance_cursor = connection.cursor()
                    if request_json['transaction_type'] == 'credit':
                        balance_cursor.execute("""
                            UPDATE users 
                            SET cash_balance = cash_balance + %s 
                            WHERE id = %s
                        """, (request_json['amount'], user_id))
                        print(f"Added ₹{request_json['amount']} to cash balance for user {user_id}")
                    else:  # debit
                        balance_cursor.execute("""
                            UPDATE users 
                            SET cash_balance = cash_balance - %s 
                            WHERE id = %s
                        """, (request_json['amount'], user_id))
                        print(f"Deducted ₹{request_json['amount']} from cash balance for user {user_id}")
                    balance_cursor.close()
                except Exception as balance_error:
                    print(f"Error updating cash balance: {balance_error}")
                    # Continue with the approval even if balance update fails
        
        # Update the sub_user_requests table with the unique_id for tracking
        cursor.execute("""
            UPDATE sub_user_requests 
            SET status = 'approved', reviewed_by = %s, reviewed_at = NOW(), notes = %s
            WHERE id = %s
        """, (user_id, f"Approved - Unique ID: {unique_id}", request_id))
        
        print(f"Committing approval for request {request_id}")
        connection.commit()
        cursor.close()
        connection.close()
        
        print(f"Approval completed successfully for request {request_id}")
        return jsonify({'success': True, 'message': 'Request approved and added to your account'})
    except Exception as e:
        print(f"Approve request error: {e}")
        if connection:
            try:
                connection.rollback()
                cursor.close()
                connection.close()
            except:
                pass
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user-requests/<int:request_id>/reject', methods=['PUT'])
@login_required
def reject_sub_user_request(request_id):
    """Reject a sub user request"""
    try:
        data = request.get_json()
        reason = data.get('reason', '')
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor()
        user_id = session['user_id']
        
        # Check if request exists and belongs to user
        cursor.execute("""
            SELECT sur.id FROM sub_user_requests sur
            JOIN sub_users su ON sur.sub_user_id = su.id
            WHERE sur.id = %s AND su.created_by = %s AND sur.status = 'pending'
        """, (request_id, user_id))
        
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Request not found or already processed'}), 404
        
        # Update request status
        cursor.execute("""
            UPDATE sub_user_requests 
            SET status = 'rejected', reviewed_by = %s, reviewed_at = NOW(), notes = %s
            WHERE id = %s
        """, (user_id, reason, request_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Request rejected successfully'})
    except Exception as e:
        print(f"Reject request error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Enhanced Sub User Invoice Management API Routes
@app.route('/api/sub-user/invoices', methods=['GET'])
def get_sub_user_invoices():
    """Get sub user's invoices"""
    print(f"DEBUG: get_sub_user_invoices called, session keys: {list(session.keys())}")
    print(f"DEBUG: session data: {dict(session)}")
    
    if 'sub_user_id' not in session:
        print("DEBUG: sub_user_id not in session")
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            print("DEBUG: Database connection failed")
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        print(f"DEBUG: Fetching invoices for sub_user_id: {sub_user_id}")
        
        # Get all invoices for this sub user
        cursor.execute("""
            SELECT i.*, COALESCE(sda.status, 'not_requested') as download_status
            FROM invoices i
            LEFT JOIN sub_user_download_approvals sda ON i.id = sda.invoice_id AND sda.sub_user_id = %s
            WHERE i.created_by_sub_user = %s
            ORDER BY i.created_at DESC
        """, (sub_user_id, sub_user_id))
        
        invoices = cursor.fetchall()
        print(f"DEBUG: Found {len(invoices)} invoices for sub_user_id: {sub_user_id}")
        
        # Convert date objects to strings and add items
        for invoice in invoices:
            if invoice['invoice_date']:
                invoice['invoice_date'] = invoice['invoice_date'].strftime('%Y-%m-%d')
            if invoice['due_date']:
                invoice['due_date'] = invoice['due_date'].strftime('%Y-%m-%d')
            if invoice['created_at']:
                invoice['created_at'] = invoice['created_at'].isoformat()
            if invoice['updated_at']:
                invoice['updated_at'] = invoice['updated_at'].isoformat()
                
            # Get invoice items
            cursor.execute("""
                SELECT description, quantity, unit_price, total_price
                FROM invoice_items 
                WHERE invoice_id = %s
                ORDER BY id
            """, (invoice['id'],))
            invoice['items'] = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        print(f"DEBUG: Returning {len(invoices)} invoices")
        print(f"DEBUG: Response structure: {type(invoices)}")
        return jsonify(invoices)
        
    except Exception as e:
        print(f"Error getting sub user invoices: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/invoices', methods=['POST'])
def create_sub_user_invoice():
    """Create a new sub user invoice"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['invoice_type', 'client_name', 'invoice_date', 'total_amount', 'items']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get the main user ID who created this sub user
        cursor.execute("SELECT created_by FROM sub_users WHERE id = %s", (sub_user_id,))
        sub_user_record = cursor.fetchone()
        if not sub_user_record:
            return jsonify({'success': False, 'message': 'Sub user not found'}), 404
        
        main_user_id = sub_user_record['created_by']
        
        # Generate invoice number and unique ID
        invoice_number = generate_invoice_number(main_user_id, data.get('invoice_type', 'out'))
        unique_id = generate_unique_id('INV')
        
        # Set status - IN invoices are auto-approved, OUT invoices are pending
        invoice_status = 'approved' if data.get('invoice_type') == 'in' else 'pending'
        
        # Insert invoice with all the new fields
        cursor.execute("""
            INSERT INTO invoices (
                user_id, created_by_sub_user, unique_id, invoice_number, invoice_type,
                client_name, client_email, client_phone, client_address, client_state, client_pin, client_gstin, client_pan,
                billing_company_name, billing_address, billing_city, billing_state, billing_pin, gstin_number, pan_number,
                invoice_date, due_date, subtotal, cgst_rate, sgst_rate, igst_rate, 
                cgst_amount, sgst_amount, igst_amount, tax_amount, total_amount,
                payment_method, bank_account_type,
                status, notes, terms_conditions, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, NOW(), NOW()
            )
        """, (
            main_user_id, sub_user_id, unique_id, invoice_number, data.get('invoice_type', 'out'),
            data.get('client_name'), data.get('client_email'), data.get('client_phone'), data.get('client_address'),
            data.get('client_state'), data.get('client_pin'), data.get('client_gstin'), data.get('client_pan'),
            data.get('billing_company_name'), data.get('billing_address'), data.get('billing_city'), data.get('billing_state'), 
            data.get('billing_pin'), data.get('gstin_number'), data.get('pan_number'),
            data.get('invoice_date'), data.get('due_date'), data.get('subtotal', 0), 
            data.get('cgst_rate', 0), data.get('sgst_rate', 0), data.get('igst_rate', 18),
            data.get('cgst_amount', 0), data.get('sgst_amount', 0), data.get('igst_amount', 0), data.get('tax_amount', 0), data.get('total_amount'),
            data.get('payment_method', 'cash'), data.get('bank_account_type'),
            invoice_status, data.get('notes'), data.get('terms_conditions')
        ))
        
        invoice_id = cursor.lastrowid
        
        # Store vendor bank details if provided
        if data.get('bank_account_type') == 'vendor' and data.get('vendor_bank_details'):
            vendor_details = data['vendor_bank_details']
            try:
                cursor.execute("""
                    INSERT INTO vendor_bank_details (
                        invoice_id, bank_name, account_number, ifsc_code, 
                        account_holder_name, upi_id, phone_number
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    invoice_id,
                    vendor_details.get('bank_name'),
                    vendor_details.get('account_number'),
                    vendor_details.get('ifsc_code'),
                    vendor_details.get('account_holder_name'),
                    vendor_details.get('upi_id'),
                    vendor_details.get('phone_number')
                ))
                print(f"DEBUG: Stored vendor bank details for invoice {invoice_id}")
            except Exception as vendor_error:
                print(f"DEBUG: Error storing vendor bank details: {vendor_error}")
                # Continue without failing - vendor bank details are optional
        
        # Insert invoice items
        if data.get('items'):
            for item in data['items']:
                cursor.execute("""
                    INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, total_price)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    invoice_id, 
                    item.get('description', ''),
                    item.get('quantity', 0),
                    item.get('unit_price', 0),
                    item.get('total_price', 0)
                ))
        
        # For IN invoices, automatically add money to main user's default account
        if data.get('invoice_type') == 'in':
            try:
                print(f"Processing IN invoice - adding ₹{data.get('total_amount')} to main user {main_user_id} account")
                
                # Get main user's default bank account
                cursor.execute("""
                    SELECT id FROM bank_accounts 
                    WHERE user_id = %s
                    ORDER BY id LIMIT 1
                """, (main_user_id,))
                
                default_account = cursor.fetchone()
                bank_account_id = default_account['id'] if default_account else None
                
                # If no default account, get the first active account
                if not bank_account_id:
                    cursor.execute("""
                        SELECT id FROM bank_accounts 
                        WHERE user_id = %s
                        ORDER BY id LIMIT 1
                    """, (main_user_id,))
                    
                    first_account = cursor.fetchone()
                    bank_account_id = first_account['id'] if first_account else None
                
                invoice_amount = float(data.get('total_amount', 0))
                
                # Add money to bank account or cash balance
                if bank_account_id:
                    cursor.execute("""
                        UPDATE bank_accounts 
                        SET current_balance = current_balance + %s 
                        WHERE id = %s AND user_id = %s
                    """, (invoice_amount, bank_account_id, main_user_id))
                    print(f"Added ₹{invoice_amount} to bank account {bank_account_id}")
                else:
                    # No bank account found, add to cash balance
                    cursor.execute("""
                        UPDATE users 
                        SET cash_balance = cash_balance + %s 
                        WHERE id = %s
                    """, (invoice_amount, main_user_id))
                    print(f"Added ₹{invoice_amount} to cash balance for main user {main_user_id}")
                
                # Create a transaction record for the IN invoice
                transaction_unique_id = generate_unique_id('TXN')
                cursor.execute("""
                    INSERT INTO transactions (
                        user_id, unique_id, title, description, amount, 
                        transaction_type, transaction_date, payment_method, 
                        created_by_sub_user, invoice_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    main_user_id,
                    transaction_unique_id,
                    f"Income from Invoice {invoice_number}",
                    f"Sub-user IN invoice: {data.get('client_name')} - {invoice_number}",
                    invoice_amount,
                    'credit',  # IN invoices are credit transactions (money coming in)
                    data.get('invoice_date'),
                    'online',  # Default to online for IN invoices
                    sub_user_id,
                    invoice_id
                ))
                
                print(f"Created transaction record for IN invoice {invoice_number}")
                
            except Exception as e:
                print(f"Error adding money for IN invoice: {e}")
                # Don't fail the invoice creation, just log the error
                import traceback
                traceback.print_exc()
        
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True, 
            'message': 'Invoice created successfully', 
            'invoice_id': invoice_id,
            'invoice_number': invoice_number,
            'unique_id': unique_id
        })
        
    except Exception as e:
        print(f"Error creating sub user invoice: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/invoices/<int:invoice_id>', methods=['DELETE'])
def delete_sub_user_invoice(invoice_id):
    """Delete a sub user invoice"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get invoice details to check ownership and handle financial reversal
        cursor.execute("""
            SELECT i.*, su.created_by as main_user_id
            FROM invoices i
            JOIN sub_users su ON i.created_by_sub_user = su.id
            WHERE i.id = %s AND i.created_by_sub_user = %s
        """, (invoice_id, sub_user_id))
        
        invoice = cursor.fetchone()
        if not invoice:
            return jsonify({'success': False, 'message': 'Invoice not found or access denied'}), 404
        
        print(f"DEBUG: Deleting sub-user invoice {invoice_id} of type {invoice['invoice_type']}")
        
        # Ensure autocommit is disabled for transaction consistency
        connection.autocommit = False
        
        # Handle financial reversal for approved invoices
        if invoice['status'] == 'approved':
            main_user_id = invoice['main_user_id']
            invoice_amount = float(invoice['total_amount'])
            
            try:
                if invoice['invoice_type'] == 'in':
                    # IN invoice deletion: reverse the credit (deduct money)
                    print(f"DEBUG: Reversing IN invoice - deducting ₹{invoice_amount} from main user {main_user_id}")
                    
                    # Find and reverse the transaction that was created for this IN invoice
                    cursor.execute("""
                        SELECT id FROM transactions 
                        WHERE user_id = %s AND invoice_id = %s AND transaction_type = 'credit'
                        AND created_by_sub_user = %s
                    """, (main_user_id, invoice_id, sub_user_id))
                    
                    transaction_record = cursor.fetchone()
                    if transaction_record:
                        # Delete the original credit transaction
                        cursor.execute("""
                            DELETE FROM transactions 
                            WHERE id = %s
                        """, (transaction_record['id'],))
                        print(f"DEBUG: Deleted credit transaction {transaction_record['id']}")
                    
                    # Get main user's default bank account to deduct money
                    cursor.execute("""
                        SELECT id FROM bank_accounts 
                        WHERE user_id = %s AND is_active = 1 AND is_default = 1
                        ORDER BY id LIMIT 1
                    """, (main_user_id,))
                    
                    default_account = cursor.fetchone()
                    bank_account_id = default_account['id'] if default_account else None
                    
                    # If no default account, get the first active account
                    if not bank_account_id:
                        cursor.execute("""
                            SELECT id FROM bank_accounts 
                            WHERE user_id = %s
                            ORDER BY id LIMIT 1
                        """, (main_user_id,))
                        
                        first_account = cursor.fetchone()
                        bank_account_id = first_account['id'] if first_account else None
                    
                    # Deduct money from bank account or cash balance
                    if bank_account_id:
                        cursor.execute("""
                            UPDATE bank_accounts 
                            SET current_balance = current_balance - %s 
                            WHERE id = %s AND user_id = %s
                        """, (invoice_amount, bank_account_id, main_user_id))
                        print(f"DEBUG: Deducted ₹{invoice_amount} from bank account {bank_account_id}")
                    else:
                        # No bank account found, deduct from cash balance
                        cursor.execute("""
                            UPDATE users 
                            SET cash_balance = cash_balance - %s 
                            WHERE id = %s
                        """, (invoice_amount, main_user_id))
                        print(f"DEBUG: Deducted ₹{invoice_amount} from cash balance for main user {main_user_id}")
                    
                    # Create a debit transaction to record the reversal
                    reversal_unique_id = generate_unique_id('TXN')
                    cursor.execute("""
                        INSERT INTO transactions (
                            user_id, unique_id, title, description, amount, 
                            transaction_type, transaction_date, payment_method, 
                            created_by_sub_user, invoice_id, category, purpose
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        main_user_id, reversal_unique_id,
                        f"Reversal: IN Invoice {invoice['invoice_number']} Deleted",
                        f"Sub-user IN invoice deletion reversal: {invoice['client_name']} - {invoice['invoice_number']}",
                        invoice_amount, 'debit', invoice['invoice_date'], 'online',
                        sub_user_id, invoice_id, 'invoice_reversal', 'in_invoice_deletion'
                    ))
                    print(f"DEBUG: Created reversal transaction for deleted IN invoice")
                
                elif invoice['invoice_type'] == 'out':
                    # OUT invoice deletion: refund the payment (add money back)
                    print(f"DEBUG: Refunding OUT invoice - adding ₹{invoice_amount} back to main user {main_user_id}")
                    
                    # Check if this invoice has already been refunded to prevent duplicates
                    cursor.execute("""
                        SELECT id FROM transactions 
                        WHERE user_id = %s AND invoice_id = %s AND transaction_type = 'credit'
                        AND purpose = 'out_invoice_deletion_refund'
                    """, (main_user_id, invoice_id))
                    
                    existing_refund = cursor.fetchone()
                    if existing_refund:
                        print(f"DEBUG: Refund already exists for invoice {invoice_id}, skipping duplicate refund")
                    else:
                        # Find the original debit transaction to determine which account/method was used
                        cursor.execute("""
                            SELECT bank_account_id, payment_method FROM transactions 
                            WHERE user_id = %s AND invoice_id = %s AND transaction_type = 'debit'
                            AND purpose = 'out_invoice_approval'
                            ORDER BY created_at DESC
                            LIMIT 1
                        """, (main_user_id, invoice_id))
                        
                        original_transaction = cursor.fetchone()
                        
                        # Use the same payment method and account as the original approval
                        refund_bank_account_id = None
                        refund_payment_method = 'cash'
                        
                        if original_transaction:
                            refund_bank_account_id = original_transaction['bank_account_id']
                            refund_payment_method = original_transaction['payment_method']
                        else:
                            # Fallback: check invoice approval details
                            if invoice.get('approved_bank_account_id'):
                                refund_bank_account_id = invoice['approved_bank_account_id']
                                refund_payment_method = invoice.get('approved_payment_method', 'bank')
                        
                        # Refund money to the same source
                        if refund_payment_method == 'bank' and refund_bank_account_id:
                            # Verify bank account still exists and is active
                            cursor.execute("""
                                SELECT id, bank_name FROM bank_accounts 
                                WHERE id = %s AND user_id = %s
                            """, (refund_bank_account_id, main_user_id))
                            
                            bank_account = cursor.fetchone()
                            if bank_account:
                                cursor.execute("""
                                    UPDATE bank_accounts 
                                    SET current_balance = current_balance + %s 
                                    WHERE id = %s AND user_id = %s
                                """, (invoice_amount, refund_bank_account_id, main_user_id))
                                print(f"DEBUG: Refunded ₹{invoice_amount} to bank account {refund_bank_account_id} ({bank_account['bank_name']})")
                            else:
                                # Bank account no longer exists, refund to cash
                                cursor.execute("""
                                    UPDATE users 
                                    SET cash_balance = cash_balance + %s 
                                    WHERE id = %s
                                """, (invoice_amount, main_user_id))
                                refund_payment_method = 'cash'
                                refund_bank_account_id = None
                                print(f"DEBUG: Original bank account not found, refunded ₹{invoice_amount} to cash balance")
                        else:
                            # Cash refund
                            cursor.execute("""
                                UPDATE users 
                                SET cash_balance = cash_balance + %s 
                                WHERE id = %s
                            """, (invoice_amount, main_user_id))
                            print(f"DEBUG: Refunded ₹{invoice_amount} to cash balance")
                        
                        # Create a credit transaction to record the refund
                        refund_unique_id = generate_unique_id('TXN')
                        cursor.execute("""
                            INSERT INTO transactions (
                                user_id, unique_id, title, description, amount, 
                                transaction_type, transaction_date, payment_method, 
                                bank_account_id, created_by_sub_user, invoice_id,
                                category, purpose
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                            )
                        """, (
                            main_user_id, refund_unique_id,
                            f"Refund: OUT Invoice {invoice['invoice_number']} Deleted",
                            f"Refund for deleted approved OUT invoice: {invoice['client_name']} - {invoice['invoice_number']}",
                            invoice_amount, 'credit', invoice['invoice_date'], refund_payment_method,
                            refund_bank_account_id, sub_user_id, invoice_id,
                            'invoice_refund', 'out_invoice_deletion_refund'
                        ))
                        print(f"DEBUG: Created refund transaction for deleted OUT invoice")
                
            except Exception as financial_error:
                print(f"Error handling financial reversal/refund: {financial_error}")
                import traceback
                traceback.print_exc()
                if connection:
                    connection.rollback()
                return jsonify({'success': False, 'message': f'Failed to handle financial reversal: {str(financial_error)}'}), 500
        
        # Delete invoice items first (foreign key constraint)
        cursor.execute("DELETE FROM invoice_items WHERE invoice_id = %s", (invoice_id,))
        items_deleted = cursor.rowcount
        print(f"DEBUG: Deleted {items_deleted} invoice items")
        
        # Delete any download approval records
        cursor.execute("DELETE FROM sub_user_download_approvals WHERE invoice_id = %s", (invoice_id,))
        approvals_deleted = cursor.rowcount
        print(f"DEBUG: Deleted {approvals_deleted} download approval records")
        
        # Delete the invoice itself
        cursor.execute("DELETE FROM invoices WHERE id = %s AND created_by_sub_user = %s", (invoice_id, sub_user_id))
        
        if cursor.rowcount == 0:
            if connection:
                connection.rollback()
            return jsonify({'success': False, 'message': 'Invoice not found or already deleted'}), 404
        
        # Commit the transaction
        connection.commit()
        connection.autocommit = True  # Re-enable autocommit
        cursor.close()
        connection.close()
        
        print(f"DEBUG: Successfully deleted sub-user invoice {invoice_id}")
        
        return jsonify({
            'success': True, 
            'message': f'Invoice {invoice["invoice_number"]} deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting sub user invoice: {e}")
        try:
            if 'connection' in locals() and connection:
                connection.rollback()
                connection.autocommit = True  # Re-enable autocommit
                cursor.close()
                connection.close()
        except Exception as cleanup_error:
            print(f"Error during cleanup: {cleanup_error}")
        
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/invoices/<int:invoice_id>/pdf')
def download_sub_user_invoice_pdf(invoice_id):
    """Download PDF for sub user invoice - requires approval for OUT invoices"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Get invoice details with download approval status
        cursor.execute("""
            SELECT i.*, COALESCE(sda.status, 'not_requested') as download_status
            FROM invoices i
            LEFT JOIN sub_user_download_approvals sda ON i.id = sda.invoice_id AND sda.sub_user_id = %s
            WHERE i.id = %s AND i.created_by_sub_user = %s
        """, (sub_user_id, invoice_id, sub_user_id))
        
        invoice = cursor.fetchone()
        if not invoice:
            return jsonify({'success': False, 'message': 'Invoice not found'}), 404
        
        # Check download permission for OUT invoices
        if invoice['invoice_type'] == 'out':
            if invoice['download_status'] != 'approved':
                return jsonify({
                    'success': False, 
                    'message': 'Download approval required for OUT invoices',
                    'requires_approval': True
                }), 403
        
        print(f"DEBUG: Generating PDF for sub-user invoice {invoice_id}")
        
        # Ensure invoice_type is set correctly
        if 'invoice_type' not in invoice or invoice['invoice_type'] is None:
            invoice['invoice_type'] = 'out'
            print("DEBUG: Setting default invoice_type to 'out'")
        else:
            print(f"DEBUG: Using existing invoice_type: {invoice['invoice_type']}")
        
        # Get invoice items
        cursor.execute("SELECT * FROM invoice_items WHERE invoice_id=%s", (invoice_id,))
        items = cursor.fetchall()
        
        # Get company settings for the main user (invoice belongs to main user)
        cursor.execute("SELECT * FROM company_settings WHERE user_id = %s LIMIT 1", (invoice['user_id'],))
        company = cursor.fetchone()
        
        # Get bank details
        cursor.execute("SELECT * FROM bank_details WHERE invoice_id = %s", (invoice_id,))
        bank_details = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        # Generate PDF using the same logic as main user
        filename = f"invoice_{invoice['invoice_number']}.pdf"
        filepath = os.path.join(app.config['EXPORT_FOLDER'], filename)
        
        # Ensure exports directory exists
        os.makedirs(app.config['EXPORT_FOLDER'], exist_ok=True)
        
        # Generate the PDF using pdftemp.html template (same as main user)
        result = generate_pdftemp_invoice(invoice, items, company, bank_details, filepath, filename)
        
        # Check if result is a file path (success) or error tuple
        if isinstance(result, str) and os.path.exists(result):
            print(f"DEBUG: Sub-user PDF generated successfully at {result}")
            
            # Track download in history (if table exists)
            try:
                connection = get_db_connection()
                if connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        "INSERT INTO pdf_download_history (invoice_id, user_id, download_time, downloaded_by_sub_user) VALUES (%s, %s, %s, %s)",
                        (invoice_id, invoice['user_id'], datetime.now(), sub_user_id)
                    )
                    connection.commit()
                    cursor.close()
                    connection.close()
            except Exception as track_error:
                print(f"DEBUG: Warning - Could not track sub-user invoice download: {track_error}")
            
            return send_file(result, as_attachment=True, download_name=filename)
        else:
            # Handle error case
            error_msg = result[0]['error'] if isinstance(result, tuple) else str(result)
            print(f"DEBUG: Sub-user PDF generation failed: {error_msg}")
            return jsonify({'error': error_msg}), 500
        
    except Exception as e:
        print(f"DEBUG: Error generating sub-user invoice PDF: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/sub-user/request-invoice-download', methods=['POST'])
def request_invoice_download():
    """Request approval to download an OUT invoice"""
    if 'sub_user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        invoice_id = data.get('invoice_id')
        
        if not invoice_id:
            return jsonify({'success': False, 'message': 'Invoice ID is required'}), 400
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        sub_user_id = session['sub_user_id']
        
        # Check if invoice exists and belongs to this sub user
        cursor.execute("""
            SELECT id, invoice_type, invoice_number
            FROM invoices 
            WHERE id = %s AND created_by_sub_user = %s
        """, (invoice_id, sub_user_id))
        
        invoice = cursor.fetchone()
        if not invoice:
            return jsonify({'success': False, 'message': 'Invoice not found'}), 404
        
        if invoice['invoice_type'] != 'out':
            return jsonify({'success': False, 'message': 'Approval not required for IN invoices'}), 400
        
        # Check if request already exists
        cursor.execute("""
            SELECT id, status FROM sub_user_download_approvals 
            WHERE invoice_id = %s AND sub_user_id = %s
        """, (invoice_id, sub_user_id))
        
        existing_request = cursor.fetchone()
        if existing_request:
            if existing_request['status'] == 'pending':
                return jsonify({'success': False, 'message': 'Approval request already pending'}), 400
            elif existing_request['status'] == 'approved':
                return jsonify({'success': False, 'message': 'Invoice already approved for download'}), 400
            else:
                # Update existing rejected request
                cursor.execute("""
                    UPDATE sub_user_download_approvals 
                    SET status = 'pending', requested_at = NOW()
                    WHERE id = %s
                """, (existing_request['id'],))
        else:
            # Create new approval request
            cursor.execute("""
                INSERT INTO sub_user_download_approvals (
                    invoice_id, sub_user_id, status, requested_at
                ) VALUES (%s, %s, 'pending', NOW())
            """, (invoice_id, sub_user_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True, 
            'message': f'Download approval requested for invoice {invoice["invoice_number"]}'
        })
        
    except Exception as e:
        print(f"Error requesting invoice download: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Invoice Download Approval Management Routes
@app.route('/api/invoice-download-approvals/pending', methods=['GET'])
@login_required
def get_pending_invoice_download_approvals():
    """Get pending invoice download approval requests for the main user"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Get pending invoice download approval requests
        cursor.execute("""
            SELECT sda.id, sda.invoice_id, sda.status, sda.requested_at,
                   i.invoice_number, i.client_name, i.total_amount, i.invoice_type,
                   su.sub_user_id, CONCAT(su.first_name, ' ', su.last_name) as sub_user_name,
                   i.id as invoice_db_id
            FROM sub_user_download_approvals sda
            JOIN invoices i ON sda.invoice_id = i.id
            JOIN sub_users su ON sda.sub_user_id = su.id
            WHERE i.user_id = %s AND sda.status = 'pending'
            ORDER BY sda.requested_at DESC
        """, (user_id,))
        
        requests = cursor.fetchall()
        
        # Convert datetime to string for JSON serialization
        for request in requests:
            if request['requested_at']:
                request['requested_at'] = request['requested_at'].isoformat()
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'requests': requests})
    except Exception as e:
        print(f"Error getting pending invoice download approvals: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/invoice-download-approvals/<int:approval_id>', methods=['GET'])
@login_required
def get_invoice_download_approval_details(approval_id):
    """Get details of a specific invoice download approval request"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Get invoice download approval request details
        cursor.execute("""
            SELECT sda.id, sda.invoice_id, sda.status, sda.requested_at as created_at,
                   i.invoice_number, i.client_name, i.total_amount, i.invoice_type,
                   su.sub_user_id, CONCAT(su.first_name, ' ', su.last_name) as sub_user_name,
                   'invoice_download' as request_category,
                   'invoice_download' as request_type,
                   CONCAT('Download: ', i.invoice_number) as title,
                   i.total_amount as amount
            FROM sub_user_download_approvals sda
            JOIN invoices i ON sda.invoice_id = i.id
            JOIN sub_users su ON sda.sub_user_id = su.id
            WHERE sda.id = %s AND i.user_id = %s
        """, (approval_id, user_id))
        
        request_data = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if not request_data:
            return jsonify({'success': False, 'message': 'Invoice download approval request not found'}), 404
        
        # Create fake request_data JSON for invoice download requests
        request_data['request_data'] = json.dumps({
            'title': f"Download: {request_data['invoice_number']}",
            'amount': float(request_data['total_amount']),
            'invoice_id': request_data['invoice_id'],
            'invoice_type': request_data['invoice_type'],
            'client_name': request_data['client_name'],
            'payment_method': 'not_applicable'  # Invoice downloads don't have payment method
        })
        
        # Convert datetime to string for JSON serialization
        if request_data.get('created_at'):
            request_data['created_at'] = request_data['created_at'].isoformat()
        
        return jsonify({'success': True, 'request': request_data})
        
    except Exception as e:
        print(f"Error getting invoice download approval details for approval_id {approval_id}: {e}")
        print(f"User ID: {user_id}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/invoices/<int:invoice_id>/details', methods=['GET'])
@login_required  
def get_invoice_details_with_bank(invoice_id):
    """Get invoice details including bank information"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Get invoice details - check both main user invoices and sub-user created invoices
        cursor.execute("""
            SELECT i.*, c.company_name, c.address as company_address, c.city as company_city,
                   c.state as company_state, c.pincode as company_pincode
            FROM invoices i
            LEFT JOIN company_settings c ON i.user_id = c.user_id
            WHERE i.id = %s AND i.user_id = %s
        """, (invoice_id, user_id))
        
        invoice = cursor.fetchone()
        
        if not invoice:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Invoice not found'}), 404
        
        # Get bank details for the invoice owner (main user)
        cursor.execute("""
            SELECT bank_name, account_number, ifsc_code, branch_name
            FROM bank_accounts
            WHERE user_id = %s
            ORDER BY id
        """, (user_id,))
        
        bank_details = cursor.fetchall()
        
        # Get main user's cash balance as well
        cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (user_id,))
        cash_row = cursor.fetchone()
        cash_balance = cash_row['cash_balance'] if cash_row and 'cash_balance' in cash_row else 0
        
        # Also get vendor bank details if this invoice uses vendor account
        vendor_bank_details = None
        if invoice.get('bank_account_type') == 'vendor':
            cursor.execute("""
                SELECT bank_name, account_number, ifsc_code, account_holder_name, upi_id, phone_number
                FROM vendor_bank_details
                WHERE invoice_id = %s
            """, (invoice_id,))
            vendor_bank_details = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        # Prepare response data
        response_data = {
            'success': True,
            'invoice': {
                'id': invoice['id'],
                'invoice_number': invoice['invoice_number'],
                'invoice_type': invoice['invoice_type'],
                'client_name': invoice['client_name'],
                'total_amount': float(invoice['total_amount']) if invoice['total_amount'] else 0,
                'invoice_date': invoice['invoice_date'].isoformat() if invoice['invoice_date'] else None,
                'due_date': invoice['due_date'].isoformat() if invoice['due_date'] else None,
                'payment_method': invoice.get('payment_method'),
                'bank_account_type': invoice.get('bank_account_type'),
                'status': invoice['status']
            },
            'bank_details': bank_details,
            'cash_balance': float(cash_balance or 0),
            'vendor_bank_details': vendor_bank_details,
            'company': {
                'name': invoice['company_name'],
                'address': invoice['company_address'],
                'city': invoice['company_city'],
                'state': invoice['company_state'],
                'pincode': invoice['company_pincode']
            } if invoice.get('company_name') else None
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error getting invoice details for invoice_id {invoice_id}: {e}")
        print(f"User ID: {user_id}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/invoice-download-approvals/<int:approval_id>/approve', methods=['PUT'])
@login_required
def approve_invoice_download(approval_id):
    """Approve an invoice download request"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Verify the approval request belongs to this user
        cursor.execute("""
            SELECT sda.id, i.invoice_number
            FROM sub_user_download_approvals sda
            JOIN invoices i ON sda.invoice_id = i.id
            WHERE sda.id = %s AND i.user_id = %s AND sda.status = 'pending'
        """, (approval_id, user_id))
        
        approval = cursor.fetchone()
        if not approval:
            return jsonify({'success': False, 'message': 'Approval request not found or already processed'}), 404
        
        # Update approval status
        cursor.execute("""
            UPDATE sub_user_download_approvals 
            SET status = 'approved', approved_at = NOW(), approved_by = %s
            WHERE id = %s
        """, (user_id, approval_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True, 
            'message': f'Download approved for invoice {approval["invoice_number"]}'
        })
        
    except Exception as e:
        print(f"Error approving invoice download: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/invoices/<int:invoice_id>/approve', methods=['PUT'])
@login_required
def approve_sub_user_out_invoice(invoice_id):
    """Approve a sub user OUT invoice and deduct amount from selected bank/cash"""
    try:
        data = request.get_json()
        bank_account_id = data.get('bank_account_id')  # Can be None for cash
        payment_method = data.get('payment_method', 'cash')  # 'bank' or 'cash'
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        # Start transaction
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        print(f"Starting OUT invoice approval process for invoice {invoice_id} by user {user_id}")
        print(f"Payment method: {payment_method}, Bank account ID: {bank_account_id}")
        
        # Get invoice details and verify ownership (try both direct ownership and sub-user creation)
        try:
            cursor.execute("""
                SELECT i.*, 
                       CASE 
                           WHEN i.created_by_sub_user IS NOT NULL THEN CONCAT(su.first_name, ' ', su.last_name)
                           ELSE 'Main User'
                       END as sub_user_name,
                       CASE 
                           WHEN i.created_by_sub_user IS NOT NULL THEN su.id
                           ELSE NULL
                       END as sub_user_id
                FROM invoices i
                LEFT JOIN sub_users su ON i.created_by_sub_user = su.id
                WHERE i.id = %s AND i.user_id = %s AND i.invoice_type = 'out' AND (i.status = 'pending' OR i.status IS NULL OR i.status = '')
            """, (invoice_id, user_id))
        except Exception as query_error:
            print(f"ERROR in invoice lookup query: {query_error}")
            connection.rollback()
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': f'Database query error: {str(query_error)}'}), 500
        
        invoice = cursor.fetchone()
        print(f"DEBUG: Found invoice: {invoice}")
        
        if not invoice:
            # Debug: Check if invoice exists at all
            cursor.execute("SELECT id, user_id, invoice_type, status FROM invoices WHERE id = %s", (invoice_id,))
            debug_invoice = cursor.fetchone()
            print(f"DEBUG: Invoice {invoice_id} lookup failed. Invoice exists: {debug_invoice}")
            print(f"DEBUG: Looking for user_id={user_id}, invoice_type='out', status='pending'")
            
            connection.rollback()
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Invoice not found, already processed, or not an OUT invoice'}), 404
        
        invoice_amount = float(invoice['total_amount'])
        
        # Validate bank account if payment method is bank
        if payment_method == 'bank':
            if not bank_account_id:
                connection.rollback()
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': 'Bank account selection required for bank payment'}), 400
                
            # Verify bank account belongs to user and has sufficient balance
            cursor.execute("""
                SELECT id, bank_name, current_balance
                FROM bank_accounts
                WHERE id = %s AND user_id = %s
            """, (bank_account_id, user_id))
            
            bank_account = cursor.fetchone()
            if not bank_account:
                connection.rollback()
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': 'Invalid bank account selected'}), 400
            
            if float(bank_account['current_balance']) < invoice_amount:
                connection.rollback()
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': f'Insufficient balance in {bank_account["bank_name"]}. Available: ₹{bank_account["current_balance"]}, Required: ₹{invoice_amount}'}), 400
        
        else:  # Cash payment
            # Check cash balance
            cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (user_id,))
            user_data = cursor.fetchone()
            
            if not user_data or float(user_data['cash_balance']) < invoice_amount:
                available_cash = user_data['cash_balance'] if user_data else 0
                connection.rollback()
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': f'Insufficient cash balance. Available: ₹{available_cash}, Required: ₹{invoice_amount}'}), 400
        
        # Deduct amount from selected payment method
        if payment_method == 'bank' and bank_account_id:
            cursor.execute("""
                UPDATE bank_accounts 
                SET current_balance = current_balance - %s 
                WHERE id = %s AND user_id = %s
            """, (invoice_amount, bank_account_id, user_id))
            print(f"Deducted ₹{invoice_amount} from bank account {bank_account_id}")
        else:
            cursor.execute("""
                UPDATE users 
                SET cash_balance = cash_balance - %s 
                WHERE id = %s
            """, (invoice_amount, user_id))
            print(f"Deducted ₹{invoice_amount} from cash balance")
        
        # Update invoice status to approved and record approval details
        cursor.execute("""
            UPDATE invoices 
            SET status = 'approved',
                approved_at = NOW(),
                approved_by = %s,
                approved_payment_method = %s,
                approved_bank_account_id = %s
            WHERE id = %s
        """, (user_id, payment_method, bank_account_id, invoice_id))
        affected_rows = cursor.rowcount
        print(f"Updated invoice {invoice_id} status to 'approved' - affected rows: {affected_rows}")
        
        if affected_rows == 0:
            print(f"WARNING: No rows were updated when trying to approve invoice {invoice_id}")
            # Let's check what the current status is
            cursor.execute("SELECT id, status, invoice_type FROM invoices WHERE id = %s", (invoice_id,))
            current_invoice = cursor.fetchone()
            print(f"Current invoice state: {current_invoice}")
        else:
            print(f"Successfully updated invoice {invoice_id} status to approved")
        
        # Also auto-approve any pending download requests for this invoice
        cursor.execute("""
            UPDATE sub_user_download_approvals 
            SET status = 'approved', approved_at = NOW(), approved_by = %s
            WHERE invoice_id = %s AND status = 'pending'
        """, (user_id, invoice_id))
        download_approvals_updated = cursor.rowcount
        print(f"Auto-approved {download_approvals_updated} pending download request(s) for invoice {invoice_id}")
        
        # If no download approval record exists, create one (in case they haven't requested download yet)
        if download_approvals_updated == 0:
            # Get the sub_user_id from the invoice
            sub_user_id = invoice.get('created_by_sub_user')
            if sub_user_id:
                cursor.execute("""
                    INSERT INTO sub_user_download_approvals (
                        invoice_id, sub_user_id, status, requested_at, approved_at, approved_by
                    ) VALUES (%s, %s, 'approved', NOW(), NOW(), %s)
                    ON DUPLICATE KEY UPDATE 
                        status = 'approved', approved_at = NOW(), approved_by = %s
                """, (invoice_id, sub_user_id, user_id, user_id))
                print(f"Created pre-approved download record for invoice {invoice_id}")
        
        # The download approval requests are already updated above to 'approved' status
        # This will automatically remove them from pending requests when the frontend refreshes
        print(f"Download approval status updated - requests will be removed from pending list on refresh")
        
        # Create transaction record for the deduction
        transaction_unique_id = generate_unique_id('TXN')
        
        # Determine the payment method display name
        if payment_method == 'bank' and bank_account_id:
            # Get bank name for display
            cursor.execute("SELECT bank_name FROM bank_accounts WHERE id = %s", (bank_account_id,))
            bank_result = cursor.fetchone()
            transaction_payment_method = bank_result['bank_name'] if bank_result else 'Bank Account'
        else:
            transaction_payment_method = 'CASH'
        
        cursor.execute("""
            INSERT INTO transactions (
                user_id, unique_id, title, description, amount, 
                transaction_type, transaction_date, payment_method, 
                bank_account_id, created_by_sub_user,
                category, purpose
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            user_id, transaction_unique_id, 
            f"OUT Invoice Approval - {invoice['invoice_number']}", 
            f"Payment for approved OUT invoice from {invoice['sub_user_name']}", 
            invoice_amount, 'debit', datetime.now().date(), transaction_payment_method,
            bank_account_id, invoice['sub_user_id'],
            'invoice_payment', 'out_invoice_approval'
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        payment_source = f"bank account ({bank_account['bank_name']})" if payment_method == 'bank' else "cash balance"
        
        return jsonify({
            'success': True,
            'message': f'OUT invoice {invoice["invoice_number"]} approved successfully. ₹{invoice_amount} deducted from {payment_source}',
            'invoice_number': invoice['invoice_number'],
            'amount': invoice_amount,
            'payment_method': payment_method,
            'transaction_id': transaction_unique_id
        })
        
    except Exception as e:
        if connection:
            connection.rollback()
            cursor.close() 
            connection.close()
        print(f"Error approving OUT invoice: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/pending-out-invoices', methods=['GET'])
@login_required
def get_pending_out_invoices():
    """Get all pending OUT invoices from sub users for main user approval"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Get all pending OUT invoices from sub users
        cursor.execute("""
            SELECT 
                i.*,
                su.sub_user_id,
                CONCAT(su.first_name, ' ', su.last_name) as sub_user_name,
                su.email as sub_user_email
            FROM invoices i
            JOIN sub_users su ON i.created_by_sub_user = su.id
            WHERE su.created_by = %s 
            AND i.invoice_type = 'out' 
            AND i.status = 'pending'
            ORDER BY i.created_at ASC
        """, (user_id,))
        
        pending_invoices = cursor.fetchall()
        
        # Get invoice items for each invoice
        for invoice in pending_invoices:
            cursor.execute("""
                SELECT * FROM invoice_items WHERE invoice_id = %s ORDER BY id
            """, (invoice['id'],))
            invoice['items'] = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'pending_invoices': pending_invoices
        })
        
    except Exception as e:
        print(f"Error getting pending OUT invoices: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sub-user/invoices/<int:invoice_id>/reject', methods=['PUT'])
@login_required
def reject_sub_user_out_invoice(invoice_id):
    """Reject a sub user OUT invoice"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Get invoice details and verify ownership
        cursor.execute("""
            SELECT i.*, 
                   CASE 
                       WHEN i.created_by_sub_user IS NOT NULL THEN CONCAT(su.first_name, ' ', su.last_name)
                       ELSE 'Main User'
                   END as sub_user_name
            FROM invoices i
            LEFT JOIN sub_users su ON i.created_by_sub_user = su.id
            WHERE i.id = %s AND i.user_id = %s AND i.invoice_type = 'out' AND (i.status = 'pending' OR i.status IS NULL OR i.status = '')
        """, (invoice_id, user_id))
        
        invoice = cursor.fetchone()
        if not invoice:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Invoice not found or already processed'}), 404
        
        # Update invoice status to rejected
        cursor.execute("""
            UPDATE invoices 
            SET status = 'rejected',
                approved_at = NOW(),
                approved_by = %s
            WHERE id = %s
        """, (user_id, invoice_id))
        
        # Also reject any pending download requests for this invoice
        cursor.execute("""
            UPDATE sub_user_download_approvals 
            SET status = 'rejected', approved_at = NOW(), approved_by = %s
            WHERE invoice_id = %s AND status = 'pending'
        """, (user_id, invoice_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': f'OUT invoice {invoice["invoice_number"]} rejected successfully',
            'invoice_number': invoice['invoice_number']
        })
        
    except Exception as e:
        print(f"Error rejecting OUT invoice: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/debug/invoice/<int:invoice_id>/status', methods=['GET'])
def debug_invoice_status(invoice_id):
    """Debug endpoint to check invoice status"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        
        # Get invoice details
        cursor.execute("""
            SELECT id, invoice_number, status, approved_at, approved_by, approved_payment_method
            FROM invoices 
            WHERE id = %s
        """, (invoice_id,))
        
        invoice = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if not invoice:
            return jsonify({'success': False, 'message': 'Invoice not found'}), 404
            
        return jsonify({
            'success': True,
            'invoice': invoice
        })
        
    except Exception as e:
        print(f"Error checking invoice status: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/user/bank-accounts', methods=['GET'])
@login_required
def get_user_bank_accounts():
    """Get user's bank accounts for payment selection"""
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Get user's bank accounts
        cursor.execute("""
            SELECT id, bank_name, account_number, current_balance, ifsc_code
            FROM bank_accounts 
            WHERE user_id = %s 
            ORDER BY bank_name ASC
        """, (user_id,))
        
        bank_accounts = cursor.fetchall()
        
        # Also get user's cash balance
        cursor.execute("SELECT cash_balance FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        cash_balance = user_data['cash_balance'] if user_data else 0
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'bank_accounts': bank_accounts,
            'cash_balance': cash_balance
        })
        
    except Exception as e:
        print(f"Error getting bank accounts: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/invoice-download-approvals/<int:approval_id>/reject', methods=['PUT'])
@login_required
def reject_invoice_download(approval_id):
    """Reject an invoice download request"""
    try:
        data = request.get_json() or {}
        reason = data.get('reason', 'Rejected by main user')
        
        connection = get_db_connection()
        if not connection:
            return jsonify({'success': False, 'message': 'Database connection failed'}), 500
        
        cursor = connection.cursor(dictionary=True)
        user_id = session['user_id']
        
        # Verify the approval request belongs to this user
        cursor.execute("""
            SELECT sda.id, i.invoice_number
            FROM sub_user_download_approvals sda
            JOIN invoices i ON sda.invoice_id = i.id
            WHERE sda.id = %s AND i.user_id = %s AND sda.status = 'pending'
        """, (approval_id, user_id))
        
        approval = cursor.fetchone()
        if not approval:
            return jsonify({'success': False, 'message': 'Approval request not found or already processed'}), 404
        
        # Update approval status
        cursor.execute("""
            UPDATE sub_user_download_approvals 
            SET status = 'rejected', approved_at = NOW(), approved_by = %s, notes = %s
            WHERE id = %s
        """, (user_id, reason, approval_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True, 
            'message': f'Download rejected for invoice {approval["invoice_number"]}'
        })
        
    except Exception as e:
        print(f"Error rejecting invoice download: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# Debug endpoint to check authentication status
@app.route('/api/auth-status')
def check_auth_status():
    """Debug endpoint to check authentication status"""
    return jsonify({
        'session_keys': list(session.keys()),
        'session_data': dict(session),
        'is_main_user': 'user_id' in session,
        'is_sub_user': 'sub_user_id' in session,
        'timestamp': datetime.now().isoformat()
    })

# Create the download approvals table if it doesn't exist
def create_download_approvals_table():
    """Create sub_user_download_approvals table if it doesn't exist"""
    try:
        connection = get_db_connection()
        if not connection:
            print("Failed to get database connection for download approvals table")
            return False
        
        cursor = connection.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sub_user_download_approvals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_id INT NOT NULL,
                sub_user_id INT NOT NULL,
                status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP NULL,
                approved_by INT NULL,
                notes TEXT,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                FOREIGN KEY (sub_user_id) REFERENCES sub_users(id) ON DELETE CASCADE,
                FOREIGN KEY (approved_by) REFERENCES users(id) ON DELETE SET NULL,
                UNIQUE KEY unique_request (invoice_id, sub_user_id),
                INDEX idx_status (status),
                INDEX idx_sub_user (sub_user_id)
            )
        """)
        
        connection.commit()
        cursor.close()
        connection.close()
        print("Download approvals table created successfully")
        return True
        
    except Exception as e:
        print(f"Error creating download approvals table: {e}")
        return False

def create_vendor_bank_details_table():
    """Create vendor_bank_details table if it doesn't exist"""
    try:
        connection = get_db_connection()
        if not connection:
            print("Failed to get database connection for vendor bank details table")
            return False
        
        cursor = connection.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vendor_bank_details (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_id INT NOT NULL,
                bank_name VARCHAR(255),
                account_number VARCHAR(50),
                ifsc_code VARCHAR(20),
                account_holder_name VARCHAR(255),
                upi_id VARCHAR(100),
                phone_number VARCHAR(20),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                INDEX idx_invoice (invoice_id)
            )
        """)
        
        connection.commit()
        cursor.close()
        connection.close()
        print("Vendor bank details table created successfully")
        return True
        
    except Exception as e:
        print(f"Error creating vendor bank details table: {e}")
        return False

def update_invoices_table_for_enhanced_fields():
    """Add new fields to invoices table for enhanced sub-user invoice functionality"""
    try:
        connection = get_db_connection()
        if not connection:
            print("Failed to get database connection for invoices table update")
            return False
        
        cursor = connection.cursor()
        
        # Add new columns to invoices table
        new_columns = [
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS billing_company_name VARCHAR(255)",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS billing_address TEXT",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS billing_city VARCHAR(100)",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS billing_state VARCHAR(100)",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS billing_pin VARCHAR(10)",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS gstin_number VARCHAR(20)",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS pan_number VARCHAR(20)",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS payment_method VARCHAR(20) DEFAULT 'cash'",
            "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS bank_account_type VARCHAR(20)"
        ]
        
        for column_query in new_columns:
            try:
                cursor.execute(column_query)
                print(f"Added column: {column_query}")
            except Exception as e:
                print(f"Column may already exist or error adding: {column_query} - {e}")
        
        connection.commit()
        cursor.close()
        connection.close()
        print("Invoices table updated successfully with enhanced fields")
        return True
        
    except Exception as e:
        print(f"Error updating invoices table: {e}")
        return False

def update_invoices_table_for_sub_users():
    """Add created_by_sub_user column to invoices table if it doesn't exist"""
    try:
        connection = get_db_connection()
        if not connection:
            print("Failed to get database connection for invoices table update")
            return False
        
        cursor = connection.cursor()
        
        # Check if column already exists
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'invoices' 
            AND COLUMN_NAME = 'created_by_sub_user'
        """)
        
        column_exists = cursor.fetchone()
        
        if not column_exists:
            print("Adding created_by_sub_user column to invoices table...")
            # Add the column
            cursor.execute("""
                ALTER TABLE invoices 
                ADD COLUMN created_by_sub_user INT NULL,
                ADD INDEX idx_created_by_sub_user (created_by_sub_user)
            """)
            connection.commit()
            print("created_by_sub_user column added to invoices table successfully")
        else:
            print("created_by_sub_user column already exists in invoices table")
        
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        print(f"Error updating invoices table: {e}")
        return False

if __name__ == '__main__':
    # Create sub users table on startup
    create_sub_users_table()
    
    # Create download approvals table
    create_download_approvals_table()
    
    # Create vendor bank details table
    create_vendor_bank_details_table()
    
    # Update invoices table for sub user support
    update_invoices_table_for_sub_users()
    
    # Update invoices table with enhanced fields
    update_invoices_table_for_enhanced_fields()
    
    port = int(os.environ.get('PORT', 5000))
    
    # Run in debug mode only in development
    debug_mode = True  # Force debug mode to reload templates
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
