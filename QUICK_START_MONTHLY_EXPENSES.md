# Monthly Expenses Feature - Quick Start Guide

## 🚀 Quick Setup (3 Steps)

### Step 1: Create the Database Table
Open your terminal in the project directory and run:
```bash
python create_monthly_expenses_table.py
```

**Expected Output:**
```
Creating monthly_expenses table for main users...
✓ Successfully created monthly_expenses table for main users!
```

### Step 2: Start/Restart Your Flask Application
If the app is already running, restart it to load the new routes:
```bash
python app.py
```

### Step 3: Access the Feature
1. Open your browser and navigate to your application
2. Log in as a **main user** (the account owner)
3. Click on **"Monthly Expenses"** in the navigation menu (next to "Sub Users")
4. You're ready to start adding monthly expenses!

---

## 📋 How to Use

### Adding a Monthly Expense

1. Fill in the form fields:
   - **Expense Name**: e.g., "Office Rent", "Internet Bill", "Utilities"
   - **Amount**: Enter the amount in ৳ (Taka)
   - **Month**: Select the month (defaults to current month)
   - **Year**: Select the year (defaults to current year)
   - **Description** (Optional): Add any additional notes

2. Click **"Add Expense"** button

3. The expense will appear in the list below, grouped by month and year

### Viewing Summary

At the top of the page, you'll see two cards:

- **Current Month Total**: Sum of all expenses for the current month
- **Yearly Estimate**: Current month total × 12 months

**Example:**
- If you add ৳10,000 rent + ৳5,000 utilities for January 2025
- Current Month Total = ৳15,000
- Yearly Estimate = ৳15,000 × 12 = ৳180,000

### Deleting an Expense

1. Find the expense in the list
2. Click the **"Delete"** button
3. Confirm the deletion
4. The expense will be removed and totals will update automatically

---

## 🎯 Use Cases

### Scenario 1: Track Fixed Monthly Costs
Add all your recurring monthly expenses:
- Office Rent: ৳50,000
- Internet: ৳2,000
- Utilities: ৳3,000
- Software Subscriptions: ৳5,000

**Result**: See your total monthly overhead and yearly projection

### Scenario 2: Budget Planning
- Add expected expenses for each month
- Compare different months to see variations
- Use the yearly estimate for annual budgeting

### Scenario 3: Expense Reporting
- Track business expenses month by month
- Generate totals for reporting to main user
- Keep descriptions for audit purposes

---

## ⚠️ Troubleshooting

### Problem: "Monthly Expenses" link not showing in navigation
**Solution**: 
- Hard refresh your browser (Ctrl + F5 or Cmd + Shift + R)
- Clear browser cache
- Ensure you're logged in as a main user (not sub-user)

### Problem: Database table creation fails
**Solution**:
- Check that your MySQL password in `create_monthly_expenses_table.py` is correct
- Ensure MySQL server is running
- Verify the `expense_tracker` database exists
- Make sure the `users` table exists (required for foreign key)

### Problem: Can't add expenses / Page shows errors
**Solution**:
- Check browser console (F12) for JavaScript errors
- Verify database table was created successfully
- Ensure Flask app was restarted after adding the new routes
- Check that you're logged in as a main user

---

## 💡 Tips

✅ **Default Values**: The month and year dropdowns default to the current month/year for convenience

✅ **Grouping**: Expenses are automatically grouped by month and year in the display

✅ **Calculation**: The yearly estimate is based on the **current month** total only

✅ **Security**: You can only see and manage your own expenses

✅ **Deletion**: Deleting an expense immediately updates all calculations

---

## 📱 Mobile Access

The page is fully responsive! Access it from:
- Desktop computers
- Tablets
- Mobile phones

The layout automatically adapts to your screen size.

---

## 🔐 Security Notes

- ✅ Must be logged in as a main user to access
- ✅ Cannot see other users' expenses
- ✅ Cannot modify expenses of other users
- ✅ Session-based authentication on all endpoints
- ✅ Database constraints prevent unauthorized access

---

## 📞 Need Help?

If you encounter any issues:
1. Check the browser console (F12) for errors
2. Review the `MONTHLY_EXPENSES_SETUP.md` for detailed setup instructions
3. Verify all files are in place (see `IMPLEMENTATION_SUMMARY.md`)

---

**Version**: 1.0  
**Last Updated**: November 3, 2025
