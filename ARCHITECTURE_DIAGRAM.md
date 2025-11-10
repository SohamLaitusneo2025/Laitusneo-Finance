# Monthly Expenses Feature - Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SUB USER INTERFACE                          │
│                    (sub_user_monthly_expenses.html)                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      SUMMARY CARDS                           │  │
│  │  ┌────────────────────┐    ┌──────────────────────────┐     │  │
│  │  │ Current Month      │    │  Yearly Estimate         │     │  │
│  │  │ Total: ৳15,000    │    │  ৳15,000 × 12 = ৳180,000 │     │  │
│  │  └────────────────────┘    └──────────────────────────┘     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   ADD EXPENSE FORM                           │  │
│  │  Expense Name: [____________]  Amount: [_______]            │  │
│  │  Month: [January ▼]  Year: [2025 ▼]                        │  │
│  │  Description: [_________________________________]           │  │
│  │  [+ Add Expense]                                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  EXPENSES LIST                               │  │
│  │  ╔════════════════════════════════════════════════════════╗  │  │
│  │  ║ January 2025                    Total: ৳15,000         ║  │  │
│  │  ╠════════════════════════════════════════════════════════╣  │  │
│  │  ║ Office Rent      ৳10,000    [Delete]                   ║  │  │
│  │  ║ Utilities        ৳5,000     [Delete]                   ║  │  │
│  │  ╚════════════════════════════════════════════════════════╝  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ AJAX Requests
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FLASK BACKEND (app.py)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  PAGE ROUTES                                                 │  │
│  │  • /sub-user-monthly-expenses (GET, POST)                   │  │
│  │    └─ Renders template & handles form submission            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  API ROUTES                                                  │  │
│  │  • GET  /api/sub-user/monthly-expenses                      │  │
│  │    └─ Fetch all expenses + monthly totals                   │  │
│  │                                                              │  │
│  │  • DELETE /api/sub-user/monthly-expenses/<id>               │  │
│  │    └─ Delete specific expense                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ SQL Queries
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      MYSQL DATABASE                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Table: monthly_expenses                                     │  │
│  │  ┌────────────────────────────────────────────────────────┐  │  │
│  │  │ id (PK)              │ 1                                │  │  │
│  │  │ sub_user_id (FK)     │ 5                                │  │  │
│  │  │ expense_name         │ "Office Rent"                    │  │  │
│  │  │ amount               │ 10000.00                         │  │  │
│  │  │ month                │ 1                                │  │  │
│  │  │ year                 │ 2025                             │  │  │
│  │  │ description          │ "Monthly office space rental"    │  │  │
│  │  │ created_at           │ 2025-01-15 10:30:00             │  │  │
│  │  │ updated_at           │ 2025-01-15 10:30:00             │  │  │
│  │  └────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Foreign Key: sub_user_id → sub_users(id) ON DELETE CASCADE        │
│  Index: (sub_user_id, month, year) for fast queries                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagrams

### Adding an Expense
```
User Action           →  Frontend              →  Backend                →  Database
─────────────────────────────────────────────────────────────────────────────────────
1. Fill form          →  Collect form data     →                         →
2. Click "Add"        →  AJAX POST request     →                         →
                      →                         →  Validate session       →
                      →                         →  Extract form data      →
                      →                         →  INSERT query           →  Store expense
                      →                         →  Return success         ←  Confirm insert
                      ←  Receive response       ←                         ←
3. See success msg    ←  Reload expenses       ←                         ←
4. Form resets        ←  Update totals         ←                         ←
```

### Loading Expenses
```
Page Load            →  Frontend              →  Backend                →  Database
─────────────────────────────────────────────────────────────────────────────────────
1. DOM ready         →  Call loadExpenses()   →                         →
                     →  AJAX GET request      →                         →
                     →                         →  Validate session       →
                     →                         →  SELECT expenses        →  Fetch records
                     →                         →  SELECT monthly totals  →  Calculate sums
                     →                         →  Return JSON            ←  Data retrieved
                     ←  Receive data           ←                         ←
2. Display list      ←  Group by month/year   ←                         ←
3. Show totals       ←  Calculate yearly est  ←                         ←
```

### Calculation Logic
```
┌─────────────────────────────────────────────────────────┐
│              CALCULATION FLOW                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Step 1: Get Current Month & Year                      │
│  ┌───────────────────────────────────────────────┐     │
│  │  const currentMonth = new Date().getMonth()+1 │     │
│  │  const currentYear = new Date().getFullYear() │     │
│  └───────────────────────────────────────────────┘     │
│                         │                               │
│                         ▼                               │
│  Step 2: Find Monthly Total                            │
│  ┌───────────────────────────────────────────────┐     │
│  │  SELECT SUM(amount) FROM monthly_expenses     │     │
│  │  WHERE sub_user_id = ? AND                    │     │
│  │        month = ? AND year = ?                 │     │
│  └───────────────────────────────────────────────┘     │
│                         │                               │
│                         ▼                               │
│  Step 3: Calculate Yearly Estimate                     │
│  ┌───────────────────────────────────────────────┐     │
│  │  yearlyTotal = monthlyTotal × 12              │     │
│  └───────────────────────────────────────────────┘     │
│                         │                               │
│                         ▼                               │
│  Step 4: Display Results                               │
│  ┌───────────────────────────────────────────────┐     │
│  │  Current Month Total: ৳15,000                 │     │
│  │  Yearly Estimate: ৳180,000                    │     │
│  └───────────────────────────────────────────────┘     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Security Flow
```
┌────────────────────────────────────────────────────────┐
│              SECURITY CHECKS                           │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Every Request:                                        │
│  1. Check if 'sub_user_id' in session                 │
│     ├─ YES → Continue                                 │
│     └─ NO  → Return 401 Unauthorized                  │
│                                                        │
│  2. For DELETE operations:                            │
│     ├─ Verify expense belongs to sub_user             │
│     │  (WHERE id = ? AND sub_user_id = ?)            │
│     ├─ Match → Delete allowed                         │
│     └─ No match → Return 404 Not Found                │
│                                                        │
│  3. Database Level:                                    │
│     └─ Foreign Key prevents orphaned records          │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

**Created**: November 3, 2025  
**Version**: 1.0
