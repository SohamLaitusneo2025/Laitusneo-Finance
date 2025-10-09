// Admin Dashboard JavaScript

let usersTable, auditTable, sessionsTable;
let userStatsChart, activityChart;

// Initialize admin dashboard
$(document).ready(function() {
    initializeTables();
    loadDashboardData();
    initializeCharts();
    
    // Tab navigation
    $('.nav-link').on('click', function() {
        $('.nav-link').removeClass('active');
        $(this).addClass('active');
    });
    
         // Form submissions
     $('#createUserForm').on('submit', function(e) {
         e.preventDefault();
         createUser();
     });
     

});

// Initialize DataTables
function initializeTables() {
         // Users Table
     usersTable = $('#usersTable').DataTable({
         ajax: {
             url: '/admin/api/users',
             dataSrc: '',
             data: function() {
                 return {
                     _: new Date().getTime() // Cache busting
                 };
             },
             error: function(xhr, error, thrown) {
                 console.error('DataTable AJAX error:', error, thrown);
             }
         },
        columns: [
            { 
                data: 'id',
                className: 'text-center',
                width: '60px'
            },
            { 
                data: 'username',
                className: 'text-left font-weight-bold',
                width: '120px'
            },
            { 
                data: 'email',
                className: 'text-left',
                width: '180px'
            },
            { 
                data: null,
                className: 'text-left',
                width: '150px',
                render: function(data) {
                    return data.first_name + ' ' + data.last_name;
                }
            },
            { 
                data: 'is_active',
                className: 'text-center',
                width: '100px',
                render: function(data) {
                    return data ? 
                        '<span class="status-badge active">Active</span>' : 
                        '<span class="status-badge inactive">Inactive</span>';
                }
            },
            { 
                data: 'is_admin',
                className: 'text-center',
                width: '80px',
                render: function(data) {
                    return data ? 
                        '<span class="admin-badge admin">Admin</span>' : 
                        '<span class="admin-badge user">User</span>';
                }
            },
             { 
                 data: 'last_login',
                 className: 'text-center',
                 width: '120px',
                 render: function(data) {
                     if (!data) return '<span class="text-muted">Never</span>';
                     // If data is already formatted (from backend), return as is
                     if (typeof data === 'string' && data.includes('-') && data.includes(':')) {
                         return '<small>' + data + '</small>';
                     }
                     try {
                         return '<small>' + new Date(data).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata'}) + '</small>';
                     } catch (e) {
                         return '<small>' + data + '</small>';
                     }
                 }
             },
             { 
                 data: 'created_at',
                 className: 'text-center',
                 width: '120px',
                 render: function(data) {
                     // If data is already formatted (from backend), return as is
                     if (typeof data === 'string' && data.includes('-') && data.includes(':')) {
                         return '<small>' + data + '</small>';
                     }
                     try {
                         return '<small>' + new Date(data).toLocaleDateString('en-IN', {timeZone: 'Asia/Kolkata'}) + '</small>';
                     } catch (e) {
                         return '<small>' + data + '</small>';
                     }
                 }
             },
            {
                data: null,
                className: 'text-center',
                width: '180px',
                orderable: false,
                render: function(data) {
                    return `
                        <div class="action-buttons">
                            <button class="btn btn-info" onclick="viewUserDetails(${data.id})" title="View Details">
                                <i class="fas fa-eye"></i>
                            </button>

                             <button class="btn btn-success" onclick="exportUserData(${data.id})" title="Export Data">
                                 <i class="fas fa-download"></i>
                             </button>
                            <button class="btn btn-secondary" onclick="resetUserPassword(${data.id})" title="Reset Password">
                                <i class="fas fa-key"></i>
                            </button>
                            <button class="btn btn-danger" onclick="deleteUser(${data.id})" title="Delete User">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    `;
                }
            }
        ],
        order: [[0, 'desc']],
        responsive: {
            details: {
                type: 'column',
                target: 'tr'
            }
        },
        pageLength: 10,
        lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
        dom: '<"row"<"col-sm-6"l><"col-sm-6"f>>' +
             '<"row"<"col-sm-12"B>>' +
             '<"row"<"col-sm-12"tr>>' +
             '<"row"<"col-sm-5"i><"col-sm-7"p>>',
        buttons: [
            {
                extend: 'copy',
                text: '<i class="fas fa-copy me-1"></i>Copy',
                className: 'btn-secondary'
            },
            {
                extend: 'csv',
                text: '<i class="fas fa-file-csv me-1"></i>CSV',
                className: 'btn-secondary'
            },
            {
                extend: 'pdf',
                text: '<i class="fas fa-file-pdf me-1"></i>PDF',
                className: 'btn-secondary',
                orientation: 'landscape',
                pageSize: 'A4'
            },
            {
                extend: 'print',
                text: '<i class="fas fa-print me-1"></i>Print',
                className: 'btn-secondary'
            }
        ],
        language: {
            search: "Search users:",
            lengthMenu: "Show _MENU_ users per page",
            info: "Showing _START_ to _END_ of _TOTAL_ users",
            infoEmpty: "No users found",
            infoFiltered: "(filtered from _MAX_ total users)",
            zeroRecords: "No matching users found",
            emptyTable: "No user data available"
        },
        drawCallback: function() {
            // Reinitialize tooltips after table redraw
            $('[title]').tooltip();
        }
    });
    
    // Audit Table
    auditTable = $('#auditTable').DataTable({
        ajax: {
            url: '/admin/api/audit-logs',
            dataSrc: ''
        },
        columns: [
            { data: 'id' },
            { data: 'user_name' },
            { data: 'action' },
            { data: 'table_name' },
            { data: 'ip_address' },
                         { 
                 data: 'created_at',
                 render: function(data) {
                     try {
                         return new Date(data).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata'});
                     } catch (e) {
                         return data;
                     }
                 }
             },
            {
                data: null,
                render: function(data) {
                    let details = '';
                    if (data.old_values) details += '<strong>Old:</strong> ' + JSON.stringify(data.old_values) + '<br>';
                    if (data.new_values) details += '<strong>New:</strong> ' + JSON.stringify(data.new_values);
                    return details || 'No details';
                }
            }
        ],
        order: [[5, 'desc']],
        responsive: true,
        dom: 'Bfrtip',
        buttons: ['copy', 'csv', 'pdf', 'print']
    });
    
    // Sessions Table
    sessionsTable = $('#sessionsTable').DataTable({
        ajax: {
            url: '/admin/api/active-sessions',
            dataSrc: ''
        },
        columns: [
            { data: 'username' },
            { data: 'ip_address' },
            { 
                data: 'user_agent',
                render: function(data) {
                    return data ? data.substring(0, 50) + '...' : 'Unknown';
                }
            },
                         { 
                 data: 'login_time',
                 render: function(data) {
                     try {
                         return new Date(data).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata'});
                     } catch (e) {
                         return data;
                     }
                 }
             },
                         { 
                 data: 'last_activity',
                 render: function(data) {
                     try {
                         return new Date(data).toLocaleString('en-IN', {timeZone: 'Asia/Kolkata'});
                     } catch (e) {
                         return data;
                     }
                 }
             },
            {
                data: null,
                render: function(data) {
                    return `
                        <button class="btn btn-danger btn-sm" onclick="terminateSession(${data.id})">
                            <i class="fas fa-stop-circle"></i> Terminate
                        </button>
                    `;
                }
            }
        ],
        order: [[4, 'desc']],
        responsive: true
    });
}

