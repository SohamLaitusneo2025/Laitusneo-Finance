// Banking System JavaScript

let collectionChart = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Get current section from URL
    const urlParams = new URLSearchParams(window.location.search);
    const section = urlParams.get('section') || 'dashboard';
    
    // Load debts for dropdowns (always needed)
    loadDebtsForDropdown();
    
    // Load content based on current section
    switch(section) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'customers':
            loadCustomers();
            break;
        case 'debts':
            loadDebts();
            break;
        case 'emis':
            loadDebtsForEMI();
            // Check if debt_id is in URL and pre-select it
            const debtId = urlParams.get('debt_id');
            if (debtId) {
                setTimeout(() => {
                    const select = document.getElementById('debtSelectForEMI');
                    if (select) {
                        select.value = debtId;
                        loadEMIs();
                    }
                }, 500);
            }
            break;
        case 'reminders':
            loadReminders();
            break;
        case 'reports':
            loadReports();
            break;
        default:
            loadDashboard();
    }
});

// ==================== DASHBOARD ====================

async function loadDashboard() {
    try {
        const response = await fetch('/api/banking/dashboard');
        const data = await response.json();
        
        if (response.ok) {
            const totalOutstandingEl = document.getElementById('totalOutstanding');
            const totalCollectedEl = document.getElementById('totalCollected');
            const activeDebtsEl = document.getElementById('activeDebts');
            const overdueDebtsEl = document.getElementById('overdueDebts');
            
            if (totalOutstandingEl) totalOutstandingEl.textContent = formatCurrency(data.total_outstanding);
            if (totalCollectedEl) totalCollectedEl.textContent = formatCurrency(data.total_collected);
            if (activeDebtsEl) activeDebtsEl.textContent = data.active_debts;
            if (overdueDebtsEl) overdueDebtsEl.textContent = data.overdue_debts;
            
            loadUpcomingPayments();
        } else {
            showError(data.error || 'Failed to load dashboard');
        }
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showError('Failed to load dashboard');
    }
}

