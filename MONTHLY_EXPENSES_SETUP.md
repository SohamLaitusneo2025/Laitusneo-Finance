# Monthly Expenses Feature - Setup Guide

## Overview
The Monthly Expenses feature allows sub-users to track their recurring monthly expenses and view yearly projections.

## Features
- ✅ Add monthly expenses with name, amount, month, and year
- ✅ View expenses grouped by month and year
- ✅ Automatic calculation of monthly totals
- ✅ Yearly estimate (Monthly total × 12)
- ✅ Delete individual expense entries
- ✅ Responsive design for mobile and desktop
- ✅ Professional UI with gradient styling

## Setup Instructions

### 1. Create the Database Table

You have two options to create the required database table:

#### Option A: Using the Python Script (Recommended)
```bash
python create_monthly_expenses_table.py
```

#### Option B: Using MySQL Command Line or phpMyAdmin
Execute the SQL file `monthly_expenses_table.sql`:
```sql
CREATE TABLE IF NOT EXISTS monthly_expenses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sub_user_id INT NOT NULL,
    expense_name VARCHAR(255) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    month INT NOT NULL,
    year INT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (sub_user_id) REFERENCES sub_users(id) ON DELETE CASCADE,
    INDEX idx_sub_user_month_year (sub_user_id, month, year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 2. Files Modified/Created

#### New Files:
- `templates/sub_user_monthly_expenses.html` - Main template for the monthly expenses page
- `monthly_expenses_table.sql` - SQL script to create the database table
- `create_monthly_expenses_table.py` - Python script to create the table
- `MONTHLY_EXPENSES_SETUP.md` - This setup guide

#### Modified Files:
- `app.py` - Added routes and API endpoints:
  - `/sub-user-monthly-expenses` (GET/POST) - Main page route
  - `/api/sub-user/monthly-expenses` (GET) - Fetch all expenses
  - `/api/sub-user/monthly-expenses/<id>` (DELETE) - Delete an expense
  
- `templates/sub_user_base.html` - Added "Monthly Expenses" link to navigation menu

### 3. How to Use

1. **Access the Feature**:
   - Log in as a sub-user
   - Click on "Monthly Expenses" in the navigation menu

2. **Add a Monthly Expense**:
   - Fill in the expense name (e.g., "Office Rent", "Utilities")
   - Enter the amount
   - Select the month and year
   - Optionally add a description
   - Click "Add Expense"

3. **View Expenses**:
   - Expenses are grouped by month and year
   - Each group shows a total for that month
   - Individual expenses can be deleted

4. **View Summary**:
   - **Current Month Total**: Shows the total expenses for the current month
   - **Yearly Estimate**: Automatically calculates (Current Month Total × 12)

## Database Schema

```sql
monthly_expenses
├── id (INT, PRIMARY KEY, AUTO_INCREMENT)
├── sub_user_id (INT, FOREIGN KEY → sub_users.id)
├── expense_name (VARCHAR(255))
├── amount (DECIMAL(10, 2))
├── month (INT, 1-12)
├── year (INT)
├── description (TEXT, OPTIONAL)
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)
```

## API Endpoints

### GET `/api/sub-user/monthly-expenses`
Fetches all monthly expenses for the logged-in sub-user.

**Response:**
```json
{
  "success": true,
  "expenses": [...],
  "monthly_totals": [...]
}
```

### POST `/sub-user-monthly-expenses`
Adds a new monthly expense.

**Form Data:**
- `expense_name` (required)
- `amount` (required)
- `month` (required, 1-12)
- `year` (required)
- `description` (optional)

### DELETE `/api/sub-user/monthly-expenses/<id>`
Deletes a specific monthly expense.

## Calculations

- **Monthly Total**: Sum of all expenses for a specific month and year
- **Yearly Estimate**: Current month total × 12 months

Example:
- If January 2025 has expenses totaling ৳50,000
- Yearly estimate = ৳50,000 × 12 = ৳600,000

## Security Features

- ✅ Session-based authentication required
- ✅ Sub-users can only access their own expenses
- ✅ Foreign key constraints ensure data integrity
- ✅ SQL injection protection via parameterized queries

## Troubleshooting

### Issue: Table creation fails
**Solution**: Ensure the `sub_users` table exists first, as `monthly_expenses` has a foreign key reference.

### Issue: Navigation link not appearing
**Solution**: Clear your browser cache or do a hard refresh (Ctrl + F5).

### Issue: Expenses not loading
**Solution**: Check browser console for JavaScript errors and ensure the database connection is working.

## Future Enhancements (Possible)

- Export monthly expenses to PDF/Excel
- Edit existing expense entries
- Set recurring expenses automatically
- Compare expenses across different months
- Add expense categories
- Budget alerts when exceeding monthly limits

---

**Created**: November 3, 2025  
**Version**: 1.0
