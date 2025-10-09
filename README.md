# Laitusneo - Expense Tracker & Invoicing System

## 🚀 Project Overview

**Laitusneo** is a comprehensive expense tracking and invoicing system designed for businesses and individuals to manage their financial operations efficiently. The system features a multi-user architecture with role-based access control, supporting main users, sub-users, and administrative functions.

### ✨ Key Features

- **Multi-User Management**: Support for main users, sub-users, and admin roles
- **Expense Tracking**: Comprehensive expense management with categorization and approval workflows
- **Transaction Management**: Real-time transaction tracking with balance management
- **Invoice Generation**: Professional invoice creation and management (Coming Soon for sub-users)
- **PDF Export**: Generate professional PDF reports and invoices
- **Real-time Analytics**: Dashboard with charts and financial insights
- **Responsive Design**: Modern, professional UI that works on all devices
- **Secure Authentication**: Role-based access control with session management

## 🏗️ System Architecture

### User Roles

1. **Main User (Client)**
   - Full access to all features
   - Can create and manage sub-users
   - Approve/reject sub-user requests
   - Access to complete financial dashboard

2. **Sub User**
   - Limited access to assigned features
   - Can create expense and transaction requests
   - Submit requests for approval
   - View approved transactions

3. **Admin**
   - System administration
   - User management
   - System-wide reports and analytics

### Technology Stack

- **Backend**: Python Flask
- **Database**: MySQL
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **PDF Generation**: ReportLab
- **Authentication**: Flask-Session with password hashing
- **Icons**: Font Awesome 6
- **Charts**: Chart.js

## 📋 Prerequisites

- Python 3.8 or higher
- MySQL 5.7 or higher
- pip (Python package installer)

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone <repository-url>
cd laitusneo-expense-tracker
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Database Setup

#### Create MySQL Database
```sql
CREATE DATABASE expense_tracker;
```

#### Update Database Configuration
Edit `app.py` and update the `DB_CONFIG` dictionary:
```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'your_mysql_username',
    'password': 'your_mysql_password',
    'database': 'expense_tracker'
}
```

### 5. Run the Application
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## 📁 Project Structure

```
laitusneo-expense-tracker/
├── app.py                          # Main Flask application
├── requirements.txt                # Python dependencies
├── README.md                      # Project documentation
├── static/                        # Static assets
│   ├── style.css                  # Main stylesheet
│   ├── app.js                     # Main JavaScript file
│   ├── admin.js                   # Admin-specific JavaScript
│   ├── invoice_form_generator.js  # Invoice generation scripts
│   ├── laitusneo.svg             # Company logo
│   └── default-avatar.png        # Default user avatar
├── templates/                     # HTML templates
│   ├── base.html                 # Base template
│   ├── login.html                # Login page
│   ├── register.html             # Registration page
│   ├── dashboard.html            # Main user dashboard
│   ├── expenses.html             # Expense management
│   ├── transactions.html         # Transaction management
│   ├── invoices.html             # Invoice management
│   ├── sub_user_base.html        # Sub-user base template
│   ├── sub_user_dashboard.html   # Sub-user dashboard
│   ├── sub_user_expenses.html    # Sub-user expenses
│   ├── sub_user_transactions.html # Sub-user transactions
│   ├── sub_user_invoices.html    # Sub-user invoices
│   ├── sub_users.html            # Sub-user management
│   ├── admin_dashboard.html      # Admin dashboard
│   └── settings.html             # User settings
├── uploads/                      # File uploads
├── exports/                      # Generated PDFs and exports
└── uploads/templates/            # PDF templates
```

## 🗄️ Database Schema

### Core Tables