async function loadUpcomingPayments() {
    try {
        const response = await fetch('/api/banking/upcoming-payments?days=7');
        const payments = await response.json();
        
        const tbody = document.getElementById('upcomingPaymentsTable');
        if (!tbody) {
            // Table doesn't exist (not on dashboard section), skip
            return;
        }
        
        if (payments.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">No upcoming payments</td></tr>';
            return;
        }
        
        tbody.innerHTML = payments.map(payment => `
            <tr>
                <td>${payment.customer_name || 'N/A'}</td>
                <td>${payment.debt_code || 'N/A'}</td>
                <td>#${payment.installment_number}</td>
                <td>${formatCurrency(payment.amount)}</td>
                <td>${formatDate(payment.due_date)}</td>
                <td><span class="badge bg-warning">Pending</span></td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading upcoming payments:', error);
    }
}

// ==================== CUSTOMERS ====================

async function loadCustomers() {
    try {
        const response = await fetch('/api/banking/customers');
        const customers = await response.json();
        
        // Update statistics cards
        updateCustomerStats(customers);
        
        const tbody = document.getElementById('customersTable');
        if (customers.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">No customers found</td></tr>';
            return;
        }
        
        tbody.innerHTML = customers.map(customer => `
            <tr>
                <td>${customer.customer_code || 'N/A'}</td>
                <td>${customer.name}</td>
                <td>${customer.phone || 'N/A'}</td>
                <td>${customer.email || 'N/A'}</td>
                <td>${formatCurrency(customer.outstanding_balance || 0)}</td>
                <td><span class="badge bg-${customer.status === 'active' ? 'success' : 'secondary'}">${customer.status.toUpperCase()}</span></td>
                <td>
                    <button class="btn btn-sm btn-outline-primary me-1" onclick="editCustomer(${customer.id})" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-${customer.status === 'active' ? 'warning' : 'success'} me-1" onclick="toggleCustomerStatus(${customer.id}, '${customer.status}')" title="${customer.status === 'active' ? 'Deactivate' : 'Activate'}">
                        <i class="fas fa-${customer.status === 'active' ? 'ban' : 'check'}"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteCustomer(${customer.id})" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading customers:', error);
        showError('Failed to load customers');
    }
}

function updateCustomerStats(customers) {
    const totalCustomers = customers.length;
    const activeCustomers = customers.filter(c => c.status === 'active').length;
    const totalOutstanding = customers.reduce((sum, c) => sum + (parseFloat(c.outstanding_balance) || 0), 0);
    const customersWithOutstanding = customers.filter(c => parseFloat(c.outstanding_balance || 0) > 0).length;
    
    document.getElementById('totalCustomers').textContent = totalCustomers;
    document.getElementById('activeCustomers').textContent = activeCustomers;
    document.getElementById('totalOutstandingCustomers').textContent = formatCurrency(totalOutstanding);
    document.getElementById('customersWithOutstanding').textContent = customersWithOutstanding;
}

async function exportCustomers() {
    try {
        const response = await fetch('/api/banking/customers/export');
        if (!response.ok) {
            throw new Error('Export failed');
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `customers_export_${new Date().toISOString().split('T')[0]}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showSuccess('Customers exported successfully');
    } catch (error) {
        console.error('Error exporting customers:', error);
        showError('Failed to export customers');
    }
}

function openCustomerModal(customerId = null) {
    const modal = new bootstrap.Modal(document.getElementById('customerModal'));
    const form = document.getElementById('customerForm');
    form.reset();
    document.getElementById('customerId').value = '';
    
    if (customerId) {
        editCustomer(customerId);
    } else {
        document.getElementById('customerModalTitle').innerHTML = '<i class="fas fa-user-plus me-2"></i>Add Customer';
        modal.show();
    }
}

async function editCustomer(customerId) {
    try {
        const response = await fetch('/api/banking/customers');
        const customers = await response.json();
        const customer = customers.find(c => c.id === customerId);
        
        if (!customer) {
            showError('Customer not found');
            return;
        }
        
        document.getElementById('customerId').value = customer.id;
        document.getElementById('customerName').value = customer.name || '';
        document.getElementById('customerPhone').value = customer.phone || '';
        document.getElementById('customerEmail').value = customer.email || '';
        document.getElementById('customerCode').value = customer.customer_code || '';
        document.getElementById('customerAddress').value = customer.address || '';
        document.getElementById('customerCity').value = customer.city || '';
        document.getElementById('customerState').value = customer.state || '';
        document.getElementById('customerPincode').value = customer.pincode || '';
        document.getElementById('customerPAN').value = customer.pan_number || '';
        document.getElementById('customerAadhar').value = customer.aadhar_number || '';
        document.getElementById('customerNotes').value = customer.notes || '';
        
        document.getElementById('customerModalTitle').innerHTML = '<i class="fas fa-edit me-2"></i>Edit Customer';
        const modal = new bootstrap.Modal(document.getElementById('customerModal'));
        modal.show();
    } catch (error) {
        console.error('Error loading customer:', error);
        showError('Failed to load customer');
    }
}

async function saveCustomer() {
    const form = document.getElementById('customerForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    
    const customerId = document.getElementById('customerId').value;
    const data = {
        name: document.getElementById('customerName').value,
        phone: document.getElementById('customerPhone').value,
        email: document.getElementById('customerEmail').value,
        customer_code: document.getElementById('customerCode').value,
        address: document.getElementById('customerAddress').value,
        city: document.getElementById('customerCity').value,
        state: document.getElementById('customerState').value,
        pincode: document.getElementById('customerPincode').value,
        pan_number: document.getElementById('customerPAN').value,
        aadhar_number: document.getElementById('customerAadhar').value,
        notes: document.getElementById('customerNotes').value,
        status: 'active'
    };
    
    try {
        const url = customerId ? `/api/banking/customers/${customerId}` : '/api/banking/customers';
        const method = customerId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess(result.message || 'Customer saved successfully');
            bootstrap.Modal.getInstance(document.getElementById('customerModal')).hide();
            loadCustomers();
        } else {
            showError(result.error || 'Failed to save customer');
        }
    } catch (error) {
        console.error('Error saving customer:', error);
        showError('Failed to save customer');
    }
}

async function toggleCustomerStatus(customerId, currentStatus) {
    const newStatus = currentStatus === 'active' ? 'inactive' : 'active';
    const action = newStatus === 'active' ? 'activate' : 'deactivate';
    
    if (!confirm(`Are you sure you want to ${action} this customer?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/banking/customers/${customerId}/toggle-status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ status: newStatus })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess(result.message || `Customer ${action}d successfully`);
            loadCustomers();
        } else {
            showError(result.error || `Failed to ${action} customer`);
        }
    } catch (error) {
        console.error(`Error ${action}ing customer:`, error);
        showError(`Failed to ${action} customer`);
    }
}

async function deleteCustomer(customerId) {
    if (!confirm('Are you sure you want to delete this customer?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/banking/customers/${customerId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess(result.message || 'Customer deleted successfully');
            loadCustomers();
        } else {
            showError(result.error || 'Failed to delete customer');
        }
    } catch (error) {
        console.error('Error deleting customer:', error);
        showError('Failed to delete customer');
    }
}

// ==================== DEBTS ====================

