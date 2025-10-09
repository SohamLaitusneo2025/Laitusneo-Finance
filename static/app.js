/**
 * Expense Tracker - Main JavaScript File
 * Contains common functions and utilities used across the application
 */

// Global variables
let currentUser = null;
let appSettings = {
    currency: 'INR',
    dateFormat: 'DD/MM/YYYY',
    theme: 'light'
};

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupGlobalEventListeners();
    updateActiveNavigation();
});

/**
 * Initialize the application
 */
function initializeApp() {
    // Load user preferences
    loadUserPreferences();
    
    // Setup tooltips
    setupTooltips();
    
    // Setup theme
    applyTheme();
    
    // Setup global error handlers
    setupErrorHandlers();
}

/**
 * Setup global event listeners
 */
function setupGlobalEventListeners() {
    // Handle form submissions with loading states
    document.addEventListener('submit', function(e) {
        if (e.target.classList.contains('form-with-loading')) {
            handleFormSubmission(e);
        }
    });
    
    // Handle file uploads with drag and drop
    setupFileUploadHandlers();
    
    // Handle keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        handleKeyboardShortcuts(e);
    });
    
    // Auto-hide alerts after 5 seconds
    document.addEventListener('DOMContentLoaded', function() {
        setTimeout(() => {
            document.querySelectorAll('.alert').forEach(alert => {
                if (alert.querySelector('.btn-close')) {
                    alert.style.opacity = '0';
                    setTimeout(() => alert.remove(), 300);
                }
            });
        }, 5000);
    });
}

/**
 * Update active navigation item based on current page
 */
function updateActiveNavigation() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
}

/**
 * Setup Bootstrap tooltips
 */
function setupTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Load user preferences from localStorage
 */
function loadUserPreferences() {
    const savedSettings = localStorage.getItem('expenseTrackerSettings');
    if (savedSettings) {
        try {
            const settings = JSON.parse(savedSettings);
            appSettings = { ...appSettings, ...settings };
        } catch (error) {
            console.error('Error loading user preferences:', error);
        }
    }
}

/**
 * Apply current theme
 */
function applyTheme() {
    document.body.setAttribute('data-theme', appSettings.theme);
}

/**
 * Setup error handlers
 */
function setupErrorHandlers() {
    window.addEventListener('error', function(e) {
        console.error('Global error:', e.error);
        
        // Check if it's a JSON parsing error (likely authentication issue)
        if (e.error && e.error.message && e.error.message.includes('JSON')) {
            console.log('JSON parsing error detected - likely authentication issue');
            // Don't show notification for JSON parsing errors, let the page handle it
            return;
        }
        
        showNotification('An unexpected error occurred. Please try again.', 'error');
    });
    
    window.addEventListener('unhandledrejection', function(e) {
        console.error('Unhandled promise rejection:', e.reason);
        
        // Check if it's a network error or authentication issue
        if (e.reason && (e.reason.message && e.reason.message.includes('401')) || 
            (e.reason && e.reason.status === 401)) {
            console.log('Authentication error detected - redirecting to login');
            window.location.href = '/login';
            return;
        }
        
        showNotification('An unexpected error occurred. Please try again.', 'error');
    });
}

/**
 * Handle form submission with loading states
 */
function handleFormSubmission(e) {
    const form = e.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    
    if (submitBtn) {
        setButtonLoading(submitBtn, true);
        
        // Re-enable after 5 seconds as fallback
        setTimeout(() => {
            setButtonLoading(submitBtn, false);
        }, 5000);
    }
}

/**
 * Setup file upload handlers
 */
function setupFileUploadHandlers() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    
    fileInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                showNotification(`File "${file.name}" selected successfully!`, 'success');
            }
        });
    });
}

/**
 * Handle keyboard shortcuts
 */