#### Users Table
```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

#### Sub Users Table
```sql
CREATE TABLE sub_users (
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
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);
```

#### Expenses Table
```sql
CREATE TABLE expenses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    unique_id VARCHAR(20) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    category VARCHAR(100),
    purpose TEXT,
    payment_method VARCHAR(50),
    bank_account VARCHAR(100),
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### Transactions Table
```sql
CREATE TABLE transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    unique_id VARCHAR(20) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    transaction_type ENUM('income', 'expense', 'transfer') NOT NULL,
    category VARCHAR(100),
    description TEXT,
    payment_method VARCHAR(50),
    bank_account VARCHAR(100),
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### Sub User Requests Table
```sql
CREATE TABLE sub_user_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sub_user_id INT NOT NULL,
    request_type ENUM('expense', 'transaction', 'invoice') NOT NULL,
    unique_id VARCHAR(20) UNIQUE NOT NULL,
    status ENUM('pending', 'approved', 'rejected', 'deleted') DEFAULT 'pending',
    request_data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (sub_user_id) REFERENCES sub_users(id) ON DELETE CASCADE
);
```

## 🔧 API Endpoints

### Authentication
- `POST /login` - User login
- `POST /register` - User registration
- `POST /sub-user-login` - Sub-user login
- `POST /admin-login` - Admin login
- `GET /logout` - User logout

### Main User Endpoints
- `GET /dashboard` - Main dashboard
- `GET /expenses` - Expense management page
- `GET /transactions` - Transaction management page
- `GET /invoices` - Invoice management page
- `GET /sub-users` - Sub-user management page

### Sub User Endpoints
- `GET /sub-user/dashboard` - Sub-user dashboard
- `GET /sub-user/expenses` - Sub-user expenses
- `GET /sub-user/transactions` - Sub-user transactions
- `GET /sub-user/invoices` - Sub-user invoices

### API Endpoints
- `GET /api/expenses` - Get user expenses
- `POST /api/expenses` - Create new expense
- `DELETE /api/expenses/<id>` - Delete expense
- `GET /api/transactions` - Get user transactions
- `POST /api/transactions` - Create new transaction
- `DELETE /api/transactions/<id>` - Delete transaction
- `GET /api/sub-user/expense-requests` - Get sub-user expense requests
- `POST /api/sub-user/expense-requests` - Create sub-user expense request
- `POST /api/sub-user/expense-requests/<id>/approve` - Approve expense request

## 🎨 UI/UX Features

### Design Principles
- **Professional**: Clean, modern interface suitable for business use
- **Responsive**: Works seamlessly on desktop, tablet, and mobile
- **Intuitive**: Easy-to-use interface with clear navigation
- **Accessible**: Proper contrast ratios and keyboard navigation

### Key UI Components
- **Dashboard Cards**: Summary statistics with visual indicators
- **Data Tables**: Sortable, filterable tables with pagination
- **Modal Forms**: Clean form interfaces for data entry
- **Charts**: Interactive charts for financial visualization
- **Notifications**: Toast notifications for user feedback

## 🔒 Security Features

- **Password Hashing**: Uses Werkzeug's secure password hashing
- **Session Management**: Secure session handling with Flask-Session
- **CSRF Protection**: Built-in CSRF protection
- **Input Validation**: Server-side validation for all inputs
- **SQL Injection Prevention**: Parameterized queries
- **File Upload Security**: Secure file handling with validation

## 📊 Features by User Role

### Main User Features
- ✅ Complete expense and transaction management
- ✅ Sub-user creation and management
- ✅ Request approval/rejection workflow
- ✅ PDF export and reporting
- ✅ Financial analytics and charts
- ✅ Invoice management
- ✅ Bank account management
- ✅ Settings and profile management

### Sub User Features
- ✅ Expense request creation
- ✅ Transaction request creation
- ✅ View approved transactions
- ✅ Personal dashboard
- ✅ Settings management
- 🚧 Invoice management (Coming Soon)

### Admin Features
- ✅ System-wide user management
- ✅ System analytics and reports
- ✅ Database management
- ✅ System configuration

## 🚀 Getting Started Guide

### For New Users

1. **Registration**: Create a new account at `/register`
2. **Login**: Access your dashboard at `/login`
3. **Add Bank Account**: Configure your default bank account in settings
4. **Create Sub-Users**: Add team members as sub-users
5. **Start Tracking**: Begin adding expenses and transactions

### For Sub-Users

1. **Login**: Use your sub-user ID and password
2. **Create Requests**: Submit expense and transaction requests
3. **Track Status**: Monitor approval status of your requests
4. **View History**: Access your approved transactions

## 🔧 Configuration

### Environment Variables
Create a `.env` file for sensitive configuration:
```env
SECRET_KEY=your-secret-key-here
DB_HOST=localhost
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_NAME=expense_tracker
```

### Customization
- **Branding**: Update logo and colors in `static/style.css`
- **Email**: Configure SMTP settings for email notifications
- **File Storage**: Configure cloud storage for file uploads
- **Database**: Modify connection settings in `app.py`

## 🐛 Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Verify MySQL is running
   - Check database credentials in `DB_CONFIG`
   - Ensure database exists

2. **Import Errors**
   - Run `pip install -r requirements.txt`
   - Check Python version compatibility

3. **File Upload Issues**
   - Verify upload directories exist
   - Check file permissions
   - Validate file types and sizes

4. **Session Issues**
   - Clear browser cookies
   - Restart the Flask application
   - Check secret key configuration

## 📈 Performance Optimization

### Database Optimization
- Indexed columns for faster queries
- Connection pooling for better performance
- Optimized queries with proper JOINs

### Frontend Optimization
- Minified CSS and JavaScript
- Optimized images and assets
- Lazy loading for large datasets

### Caching
- Session-based caching
- Static file caching
- Database query optimization

## 🔄 Deployment

### Production Deployment

1. **Server Setup**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Set production environment
   export FLASK_ENV=production
   export FLASK_DEBUG=False
   ```

2. **Database Migration**
   ```bash
   # Run database setup
   python -c "from app import create_tables; create_tables()"
   ```

3. **Web Server Configuration**
   - Use Gunicorn or uWSGI for production
   - Configure Nginx as reverse proxy
   - Set up SSL certificates

### Docker Deployment
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the documentation

## 🔮 Future Enhancements

- [ ] Mobile app development
- [ ] Advanced reporting and analytics
- [ ] Integration with accounting software
- [ ] Multi-currency support
- [ ] Automated expense categorization
- [ ] Email notifications
- [ ] API for third-party integrations
- [ ] Advanced user permissions
- [ ] Audit trail and logging
- [ ] Backup and recovery system

---

**Laitusneo** - Professional Expense Tracking & Invoicing System