// Load dashboard data
function loadDashboardData() {
    // Load recent activity
    $.get('/admin/api/recent-activity', function(data) {
        let html = '';
        data.forEach(function(item) {
            html += `
                <div class="audit-item ${item.action.toLowerCase()}">
                    <div class="d-flex justify-content-between">
                        <strong>${item.user_name || 'System'}</strong>
                                                 <small>${item.created_at}</small>
                    </div>
                    <div>${item.action} - ${item.table_name || 'System'}</div>
                    <small class="text-muted">${item.ip_address}</small>
                </div>
            `;
        });
        $('#recentActivity').html(html);
    });
}

// Initialize charts
function initializeCharts() {
    // User Statistics Chart
    const userStatsCtx = document.getElementById('userStatsChart').getContext('2d');
    userStatsChart = new Chart(userStatsCtx, {
        type: 'doughnut',
        data: {
            labels: ['Active Users', 'Inactive Users', 'Admin Users'],
            datasets: [{
                data: [0, 0, 0],
                backgroundColor: ['#28a745', '#dc3545', '#ffc107']
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
    
    // Activity Trends Chart
    const activityCtx = document.getElementById('activityChart').getContext('2d');
    activityChart = new Chart(activityCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Daily Logins',
                data: [],
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // Load chart data
    loadChartData();
}

// Load chart data
function loadChartData() {
    $.get('/admin/api/chart-data', function(data) {
        // Update user stats chart
        userStatsChart.data.datasets[0].data = [
            data.active_users,
            data.inactive_users,
            data.admin_users
        ];
        userStatsChart.update();
        
        // Update activity chart
        activityChart.data.labels = data.activity_labels;
        activityChart.data.datasets[0].data = data.activity_data;
        activityChart.update();
    });
}

// Refresh statistics
function refreshStats() {
    location.reload();
}

// Refresh users table completely
function refreshUsersTable() {
    console.log('Refreshing users table...');
    if (usersTable) {
        usersTable.destroy();
    }
    $('#usersTable').empty();
    setTimeout(function() {
        initializeTables();
        console.log('Users table refreshed');
    }, 100);
}

// Show create user modal
function showCreateUserModal() {
    $('#createUserModal').modal('show');
}

// Create new user
function createUser() {
    const formData = new FormData($('#createUserForm')[0]);
    
    $.ajax({
        url: '/admin/api/users',
        method: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(response) {
            if (response.success) {
                $('#createUserModal').modal('hide');
                $('#createUserForm')[0].reset();
                usersTable.ajax.reload();
                showAlert('User created successfully!', 'success');
            } else {
                showAlert(response.message || 'Error creating user', 'error');
            }
        },
        error: function() {
            showAlert('Error creating user', 'error');
        }
    });
}

// View user details
function viewUserDetails(userId) {
    $.get(`/admin/api/users/${userId}`, function(data) {
        let html = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Basic Information</h6>
                    <table class="table table-sm">
                        <tr><td><strong>ID:</strong></td><td>${data.id}</td></tr>
                        <tr><td><strong>Username:</strong></td><td>${data.username}</td></tr>
                        <tr><td><strong>Email:</strong></td><td>${data.email}</td></tr>
                        <tr><td><strong>Name:</strong></td><td>${data.first_name || ''} ${data.last_name || ''}</td></tr>
                        <tr><td><strong>Status:</strong></td><td>${data.is_active ? 'Active' : 'Inactive'}</td></tr>
                        <tr><td><strong>Admin:</strong></td><td>${data.is_admin ? 'Yes' : 'No'}</td></tr>
                                                 <tr><td><strong>Created:</strong></td><td>${data.created_at}</td></tr>
                         <tr><td><strong>Last Login:</strong></td><td>${data.last_login || 'Never'}</td></tr>
                         <tr><td><strong>Updated:</strong></td><td>${data.updated_at}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6>User Statistics</h6>
                    <div class="row">
                        <div class="col-md-4">
                            <div class="card bg-primary text-white text-center">
                                <div class="card-body">
                                    <h4>${data.stats.expenses_count || 0}</h4>
                                    <small>Expenses</small>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="card bg-success text-white text-center">
                                <div class="card-body">
                                    <h4>${data.stats.transactions_count || 0}</h4>
                                    <small>Transactions</small>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="card bg-info text-white text-center">
                                <div class="card-body">
                                    <h4>${data.stats.invoices_count || 0}</h4>
                                    <small>Invoices</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add recent data if available
        if (data.recent_data) {
            html += `
                <hr>
                <div class="row">
                    <div class="col-md-4">
                        <h6>Recent Expenses</h6>
                        <div class="list-group list-group-flush">
            `;
            
            if (data.recent_data.expenses && data.recent_data.expenses.length > 0) {
                data.recent_data.expenses.forEach(expense => {
                    html += `
                        <div class="list-group-item">
                            <div class="d-flex justify-content-between">
                                <div>
                                    <strong>${expense.title || expense.expense_type}</strong><br>
                                    <small>${expense.category} - ₹${expense.amount}</small>
                                </div>
                                <small>${new Date(expense.expense_date).toLocaleDateString('en-IN', {timeZone: 'Asia/Kolkata'})}</small>
                            </div>
                        </div>
                    `;
                });
            } else {
                html += '<div class="list-group-item text-muted">No recent expenses</div>';
            }
            
            html += `
                        </div>
                    </div>
                    <div class="col-md-4">
                        <h6>Recent Transactions</h6>
                        <div class="list-group list-group-flush">
            `;
            
            if (data.recent_data.transactions && data.recent_data.transactions.length > 0) {
                data.recent_data.transactions.forEach(transaction => {
                    html += `
                        <div class="list-group-item">
                            <div class="d-flex justify-content-between">
                                <div>
                                    <strong>${transaction.title || transaction.transaction_type}</strong><br>
                                    <small>${transaction.category} - ₹${transaction.amount}</small>
                                </div>
                                <small>${new Date(transaction.transaction_date).toLocaleDateString('en-IN', {timeZone: 'Asia/Kolkata'})}</small>
                            </div>
                        </div>
                    `;
                });
            } else {
                html += '<div class="list-group-item text-muted">No recent transactions</div>';
            }
            
            html += `
                        </div>
                    </div>
                    <div class="col-md-4">
                        <h6>Recent Invoices</h6>
                        <div class="list-group list-group-flush">
            `;
            
            if (data.recent_data.invoices && data.recent_data.invoices.length > 0) {
                data.recent_data.invoices.forEach(invoice => {
                    html += `
                        <div class="list-group-item">
                            <div class="d-flex justify-content-between">
                                <div>
                                    <strong>${invoice.invoice_number}</strong><br>
                                    <small>${invoice.client_name} - ₹${invoice.total_amount}</small>
                                </div>
                                <small>
                                    <span class="badge bg-${invoice.status === 'paid' ? 'success' : 'warning'}">${invoice.status}</span><br>
                                    ${new Date(invoice.invoice_date).toLocaleDateString('en-IN', {timeZone: 'Asia/Kolkata'})}
                                </small>
                            </div>
                        </div>
                    `;
                });
            } else {
                html += '<div class="list-group-item text-muted">No recent invoices</div>';
            }
            
            html += `
                        </div>
                    </div>
                </div>
            `;
        }
        
        $('#userDetailsContent').html(html);
        $('#userDetailsModal').modal('show');
    });
}



 // Export user data
 function exportUserData(userId) {
     window.location.href = `/admin/api/users/${userId}/export-data`;
 }

// Reset user password
function resetUserPassword(userId) {
    showDeleteConfirmation(
        'Are you sure you want to reset this user\'s password?',
        'user password',
        function() {
            $.post(`/admin/api/users/${userId}/reset-password`, function(response) {
                if (response.success) {
                    showAlert('Password reset successfully! New password: ' + response.new_password, 'success');
                } else {
                    showAlert(response.message || 'Error resetting password', 'error');
                }
            });
        }
    );
}

// Delete user
function deleteUser(userId) {
    showDeleteConfirmation(
        'Are you sure you want to delete this user? This action cannot be undone.',
        'user',
        function() {
            $.ajax({
                url: `/admin/api/users/${userId}`,
                method: 'DELETE',
                success: function(response) {
                    if (response.success) {
                        usersTable.ajax.reload();
                        showAlert('User deleted successfully!', 'success');
                    } else {
                        showAlert(response.message || 'Error deleting user', 'error');
                    }
                },
                error: function() {
                    showAlert('Error deleting user', 'error');
                }
            });
        }
    );
}

// Terminate session
function terminateSession(sessionId) {
    showDeleteConfirmation(
        'Are you sure you want to terminate this session?',
        'session',
        function() {
            $.post(`/admin/api/sessions/${sessionId}/terminate`, function(response) {
                if (response.success) {
                    sessionsTable.ajax.reload();
                    showAlert('Session terminated successfully!', 'success');
                } else {
                    showAlert(response.message || 'Error terminating session', 'error');
                }
            });
        }
    );
}

// Terminate all sessions
function terminateAllSessions() {
    showDeleteConfirmation(
        'Are you sure you want to terminate all active sessions?',
        'all sessions',
        function() {
            $.post('/admin/api/sessions/terminate-all', function(response) {
                if (response.success) {
                    sessionsTable.ajax.reload();
                    showAlert('All sessions terminated successfully!', 'success');
                } else {
                    showAlert(response.message || 'Error terminating sessions', 'error');
                }
            });
        }
    );
}

// Export all data
function exportAllData() {
    window.location.href = '/admin/api/export-all-data';
}

// Export audit logs
function exportAuditLogs() {
    window.location.href = '/admin/api/export-audit-logs';
}

// Generate system report
function generateReport() {
    window.location.href = '/admin/api/generate-report';
}

// Clear old logs
function clearOldLogs() {
    showDeleteConfirmation(
        'Are you sure you want to clear old audit logs? This action cannot be undone.',
        'audit logs',
        function() {
            $.post('/admin/api/clear-old-logs', function(response) {
                if (response.success) {
                    auditTable.ajax.reload();
                    showAlert('Old logs cleared successfully!', 'success');
                } else {
                    showAlert(response.message || 'Error clearing logs', 'error');
                }
            });
        }
    );
}

// Show system report
function showSystemReport() {
    window.open('/admin/api/system-report', '_blank');
}

// Export user data
function exportUserData(userId) {
    window.location.href = `/admin/api/users/${userId}/export-data`;
}

// Show alert
function showAlert(message, type) {
    const alertClass = type === 'error' ? 'danger' : type;
    const html = `
        <div class="alert alert-${alertClass} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    // Remove existing alerts
    $('.alert').remove();
    
    // Add new alert at the top of the main content
    $('main').prepend(html);
    
    // Scroll to top to show the alert
    $('html, body').animate({ scrollTop: 0 }, 300);
    
    // Auto-dismiss after 5 seconds
    setTimeout(function() {
        $('.alert').fadeOut();
    }, 5000);
}

// Auto-refresh data every 30 seconds
setInterval(function() {
    if ($('#dashboard').hasClass('active')) {
        loadDashboardData();
    }
}, 30000);