async function loadDebts() {
    try {
        const status = document.getElementById('debtStatusFilter')?.value || 'all';
        const url = `/api/banking/debts?status=${status}`;
        const response = await fetch(url);
        const debts = await response.json();
        
        // Update statistics
        updateDebtStats(debts);
        
        const tbody = document.getElementById('debtsTable');
        if (!tbody) return;
        
        if (debts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4">No debts found</td></tr>';
            return;
        }
        
        tbody.innerHTML = debts.map(debt => {
            const statusClass = debt.status === 'active' ? 'success' : debt.status === 'overdue' ? 'danger' : 'secondary';
            return `
                <tr>
                    <td>${debt.debt_code || 'N/A'}</td>
                    <td>${debt.customer_name || 'N/A'}</td>
                    <td>${formatCurrency(debt.total_amount)}</td>
                    <td>${formatCurrency(debt.paid_amount)}</td>
                    <td>${formatCurrency(debt.balance)}</td>
                    <td>${debt.due_date ? formatDate(debt.due_date) : 'N/A'}</td>
                    <td><span class="badge bg-${statusClass}">${debt.status.toUpperCase()}</span></td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary me-1" onclick="viewDebtEMIs(${debt.id})" title="View EMIs">
                            <i class="fas fa-calendar-check"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-info me-1" onclick="recordPaymentForDebt(${debt.id})" title="Record Payment">
                            <i class="fas fa-money-bill-wave"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteDebt(${debt.id})" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading debts:', error);
        showError('Failed to load debts');
    }
}

function updateDebtStats(debts) {
    const totalDebts = debts.length;
    const activeDebts = debts.filter(d => d.status === 'active').length;
    const overdueDebts = debts.filter(d => d.status === 'overdue').length;
    const totalOutstanding = debts.reduce((sum, d) => sum + (parseFloat(d.balance) || 0), 0);
    
    const totalDebtsEl = document.getElementById('totalDebts');
    const totalOutstandingEl = document.getElementById('totalDebtOutstanding');
    const activeDebtsEl = document.getElementById('activeDebtsCount');
    const overdueDebtsEl = document.getElementById('overdueDebtsCount');
    
    if (totalDebtsEl) totalDebtsEl.textContent = totalDebts;
    if (totalOutstandingEl) totalOutstandingEl.textContent = formatCurrency(totalOutstanding);
    if (activeDebtsEl) activeDebtsEl.textContent = activeDebts;
    if (overdueDebtsEl) overdueDebtsEl.textContent = overdueDebts;
}

function toggleDebtSearchSection() {
    const searchSection = document.getElementById('debtSearchSection');
    const toggleBtn = document.getElementById('debtSearchToggleBtn');
    
    if (searchSection && toggleBtn) {
        if (searchSection.style.display === 'none') {
            searchSection.style.display = 'block';
            toggleBtn.classList.add('active');
        } else {
            searchSection.style.display = 'none';
            toggleBtn.classList.remove('active');
        }
    }
}

function searchDebts() {
    const code = document.getElementById('debtSearchCode')?.value || '';
    const customer = document.getElementById('debtSearchCustomer')?.value || '';
    const amount = document.getElementById('debtSearchAmount')?.value || '';
    
    const status = document.getElementById('debtStatusFilter')?.value || 'all';
    let url = `/api/banking/debts?status=${status}`;
    
    const params = [];
    if (code) params.push(`code=${encodeURIComponent(code)}`);
    if (customer) params.push(`customer=${encodeURIComponent(customer)}`);
    if (amount) params.push(`amount=${encodeURIComponent(amount)}`);
    
    if (params.length > 0) {
        url += '&' + params.join('&');
    }
    
    fetch(url)
        .then(response => response.json())
        .then(debts => {
            updateDebtStats(debts);
            const tbody = document.getElementById('debtsTable');
            if (!tbody) return;
            
            if (debts.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4">No debts found</td></tr>';
                return;
            }
            
            tbody.innerHTML = debts.map(debt => {
                const statusClass = debt.status === 'active' ? 'success' : debt.status === 'overdue' ? 'danger' : 'secondary';
                return `
                    <tr>
                        <td>${debt.debt_code || 'N/A'}</td>
                        <td>${debt.customer_name || 'N/A'}</td>
                        <td>${formatCurrency(debt.total_amount)}</td>
                        <td>${formatCurrency(debt.paid_amount)}</td>
                        <td>${formatCurrency(debt.balance)}</td>
                        <td>${debt.due_date ? formatDate(debt.due_date) : 'N/A'}</td>
                        <td><span class="badge bg-${statusClass}">${debt.status.toUpperCase()}</span></td>
                        <td>
                            <button class="btn btn-sm btn-outline-primary me-1" onclick="viewDebtEMIs(${debt.id})" title="View EMIs">
                                <i class="fas fa-calendar-check"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-info me-1" onclick="recordPaymentForDebt(${debt.id})" title="Record Payment">
                                <i class="fas fa-money-bill-wave"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteDebt(${debt.id})" title="Delete">
                                <i class="fas fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');
        })
        .catch(error => {
            console.error('Error searching debts:', error);
            showError('Failed to search debts');
        });
}

function clearDebtSearch() {
    document.getElementById('debtSearchCode').value = '';
    document.getElementById('debtSearchCustomer').value = '';
    document.getElementById('debtSearchAmount').value = '';
    loadDebts();
}

async function loadDebtsForDropdown() {
    try {
        const response = await fetch('/api/banking/debts?status=all');
        const debts = await response.json();
        
        const select = document.getElementById('paymentDebtId');
        if (select) {
            select.innerHTML = '<option value="">Select Debt</option>' + 
                debts.map(debt => `<option value="${debt.id}" data-customer-id="${debt.customer_id}" data-customer-name="${debt.customer_name || ''}">${debt.debt_code} - ${debt.customer_name} (Balance: ${formatCurrency(debt.balance)})</option>`).join('');
        }
        
        const reminderSelect = document.getElementById('reminderDebtId');
        if (reminderSelect) {
            reminderSelect.innerHTML = '<option value="">Select Debt</option>' + 
                debts.map(debt => `<option value="${debt.id}" data-customer-id="${debt.customer_id}" data-customer-name="${debt.customer_name || ''}">${debt.debt_code} - ${debt.customer_name}</option>`).join('');
        }
    } catch (error) {
        console.error('Error loading debts for dropdown:', error);
    }
}

function openDebtModal() {
    const modal = new bootstrap.Modal(document.getElementById('debtModal'));
    const form = document.getElementById('debtForm');
    form.reset();
    document.getElementById('debtId').value = '';
    document.getElementById('debtEMIEnabled').checked = false;
    toggleEMIFields();
    
    // Load customers
    loadCustomersForDebt();
    
    // Set today's date
    document.getElementById('debtStartDate').value = new Date().toISOString().split('T')[0];
    
    document.getElementById('debtModalTitle').innerHTML = '<i class="fas fa-file-invoice-dollar me-2"></i>Add Debt';
    modal.show();
}

async function loadCustomersForDebt() {
    try {
        const response = await fetch('/api/banking/customers');
        const customers = await response.json();
        
        const select = document.getElementById('debtCustomerId');
        select.innerHTML = '<option value="">Select Customer</option>' + 
            customers.map(c => `<option value="${c.id}">${c.name} (${c.customer_code || 'N/A'})</option>`).join('');
    } catch (error) {
        console.error('Error loading customers:', error);
    }
}

function toggleEMIFields() {
    const enabled = document.getElementById('debtEMIEnabled').checked;
    document.getElementById('emiCountField').style.display = enabled ? 'block' : 'none';
    document.getElementById('emiAmountField').style.display = enabled ? 'block' : 'none';
    if (enabled) {
        updateEMICalculation();
    }
}

function updateEMICalculation() {
    const enabled = document.getElementById('debtEMIEnabled').checked;
    if (!enabled) return;
    
    const totalAmount = parseFloat(document.getElementById('debtTotalAmount').value) || 0;
    const emiCount = parseInt(document.getElementById('debtEMICount').value) || 0;
    
    if (emiCount > 0 && totalAmount > 0) {
        const emiAmount = totalAmount / emiCount;
        document.getElementById('debtEMIAmount').value = emiAmount.toFixed(2);
    }
}

async function saveDebt() {
    const form = document.getElementById('debtForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    
    const debtId = document.getElementById('debtId').value;
    const emiEnabled = document.getElementById('debtEMIEnabled').checked;
    
    const data = {
        customer_id: parseInt(document.getElementById('debtCustomerId').value),
        total_amount: parseFloat(document.getElementById('debtTotalAmount').value),
        interest_rate: parseFloat(document.getElementById('debtInterestRate').value) || 0,
        due_date: document.getElementById('debtDueDate').value || null,
        start_date: document.getElementById('debtStartDate').value,
        loan_purpose: document.getElementById('debtLoanPurpose').value,
        notes: document.getElementById('debtNotes').value,
        emi_enabled: emiEnabled,
        emi_count: emiEnabled ? parseInt(document.getElementById('debtEMICount').value) : 0
    };
    
    try {
        const url = debtId ? `/api/banking/debts/${debtId}` : '/api/banking/debts';
        const method = debtId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess(result.message || 'Debt saved successfully');
            bootstrap.Modal.getInstance(document.getElementById('debtModal')).hide();
            loadDebts();
            loadDebtsForDropdown();
        } else {
            showError(result.error || 'Failed to save debt');
        }
    } catch (error) {
        console.error('Error saving debt:', error);
        showError('Failed to save debt');
    }
}

async function deleteDebt(debtId) {
    if (!confirm('Are you sure you want to delete this debt?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/banking/debts/${debtId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess(result.message || 'Debt deleted successfully');
            loadDebts();
            loadDebtsForDropdown();
        } else {
            showError(result.error || 'Failed to delete debt');
        }
    } catch (error) {
        console.error('Error deleting debt:', error);
        showError('Failed to delete debt');
    }
}

// ==================== PAYMENTS ====================
// Note: Payments section has been removed, but keeping function for backward compatibility

async function loadPayments() {
    // Payments section removed - function kept for backward compatibility
    // No-op to prevent errors
    return;
}

function openPaymentModal() {
    const modal = new bootstrap.Modal(document.getElementById('paymentModal'));
    const form = document.getElementById('paymentForm');
    form.reset();
    document.getElementById('paymentEMIId').innerHTML = '<option value="">Select EMI (if applicable)</option>';
    document.getElementById('paymentDate').value = new Date().toISOString().split('T')[0];
    
    loadDebtsForDropdown();
    modal.show();
}

async function loadDebtEMIs() {
    const debtId = document.getElementById('paymentDebtId').value;
    const customerSelect = document.getElementById('paymentDebtId');
    const selectedOption = customerSelect.options[customerSelect.selectedIndex];
    
    if (selectedOption) {
        document.getElementById('paymentCustomerId').value = selectedOption.getAttribute('data-customer-id') || '';
        document.getElementById('paymentCustomerName').value = selectedOption.getAttribute('data-customer-name') || '';
    }
    
    if (!debtId) {
        document.getElementById('paymentEMIId').innerHTML = '<option value="">Select EMI (if applicable)</option>';
        return;
    }
    
    try {
        const response = await fetch(`/api/banking/debts/${debtId}/emis`);
        const emis = await response.json();
        
        const select = document.getElementById('paymentEMIId');
        select.innerHTML = '<option value="">Select EMI (if applicable)</option>' + 
            emis.filter(emi => emi.status !== 'paid').map(emi => 
                `<option value="${emi.id}">Installment #${emi.installment_number} - ${formatCurrency(emi.amount - emi.paid_amount)} remaining (Due: ${formatDate(emi.due_date)})</option>`
            ).join('');
    } catch (error) {
        console.error('Error loading EMIs:', error);
    }
}

function recordPaymentForDebt(debtId) {
    openPaymentModal();
    setTimeout(() => {
        document.getElementById('paymentDebtId').value = debtId;
        loadDebtEMIs();
    }, 300);
}

async function savePayment() {
    const form = document.getElementById('paymentForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    
    const data = {
        debt_id: parseInt(document.getElementById('paymentDebtId').value),
        customer_id: parseInt(document.getElementById('paymentCustomerId').value),
        emi_id: document.getElementById('paymentEMIId').value ? parseInt(document.getElementById('paymentEMIId').value) : null,
        amount: parseFloat(document.getElementById('paymentAmount').value),
        payment_method: document.getElementById('paymentMethod').value,
        payment_date: document.getElementById('paymentDate').value,
        transaction_id: document.getElementById('paymentTransactionId').value,
        receipt_number: document.getElementById('paymentReceiptNumber').value,
        remarks: document.getElementById('paymentRemarks').value
    };
    
    try {
        const response = await fetch('/api/banking/payments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess(result.message || 'Payment recorded successfully');
            bootstrap.Modal.getInstance(document.getElementById('paymentModal')).hide();
            loadPayments();
            loadDebts();
            loadDashboard();
        } else {
            showError(result.error || 'Failed to record payment');
        }
    } catch (error) {
        console.error('Error recording payment:', error);
        showError('Failed to record payment');
    }
}

function viewPaymentReceipt(paymentId) {
    // TODO: Implement receipt generation
    alert('Receipt generation coming soon!');
}

// ==================== EMIs ====================

async function loadDebtsForEMI() {
    try {
        const response = await fetch('/api/banking/debts?status=all');
        const debts = await response.json();
        
        const select = document.getElementById('debtSelectForEMI');
        select.innerHTML = '<option value="">Select a debt to view EMIs</option>' + 
            debts.map(debt => `<option value="${debt.id}">${debt.debt_code} - ${debt.customer_name} (${formatCurrency(debt.balance)} remaining)</option>`).join('');
    } catch (error) {
        console.error('Error loading debts for EMI:', error);
    }
}

async function loadEMIs() {
    const debtId = document.getElementById('debtSelectForEMI').value;
    
    if (!debtId) {
        document.getElementById('emisTable').innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Select a debt to view EMIs</td></tr>';
        document.getElementById('emiStatsCards').style.display = 'none';
        document.getElementById('selectedDebtInfo').style.display = 'none';
        return;
    }
    
    try {
        // Load debt info
        const debtResponse = await fetch(`/api/banking/debts?status=all`);
        const debts = await debtResponse.json();
        const selectedDebt = debts.find(d => d.id == debtId);
        
        if (selectedDebt) {
            document.getElementById('selectedDebtCode').textContent = selectedDebt.debt_code || 'N/A';
            document.getElementById('selectedDebtCustomer').textContent = selectedDebt.customer_name || 'N/A';
            document.getElementById('selectedDebtAmount').textContent = formatCurrency(selectedDebt.total_amount);
            document.getElementById('selectedDebtBalance').textContent = formatCurrency(selectedDebt.balance);
            document.getElementById('selectedDebtInfo').style.display = 'block';
        }
        
        // Load EMIs
        const response = await fetch(`/api/banking/debts/${debtId}/emis`);
        const emis = await response.json();
        
        // Update statistics
        updateEMIStats(emis);
        document.getElementById('emiStatsCards').style.display = 'flex';
        
        // Store original EMIs for search filtering
        window.currentEMIs = emis;
        
        // Display EMIs
        displayEMIs(emis);
    } catch (error) {
        console.error('Error loading EMIs:', error);
        showError('Failed to load EMIs');
    }
}

function updateEMIStats(emis) {
    const totalEMIs = emis.length;
    const paidEMIs = emis.filter(e => e.status === 'paid').length;
    const pendingEMIs = emis.filter(e => e.status === 'pending' || e.status === 'partial').length;
    const pendingAmount = emis
        .filter(e => e.status === 'pending' || e.status === 'partial')
        .reduce((sum, e) => sum + (parseFloat(e.amount) - parseFloat(e.paid_amount || 0)), 0);
    
    const totalEMIsEl = document.getElementById('totalEMIs');
    const paidEMIsEl = document.getElementById('paidEMIs');
    const pendingEMIsEl = document.getElementById('pendingEMIs');
    const pendingAmountEl = document.getElementById('pendingEMIAmount');
    
    if (totalEMIsEl) totalEMIsEl.textContent = totalEMIs;
    if (paidEMIsEl) paidEMIsEl.textContent = paidEMIs;
    if (pendingEMIsEl) pendingEMIsEl.textContent = pendingEMIs;
    if (pendingAmountEl) pendingAmountEl.textContent = formatCurrency(pendingAmount);
}

function displayEMIs(emis) {
    const tbody = document.getElementById('emisTable');
    if (!tbody) return;
    
    if (emis.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">No EMIs found for this debt</td></tr>';
        return;
    }
    
    tbody.innerHTML = emis.map(emi => {
        const statusClass = emi.status === 'paid' ? 'success' : emi.status === 'overdue' ? 'danger' : emi.status === 'partial' ? 'info' : 'warning';
        const balance = parseFloat(emi.amount) - parseFloat(emi.paid_amount || 0);
        const hasPayment = emi.status === 'paid' || emi.status === 'partial';
        return `
            <tr>
                <td>#${emi.installment_number}</td>
                <td>${formatDate(emi.due_date)}</td>
                <td>${formatCurrency(emi.amount)}</td>
                <td>${formatCurrency(emi.paid_amount || 0)}</td>
                <td>${formatCurrency(balance)}</td>
                <td><span class="badge bg-${statusClass}">${emi.status.toUpperCase()}</span></td>
                <td>
                    <div class="d-flex gap-1">
                        ${emi.status !== 'paid' ? `<button class="btn btn-sm btn-outline-primary" onclick="recordPaymentForEMI(${emi.id}, ${emi.debt_id})" title="Record Payment">
                            <i class="fas fa-money-bill-wave"></i>
                        </button>` : ''}
                        ${hasPayment ? `<button class="btn btn-sm btn-outline-success" onclick="generateEMIReceipt(${emi.id})" title="Generate Receipt">
                            <i class="fas fa-receipt"></i>
                        </button>` : ''}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

async function generateEMIReceipt(emiId) {
    try {
        // Open receipt in new window
        const receiptUrl = `/api/receipt/emi/${emiId}`;
        window.open(receiptUrl, '_blank');
    } catch (error) {
        console.error('Error generating receipt:', error);
        showError('Failed to generate receipt');
    }
}

function toggleEMISearchSection() {
    const searchSection = document.getElementById('emiSearchSection');
    const toggleBtn = document.getElementById('emiSearchToggleBtn');
    
    if (searchSection && toggleBtn) {
        if (searchSection.style.display === 'none') {
            searchSection.style.display = 'block';
            toggleBtn.classList.add('active');
        } else {
            searchSection.style.display = 'none';
            toggleBtn.classList.remove('active');
        }
    }
}

function searchEMIs() {
    const installment = document.getElementById('emiSearchInstallment')?.value || '';
    const status = document.getElementById('emiSearchStatus')?.value || '';
    
    if (!window.currentEMIs) {
        showError('Please select a debt first');
        return;
    }
    
    let filteredEMIs = [...window.currentEMIs];
    
    if (installment) {
        filteredEMIs = filteredEMIs.filter(e => e.installment_number == installment);
    }
    
    if (status) {
        filteredEMIs = filteredEMIs.filter(e => e.status === status);
    }
    
    updateEMIStats(filteredEMIs);
    displayEMIs(filteredEMIs);
}

function clearEMISearch() {
    document.getElementById('emiSearchInstallment').value = '';
    document.getElementById('emiSearchStatus').value = '';
    if (window.currentEMIs) {
        updateEMIStats(window.currentEMIs);
        displayEMIs(window.currentEMIs);
    }
}

function viewDebtEMIs(debtId) {
    // Navigate to EMIs section with the debt pre-selected
    window.location.href = `/banking?section=emis&debt_id=${debtId}`;
}

function recordPaymentForEMI(emiId, debtId) {
    recordPaymentForDebt(debtId);
    setTimeout(() => {
        document.getElementById('paymentEMIId').value = emiId;
    }, 500);
}

// ==================== REMINDERS ====================

async function loadReminders() {
    try {
        const response = await fetch('/api/banking/reminders');
        const reminders = await response.json();
        
        // Store original reminders for search filtering
        window.currentReminders = reminders;
        
        // Apply filters
        let filteredReminders = [...reminders];
        
        // Status filter
        const statusFilter = document.getElementById('reminderStatusFilter')?.value || 'all';
        if (statusFilter !== 'all') {
            filteredReminders = filteredReminders.filter(r => {
                if (statusFilter === 'sent') return r.sent;
                if (statusFilter === 'pending') return !r.sent;
                return true;
            });
        }
        
        // Type filter
        const typeFilter = document.getElementById('reminderTypeFilter')?.value || 'all';
        if (typeFilter !== 'all') {
            filteredReminders = filteredReminders.filter(r => r.reminder_type === typeFilter);
        }
        
        // Update statistics
        updateReminderStats(reminders);
        
        // Display reminders
        displayReminders(filteredReminders);
    } catch (error) {
        console.error('Error loading reminders:', error);
        showError('Failed to load reminders');
    }
}

function updateReminderStats(reminders) {
    const totalReminders = reminders.length;
    const pendingReminders = reminders.filter(r => !r.sent).length;
    const sentReminders = reminders.filter(r => r.sent).length;
    
    // Count due today reminders
    const today = new Date().toISOString().split('T')[0];
    const dueTodayReminders = reminders.filter(r => {
        if (!r.scheduled_date) return false;
        const scheduledDate = r.scheduled_date.split('T')[0];
        return scheduledDate === today && !r.sent;
    }).length;
    
    const totalEl = document.getElementById('totalReminders');
    const pendingEl = document.getElementById('pendingReminders');
    const sentEl = document.getElementById('sentReminders');
    const dueTodayEl = document.getElementById('dueTodayReminders');
    
    if (totalEl) totalEl.textContent = totalReminders;
    if (pendingEl) pendingEl.textContent = pendingReminders;
    if (sentEl) sentEl.textContent = sentReminders;
    if (dueTodayEl) dueTodayEl.textContent = dueTodayReminders;
}

function displayReminders(reminders) {
    const tbody = document.getElementById('remindersTable');
    if (!tbody) return;
    
    if (reminders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">No reminders found</td></tr>';
        return;
    }
    
    tbody.innerHTML = reminders.map(reminder => {
        // Format reminder type badge
        const typeClass = reminder.reminder_type === 'overdue' ? 'danger' : 
                         reminder.reminder_type === 'due_today' ? 'warning' : 
                         reminder.reminder_type === 'upcoming_due' ? 'info' : 'secondary';
        const typeText = reminder.reminder_type.replace('_', ' ').toUpperCase();
        
        // Format channel badge
        const channelText = reminder.channel ? reminder.channel.replace('_', ' ').toUpperCase() : 'N/A';
        
        return `
            <tr>
                <td>${reminder.customer_name || 'N/A'}</td>
                <td>${reminder.debt_code || 'N/A'}</td>
                <td><span class="badge bg-${typeClass}">${typeText}</span></td>
                <td>${formatDate(reminder.scheduled_date)}</td>
                <td><span class="badge bg-secondary">${channelText}</span></td>
                <td><span class="badge bg-${reminder.sent ? 'success' : 'warning'}">${reminder.sent ? 'SENT' : 'PENDING'}</span></td>
                <td>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteReminder(${reminder.id})" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function toggleReminderSearchSection() {
    const searchSection = document.getElementById('reminderSearchSection');
    const toggleBtn = document.getElementById('reminderSearchToggleBtn');
    
    if (searchSection && toggleBtn) {
        if (searchSection.style.display === 'none') {
            searchSection.style.display = 'block';
            toggleBtn.classList.add('active');
        } else {
            searchSection.style.display = 'none';
            toggleBtn.classList.remove('active');
        }
    }
}

function searchReminders() {
    const customer = document.getElementById('reminderSearchCustomer')?.value.toLowerCase() || '';
    const debtCode = document.getElementById('reminderSearchDebtCode')?.value.toLowerCase() || '';
    const date = document.getElementById('reminderSearchDate')?.value || '';
    
    if (!window.currentReminders) {
        showError('Please wait for reminders to load');
        return;
    }
    
    let filteredReminders = [...window.currentReminders];
    
    // Apply existing filters first
    const statusFilter = document.getElementById('reminderStatusFilter')?.value || 'all';
    if (statusFilter !== 'all') {
        filteredReminders = filteredReminders.filter(r => {
            if (statusFilter === 'sent') return r.sent;
            if (statusFilter === 'pending') return !r.sent;
            return true;
        });
    }
    
    const typeFilter = document.getElementById('reminderTypeFilter')?.value || 'all';
    if (typeFilter !== 'all') {
        filteredReminders = filteredReminders.filter(r => r.reminder_type === typeFilter);
    }
    
    // Apply search filters
    if (customer) {
        filteredReminders = filteredReminders.filter(r => 
            (r.customer_name || '').toLowerCase().includes(customer)
        );
    }
    
    if (debtCode) {
        filteredReminders = filteredReminders.filter(r => 
            (r.debt_code || '').toLowerCase().includes(debtCode)
        );
    }
    
    if (date) {
        filteredReminders = filteredReminders.filter(r => {
            if (!r.scheduled_date) return false;
            const scheduledDate = r.scheduled_date.split('T')[0];
            return scheduledDate === date;
        });
    }
    
    displayReminders(filteredReminders);
}

function clearReminderSearch() {
    document.getElementById('reminderSearchCustomer').value = '';
    document.getElementById('reminderSearchDebtCode').value = '';
    document.getElementById('reminderSearchDate').value = '';
    loadReminders();
}

function openReminderModal() {
    const modal = new bootstrap.Modal(document.getElementById('reminderModal'));
    const form = document.getElementById('reminderForm');
    form.reset();
    document.getElementById('reminderEMIId').innerHTML = '<option value="">Select EMI (if applicable)</option>';
    document.getElementById('reminderScheduledDate').value = new Date().toISOString().split('T')[0];
    
    loadDebtsForDropdown();
    modal.show();
}

async function loadReminderEMIs() {
    const debtId = document.getElementById('reminderDebtId').value;
    const customerSelect = document.getElementById('reminderDebtId');
    const selectedOption = customerSelect.options[customerSelect.selectedIndex];
    
    if (selectedOption) {
        document.getElementById('reminderCustomerId').value = selectedOption.getAttribute('data-customer-id') || '';
        document.getElementById('reminderCustomerName').value = selectedOption.getAttribute('data-customer-name') || '';
    }
    
    if (!debtId) {
        document.getElementById('reminderEMIId').innerHTML = '<option value="">Select EMI (if applicable)</option>';
        return;
    }
    
    try {
        const response = await fetch(`/api/banking/debts/${debtId}/emis`);
        const emis = await response.json();
        
        const select = document.getElementById('reminderEMIId');
        select.innerHTML = '<option value="">Select EMI (if applicable)</option>' + 
            emis.map(emi => 
                `<option value="${emi.id}">Installment #${emi.installment_number} - ${formatCurrency(emi.amount)} (Due: ${formatDate(emi.due_date)})</option>`
            ).join('');
    } catch (error) {
        console.error('Error loading EMIs:', error);
    }
}

async function saveReminder() {
    const form = document.getElementById('reminderForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    
    const data = {
        debt_id: parseInt(document.getElementById('reminderDebtId').value),
        customer_id: parseInt(document.getElementById('reminderCustomerId').value),
        emi_id: document.getElementById('reminderEMIId').value ? parseInt(document.getElementById('reminderEMIId').value) : null,
        reminder_type: document.getElementById('reminderType').value,
        scheduled_date: document.getElementById('reminderScheduledDate').value,
        channel: document.getElementById('reminderChannel').value,
        subject: document.getElementById('reminderSubject').value,
        message: document.getElementById('reminderMessage').value
    };
    
    try {
        const response = await fetch('/api/banking/reminders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess(result.message || 'Reminder created successfully');
            bootstrap.Modal.getInstance(document.getElementById('reminderModal')).hide();
            loadReminders();
        } else {
            showError(result.error || 'Failed to create reminder');
        }
    } catch (error) {
        console.error('Error creating reminder:', error);
        showError('Failed to create reminder');
    }
}

async function deleteReminder(reminderId) {
    if (!confirm('Are you sure you want to delete this reminder?')) {
        return;
    }
    
    // TODO: Implement delete reminder API
    showError('Delete reminder functionality coming soon!');
}

// ==================== REPORTS ====================

async function loadReports() {
    try {
        const response = await fetch('/api/banking/dashboard');
        const data = await response.json();
        
        if (response.ok && data.monthly_trend) {
            drawCollectionChart(data.monthly_trend);
        }
    } catch (error) {
        console.error('Error loading reports:', error);
    }
}

function drawCollectionChart(monthlyTrend) {
    const ctx = document.getElementById('collectionChart');
    if (!ctx) return;
    
    const labels = monthlyTrend.map(item => item.month);
    const data = monthlyTrend.map(item => item.collected);
    
    if (collectionChart) {
        collectionChart.destroy();
    }
    
    collectionChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Collection (₹)',
                data: data,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '₹' + value.toLocaleString('en-IN');
                        }
                    }
                }
            }
        }
    });
}

// ==================== UTILITY FUNCTIONS ====================

function formatCurrency(amount) {
    return '₹' + parseFloat(amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' });
}

function showSuccess(message) {
    // Use existing toast/notification system if available
    if (typeof showNotification === 'function') {
        showNotification(message, 'success');
    } else {
        alert(message);
    }
}

function showError(message) {
    // Use existing toast/notification system if available
    if (typeof showNotification === 'function') {
        showNotification(message, 'error');
    } else {
        alert(message);
    }
}