function handleKeyboardShortcuts(e) {
    // Ctrl/Cmd + S to save
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        const activeForm = document.querySelector('form:focus-within');
        if (activeForm) {
            activeForm.dispatchEvent(new Event('submit'));
        }
    }
    
    // Escape to close modals
    if (e.key === 'Escape') {
        const openModal = document.querySelector('.modal.show');
        if (openModal) {
            const modal = bootstrap.Modal.getInstance(openModal);
            if (modal) modal.hide();
        }
    }
}

/**
 * Show notification toast
 */
function showNotification(message, type = 'info', duration = 5000) {
    const alertClass = `alert-${type === 'error' ? 'danger' : type}`;
    const icon = getNotificationIcon(type);
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert ${alertClass} alert-dismissible fade show notification-toast`;
    alertDiv.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="${icon} me-3" style="font-size: 1.2rem;"></i>
            <div class="flex-grow-1">
                <div class="fw-semibold">${message}</div>
            </div>
            <button type="button" class="btn-close ms-2" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    
    document.body.appendChild(alertDiv);
    
    // Auto remove after duration
    if (duration > 0) {
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.classList.remove('show');
                setTimeout(() => alertDiv.remove(), 150);
            }
        }, duration);
    }
    
    return alertDiv;
}

/**
 * Get icon for notification type
 */
function getNotificationIcon(type) {
    const icons = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-circle',
        warning: 'fas fa-exclamation-triangle',
        info: 'fas fa-info-circle'
    };
    return icons[type] || icons.info;
}

/**
 * Format date
 */
function formatDate(date, format = appSettings.dateFormat) {
    const d = new Date(date);
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();
    
    if (format === 'DD/MM/YYYY') {
        return `${day}/${month}/${year}`;
    } else if (format === 'MM/DD/YYYY') {
        return `${month}/${day}/${year}`;
    } else {
        return d.toLocaleDateString();
    }
}

/**
 * Format file size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Validate form
 */
function validateForm(form) {
    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

/**
 * Validate email
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Export data to CSV
 */
function exportToCSV(data, filename) {
    const csvContent = "data:text/csv;charset=utf-8," + data;
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/**
 * Set button loading state
 */
function setButtonLoading(button, loading) {
    if (loading) {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Loading...';
    } else {
        button.disabled = false;
        button.innerHTML = button.getAttribute('data-original-text') || 'Submit';
    }
}

/**
 * Show inline loading
 */
function showInlineLoading(element) {
    element.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div>';
}

/**
 * Hide inline loading
 */
function hideInlineLoading(element, originalContent) {
    element.innerHTML = originalContent;
}

/**
 * Show card loading
 */
function showCardLoading(card) {
    card.classList.add('loading');
}

/**
 * Hide card loading
 */
function hideCardLoading(card) {
    card.classList.remove('loading');
}

/**
 * Copy text to clipboard
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard!', 'success');
    }).catch(() => {
        showNotification('Failed to copy to clipboard', 'error');
    });
}

/**
 * Generate unique ID
 */
function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

/**
 * Deep clone object
 */
function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

/**
 * Check if device is mobile
 */
function isMobileDevice() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

/**
 * Debounce function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Setup debounced search
 */
function setupDebouncedSearch(input, callback, delay = 300) {
    const debouncedCallback = debounce(callback, delay);
    input.addEventListener('input', debouncedCallback);
}

/**
 * Enhanced delete confirmation with modal
 */
function showDeleteConfirmation(message, itemType, onConfirm) {
    const modal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
    const messageElement = document.getElementById('deleteMessage');
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    
    // Set custom message
    messageElement.textContent = message || `Are you sure you want to delete this ${itemType}?`;
    
    // Remove any existing event listeners
    const newConfirmBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
    
    // Add new event listener
    newConfirmBtn.addEventListener('click', async function() {
        setButtonLoading(newConfirmBtn, true);
        
        try {
            await onConfirm();
            modal.hide();
        } catch (error) {
            console.error('Delete operation failed:', error);
        } finally {
            setButtonLoading(newConfirmBtn, false);
        }
    });
    
    modal.show();
}

/**
 * Enhanced delete function for any item type
 */
async function deleteItem(id, itemType, endpoint, onSuccess) {
    return new Promise((resolve, reject) => {
        showDeleteConfirmation(
            `Are you sure you want to delete this ${itemType}?`,
            itemType,
            async () => {
                try {
                    const response = await axios.delete(`${endpoint}/${id}`);
                    
                    if (response.data.success) {
                        showNotification(`${itemType} deleted successfully!`, 'success');
                        if (onSuccess) await onSuccess();
                        resolve(response.data);
                    } else {
                        throw new Error(response.data.error || 'Unknown error');
                    }
                } catch (error) {
                    const errorMessage = `Error deleting ${itemType}: ${error.response?.data?.error || error.message}`;
                    showNotification(errorMessage, 'error');
                    reject(error);
                }
            }
        );
    });
}

/**
 * Format number with commas
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Format currency with symbol
 */
function formatCurrency(amount, currencySymbol = '₹') {
    const num = parseFloat(amount) || 0;
    return `${currencySymbol}${num.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}`;
}

/**
 * Format date string
 */
function formatDate(dateString, format = 'DD/MM/YYYY') {
    if (!dateString) return '';
    const date = new Date(dateString);
    if (isNaN(date)) return dateString;
    
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear();
    
    switch (format) {
        case 'DD/MM/YYYY':
            return `${day}/${month}/${year}`;
        case 'MM/DD/YYYY':
            return `${month}/${day}/${year}`;
        case 'YYYY-MM-DD':
            return `${year}-${month}-${day}`;
        default:
            return date.toLocaleDateString();
    }
}

/**
 * Format file size in human readable format
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Validate form fields
 */
function validateForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

/**
 * Validate email format
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Export data to CSV
 */
function exportToCSV(data, filename) {
    const csv = Papa.unparse(data);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

/**
 * Truncate text to specified length
 */
function truncateText(text, maxLength, suffix = '...') {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength - suffix.length) + suffix;
}

// Export functions for use in other files
window.ExpenseTracker = {
    showNotification,
    formatCurrency,
    formatDate,
    formatFileSize,
    formatNumber,
    validateForm,
    isValidEmail,
    exportToCSV,
    setButtonLoading,
    showInlineLoading,
    hideInlineLoading,
    showCardLoading,
    hideCardLoading,
    showDeleteConfirmation,
    deleteItem,
    copyToClipboard,
    generateId,
    deepClone,
    isMobileDevice,
    truncateText,
    debounce,
    setupDebouncedSearch
};

// Invoice-specific functions
function renderInvoicesTable() {
    const tbody = document.querySelector('#invoicesTable tbody');
    const noInvoicesDiv = document.getElementById('noInvoices');
    const countBadge = document.getElementById('invoiceCount');
    
    if (!tbody || !noInvoicesDiv || !countBadge) {
        console.error('Required elements not found for renderInvoicesTable');
        return;
    }
    
    // Get invoices from global variable (set by loadInvoices)
    const invoices = window.invoices || [];
    const filteredInvoices = window.filteredInvoices || invoices;
    
    countBadge.textContent = filteredInvoices.length;
    
    if (filteredInvoices.length === 0) {
        document.getElementById('invoicesTable').style.display = 'none';
        noInvoicesDiv.style.display = 'block';
        return;
    }
    
    document.getElementById('invoicesTable').style.display = 'table';
    noInvoicesDiv.style.display = 'none';
    
    // Render the table content
    tbody.innerHTML = filteredInvoices.map(invoice => {
        const invoiceDate = new Date(invoice.invoice_date).toLocaleDateString();
        const dueDate = invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : '-';
        
        let statusClass, statusIcon;
        switch(invoice.status) {
            case 'paid':
                statusClass = 'success';
                statusIcon = 'check-circle';
                break;
            case 'sent':
                statusClass = 'info';
                statusIcon = 'paper-plane';
                break;
            case 'overdue':
                statusClass = 'danger';
                statusIcon = 'exclamation-triangle';
                break;
            default:
                statusClass = 'secondary';
                statusIcon = 'file';
        }
            
        return `
            <tr>
                <td><strong>${invoice.invoice_number}</strong></td>
                <td>
                    <strong>${invoice.client_name}</strong>
                    ${invoice.client_email ? `<br><small class="text-muted">${invoice.client_email}</small>` : ''}
                </td>
                <td><strong>${ExpenseTracker.formatCurrency(invoice.total_amount)}</strong></td>
                <td>
                    <span class="badge bg-${statusClass}">
                        <i class="fas fa-${statusIcon} me-1"></i>${invoice.status}
                    </span>
                </td>
                <td>${invoiceDate}</td>
                <td>${dueDate}</td>
                <td>
                    <div class="d-flex gap-1">
                        <button type="button" class="btn btn-outline-success btn-sm" onclick="viewInvoice(${invoice.id})" title="View PDF">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button type="button" class="btn btn-outline-warning btn-sm" onclick="changeInvoiceStatus(${invoice.id})" title="Change Status">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button type="button" class="btn btn-outline-danger btn-sm" onclick="deleteInvoice(${invoice.id})" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function updateSummaryCards() {
    const invoices = window.invoices || [];
    let totalAmount = 0;
    let paidTotal = 0;
    let pendingTotal = 0;
    let paidCount = 0;
    let pendingCount = 0;

    invoices.forEach(invoice => {
        const amount = parseFloat(invoice.total_amount) || 0;
        totalAmount += amount;
        
        if (invoice.status === 'paid') {
            paidTotal += amount;
            paidCount++;
        } else {
            pendingTotal += amount;
            pendingCount++;
        }
    });

    // Update the display elements
    const totalInvoicesEl = document.getElementById('totalInvoices');
    const totalRevenueEl = document.getElementById('totalRevenue');
    const paidInvoiceCountEl = document.getElementById('paidInvoiceCount');
    const paidAmountEl = document.getElementById('paidAmount');
    const pendingInvoiceCountEl = document.getElementById('pendingInvoiceCount');
    const pendingAmountEl = document.getElementById('pendingAmount');
    
    if (totalInvoicesEl) totalInvoicesEl.textContent = invoices.length;
    if (totalRevenueEl) totalRevenueEl.textContent = ExpenseTracker.formatCurrency(totalAmount);
    if (paidInvoiceCountEl) paidInvoiceCountEl.textContent = `count = ${paidCount}`;
    if (paidAmountEl) paidAmountEl.textContent = ExpenseTracker.formatCurrency(paidTotal);
    if (pendingInvoiceCountEl) pendingInvoiceCountEl.textContent = `count = ${pendingCount}`;
    if (pendingAmountEl) pendingAmountEl.textContent = ExpenseTracker.formatCurrency(pendingTotal);
}

// Make functions globally available
window.renderInvoicesTable = renderInvoicesTable;
window.updateSummaryCards = updateSummaryCards;

/**
 * Toggle search/filter functionality
 */
function toggleSearch() {
    const searchBtn = document.getElementById('searchToggleBtn');
    const filtersSection = document.getElementById('filtersSection');
    
    if (filtersSection.style.display === 'none' || filtersSection.style.display === '') {
        // Show search/filters
        filtersSection.style.display = 'block';
        searchBtn.classList.add('active');
        searchBtn.innerHTML = '<i class="fas fa-times"></i>';
        
        // Add smooth animation
        filtersSection.style.opacity = '0';
        filtersSection.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            filtersSection.style.transition = 'all 0.3s ease';
            filtersSection.style.opacity = '1';
            filtersSection.style.transform = 'translateY(0)';
        }, 10);
    } else {
        // Hide search/filters
        searchBtn.classList.remove('active');
        searchBtn.innerHTML = '<i class="fas fa-search"></i>';
        
        // Add smooth animation
        filtersSection.style.transition = 'all 0.3s ease';
        filtersSection.style.opacity = '0';
        filtersSection.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            filtersSection.style.display = 'none';
        }, 300);
    }
}

// Make toggleSearch globally available
window.toggleSearch = toggleSearch;
