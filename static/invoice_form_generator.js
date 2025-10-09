/**
 * Dynamic Invoice Form Generator
 * Creates comprehensive invoice forms based on PDF template fields and standard invoice requirements
 */

class InvoiceFormGenerator {
    constructor() {
        this.fieldDefinitions = {
            // Company Information Fields
            'company_info': {
                title: 'Company Information',
                icon: 'fas fa-building',
                fields: {
                    'company_name': { label: 'Company Name', type: 'text', required: true, placeholder: 'Your Company Name' },
                    'company_address': { label: 'Company Address', type: 'textarea', required: true, placeholder: 'Your Company Address' },
                    'company_phone': { label: 'Company Phone', type: 'tel', required: true, placeholder: '+91 98765 43210' },
                    'company_email': { label: 'Company Email', type: 'email', required: true, placeholder: 'info@company.com' },
                    'company_gstin': { label: 'Company GSTIN', type: 'text', required: true, placeholder: 'Your GST Number' },
                    'company_pan': { label: 'Company PAN', type: 'text', required: true, placeholder: 'Your PAN Number' },
                    'company_city': { label: 'Company City', type: 'text', required: true, placeholder: 'Your City' }
                }
            },
            
            // Invoice Details Fields
            'invoice_details': {
                title: 'Invoice Details',
                icon: 'fas fa-file-invoice',
                fields: {
                    'invoice_number': { label: 'Invoice Number', type: 'text', required: false, placeholder: 'Auto-generated', readonly: true },
                    'invoice_date': { label: 'Invoice Date', type: 'date', required: true, defaultValue: 'today' },
                    'due_date': { label: 'Due Date', type: 'date', required: true, defaultValue: 'today+30' },
                    'status': { label: 'Status', type: 'select', required: true, options: ['Pending', 'Paid', 'Overdue', 'Cancelled'], defaultValue: 'Pending' }
                }
            },
            
            // Client Information Fields
            'client_info': {
                title: 'Client Information',
                icon: 'fas fa-user',
                fields: {
                    'client_name': { label: 'Client Name', type: 'text', required: true, placeholder: 'Client or Company Name' },
                    'client_email': { label: 'Client Email', type: 'email', required: true, placeholder: 'client@email.com' },
                    'client_phone': { label: 'Client Phone', type: 'tel', required: true, placeholder: '+91 98765 43210' },
                    'client_address': { label: 'Client Address', type: 'textarea', required: false, placeholder: 'Client Address' },
                    'billing_company_name': { label: 'Billing Company', type: 'text', required: true, placeholder: 'Billing Company Name' },
                    'billing_address': { label: 'Billing Address', type: 'textarea', required: true, placeholder: 'Complete Billing Address' },
                    'billing_city': { label: 'Billing City', type: 'text', required: true, placeholder: 'City' },
                    'billing_state': { label: 'Billing State', type: 'select', required: true, options: this.getIndianStates(), onchange: 'calculateGSTBasedOnState()' },
                    'billing_pincode': { label: 'PIN Code', type: 'text', required: true, placeholder: '123456' },
                    'gstin_number': { label: 'Client GSTIN', type: 'text', required: true, placeholder: 'Client GST Number' },
                    'pan_number': { label: 'Client PAN', type: 'text', required: true, placeholder: 'Client PAN Number' }
                }
            },
            
            // Financial Information Fields
            'financial': {
                title: 'Financial Details',
                icon: 'fas fa-calculator',
                fields: {
                    'subtotal': { label: 'Subtotal', type: 'number', required: true, step: '0.01', min: '0', onchange: 'calculateTotals()' },
                    'cgst_rate': { label: 'CGST Rate (%)', type: 'number', required: false, step: '0.01', min: '0', max: '100', defaultValue: '0', readonly: true },
                    'cgst_amount': { label: 'CGST Amount', type: 'number', required: false, step: '0.01', min: '0', readonly: true },
                    'sgst_rate': { label: 'SGST Rate (%)', type: 'number', required: false, step: '0.01', min: '0', max: '100', defaultValue: '0', readonly: true },
                    'sgst_amount': { label: 'SGST Amount', type: 'number', required: false, step: '0.01', min: '0', readonly: true },
                    'igst_rate': { label: 'IGST Rate (%)', type: 'number', required: false, step: '0.01', min: '0', max: '100', defaultValue: '0', readonly: true },
                    'igst_amount': { label: 'IGST Amount', type: 'number', required: false, step: '0.01', min: '0', readonly: true },
                    'tax_amount': { label: 'Other Tax Amount', type: 'number', required: false, step: '0.01', min: '0', onchange: 'calculateTotals()' },
                    'total_amount': { label: 'Total Amount', type: 'number', required: true, step: '0.01', min: '0', readonly: true },
                    'received_amount': { label: 'Received Amount', type: 'number', required: false, step: '0.01', min: '0', defaultValue: '0' }
                }
            },
            
            // Banking Information Fields
            'banking': {
                title: 'Bank Details',
                icon: 'fas fa-university',
                fields: {
                    'bank_name': { label: 'Bank Name', type: 'text', required: false, placeholder: 'Bank Name' },
                    'account_number': { label: 'Account Number', type: 'text', required: false, placeholder: 'Account Number' },
                    'ifsc_code': { label: 'IFSC Code', type: 'text', required: false, placeholder: 'IFSC Code' },
                    'upi_id': { label: 'UPI ID', type: 'text', required: false, placeholder: 'yourname@upi' },
                    'bank_account_name': { label: 'Account Holder Name', type: 'text', required: false, placeholder: 'Account Holder Name' }
                }
            },
            
            // Additional Information Fields
            'additional': {
                title: 'Additional Information',
                icon: 'fas fa-sticky-note',
                fields: {
                    'notes': { label: 'Notes', type: 'textarea', required: false, placeholder: 'Any additional notes or comments' },
                    'terms_conditions': { label: 'Terms & Conditions', type: 'textarea', required: false, placeholder: 'Terms and conditions' },
                    'payment_terms': { label: 'Payment Terms', type: 'text', required: false, placeholder: 'Payment within 30 days' }
                }
            }
        };
        
        this.itemFields = {
            'description': { label: 'Description', type: 'text', required: true, placeholder: 'Item description' },
            'quantity': { label: 'Quantity', type: 'number', required: true, min: '0', step: '1', defaultValue: '1', onchange: 'calculateItemTotal(this)' },
            'unit_price': { label: 'Unit Price', type: 'number', required: true, min: '0', step: '0.01', onchange: 'calculateItemTotal(this)' },
            'total_price': { label: 'Total', type: 'number', required: false, readonly: true }
        };
    }
    
    /**
     * Generate a complete invoice form with all sections
     */
    generateCompleteForm(containerId, options = {}) {
        console.log('Generating complete form for container:', containerId);
        
        const container = document.getElementById(containerId);
        if (!container) {
            console.error('Container not found:', containerId);
            return;
        }
        
        const formId = options.formId || 'dynamicInvoiceForm';
        const showSections = options.sections || Object.keys(this.fieldDefinitions);
        const includeItems = options.includeItems !== false;
        
        console.log('Form options:', { formId, showSections, includeItems });
        
        let formHTML = `<form id="${formId}" class="dynamic-invoice-form">`;
        
        // Generate sections
        showSections.forEach(sectionKey => {
            if (this.fieldDefinitions[sectionKey]) {
                formHTML += this.generateFormSection(sectionKey);
            }
        });
        
        // Add items section if requested
        if (includeItems) {
            formHTML += this.generateItemsSection();
        }
        
        // Add action buttons
        formHTML += this.generateActionButtons(options.buttons);
        
        formHTML += '</form>';
        
        console.log('Generated form HTML length:', formHTML.length);
        container.innerHTML = formHTML;
        
        // Hide loading message
        const loadingMessage = document.getElementById('formLoadingMessage');
        if (loadingMessage) {
            loadingMessage.style.display = 'none';
        }
        
        // Initialize form functionality
        this.initializeForm(formId);
        
        console.log('Form generation completed');
        return formId;
    }
    
    /**
     * Generate a specific form section
     */
    generateFormSection(sectionKey) {
        const section = this.fieldDefinitions[sectionKey];
        if (!section) return '';
        
        let html = `
            <div class="form-section mb-4" data-section="${sectionKey}">
                <div class="col-12 mb-3">
                    <h6 class="border-bottom pb-2">
                        <i class="${section.icon} me-2"></i>${section.title}
                    </h6>
                </div>
                <div class="row g-3">
        `;
        
        Object.entries(section.fields).forEach(([fieldName, fieldDef]) => {
            html += this.generateFieldHTML(fieldName, fieldDef, sectionKey);
        });
        
        html += `
                </div>
            </div>
        `;
        
        return html;
    }
    
    /**
     * Generate HTML for a single field
     */
    generateFieldHTML(fieldName, fieldDef, sectionKey) {
        const colClass = this.getColumnClass(fieldDef.type);
        const fieldId = `${sectionKey}_${fieldName}`;
        const required = fieldDef.required ? 'required' : '';
        const requiredMark = fieldDef.required ? '<span class="text-danger">*</span>' : '';
        
        let fieldHTML = '';
        
        switch (fieldDef.type) {
            case 'textarea':
                fieldHTML = `
                    <textarea 
                        class="form-control" 
                        id="${fieldId}" 
                        name="${fieldName}" 
                        placeholder="${fieldDef.placeholder || ''}"
                        ${required}
                        ${fieldDef.readonly ? 'readonly' : ''}
                        rows="3"
                        ${fieldDef.onchange ? `onchange="${fieldDef.onchange}"` : ''}
                    ></textarea>
                `;
                break;
                
            case 'select':
                fieldHTML = `<select class="form-select" id="${fieldId}" name="${fieldName}" ${required}>`;
                if (!fieldDef.required) {
                    fieldHTML += '<option value="">Select an option</option>';
                }
                fieldDef.options.forEach(option => {
                    const selected = fieldDef.defaultValue === option ? 'selected' : '';
                    fieldHTML += `<option value="${option}" ${selected}>${option}</option>`;
                });
                fieldHTML += '</select>';
                break;
                
            default:
                fieldHTML = `
                    <input 
                        type="${fieldDef.type}" 
                        class="form-control" 
                        id="${fieldId}" 
                        name="${fieldName}" 
                        placeholder="${fieldDef.placeholder || ''}"
                        ${required}
                        ${fieldDef.readonly ? 'readonly' : ''}
                        ${fieldDef.min ? `min="${fieldDef.min}"` : ''}
                        ${fieldDef.max ? `max="${fieldDef.max}"` : ''}
                        ${fieldDef.step ? `step="${fieldDef.step}"` : ''}
                        ${fieldDef.onchange ? `onchange="${fieldDef.onchange}"` : ''}
                    />
                `;
        }
        
        return `
            <div class="${colClass}">
                <label for="${fieldId}" class="form-label">${fieldDef.label} ${requiredMark}</label>
                ${fieldHTML}
            </div>
        `;
    }
    
    /**
     * Generate items table section
     */
    generateItemsSection() {
        return `
            <div class="form-section mb-4" data-section="items">
                <div class="col-12 mb-3">
                    <h6 class="border-bottom pb-2">
                        <i class="fas fa-list me-2"></i>Invoice Items
                        <button type="button" class="btn btn-sm btn-outline-primary float-end" onclick="addInvoiceItem()">
                            <i class="fas fa-plus me-1"></i>Add Item
                        </button>
                    </h6>
                </div>
                <div id="itemsContainer">
                    <!-- Items will be added here -->
                </div>
            </div>
        `;
    }
    
    /**
     * Generate action buttons section
     */
    generateActionButtons(customButtons) {
        const defaultButtons = [
            { text: 'Generate PDF', class: 'btn-primary', onclick: 'generatePdfFromForm()' },
            { text: 'Save Draft', class: 'btn-secondary', onclick: 'saveDraft()' },
            { text: 'Reset Form', class: 'btn-outline-danger', onclick: 'resetForm()' }
        ];
        
        const buttons = customButtons || defaultButtons;
        
        let html = `
            <div class="form-section">
                <div class="col-12">
                    <hr class="my-4">
                    <div class="d-flex justify-content-end gap-2">
        `;
        
        buttons.forEach(button => {
            html += `
                <button type="button" class="btn ${button.class}" onclick="${button.onclick}">
                    ${button.icon ? `<i class="${button.icon} me-1"></i>` : ''}${button.text}
                </button>
            `;
        });
        
        html += `
                    </div>
                </div>
            </div>
        `;
        
        return html;
    }
    
    /**
     * Get Bootstrap column class based on field type
     */
    getColumnClass(fieldType) {
        switch (fieldType) {
            case 'textarea':
                return 'col-12';
            case 'email':
            case 'tel':
            case 'date':
                return 'col-md-6';
            case 'number':
                return 'col-md-4';
            default:
                return 'col-md-6';
        }
    }
    
    /**
     * Initialize form functionality
     */
    initializeForm(formId) {
        // Set default values
        this.setDefaultValues(formId);
        
        // Add first item
        setTimeout(() => {
            if (document.getElementById('itemsContainer')) {
                this.addInvoiceItem();
            }
        }, 100);
    }
    
    /**
     * Set default values for form fields
     */
    setDefaultValues(formId) {
        const form = document.getElementById(formId);
        if (!form) return;
        
        // Set today's date
        const todayInputs = form.querySelectorAll('input[type="date"][name*="date"]');
        const today = new Date().toISOString().split('T')[0];
        const futureDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
        
        todayInputs.forEach(input => {
            if (input.name.includes('invoice_date')) {
                input.value = today;
            } else if (input.name.includes('due_date')) {
                input.value = futureDate;
            }
        });
        
        // Set default values from field definitions
        Object.entries(this.fieldDefinitions).forEach(([sectionKey, section]) => {
            Object.entries(section.fields).forEach(([fieldName, fieldDef]) => {
                if (fieldDef.defaultValue && fieldDef.defaultValue !== 'today' && fieldDef.defaultValue !== 'today+30') {
                    const field = form.querySelector(`[name="${fieldName}"]`);
                    if (field) {
                        field.value = fieldDef.defaultValue;
                    }
                }
            });
        });
    }
    
    /**
     * Add a new invoice item row
     */
    addInvoiceItem() {
        const container = document.getElementById('itemsContainer');
        if (!container) return;
        
        const itemIndex = container.children.length;
        const itemId = `item_${itemIndex}`;
        
        let itemHTML = `
            <div class="invoice-item border rounded p-3 mb-3" data-item-index="${itemIndex}">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h6 class="mb-0">Item ${itemIndex + 1}</h6>
                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeInvoiceItem(${itemIndex})">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
                <div class="row g-3">
        `;
        
        Object.entries(this.itemFields).forEach(([fieldName, fieldDef]) => {
            const colClass = this.getColumnClass(fieldDef.type);
            const fieldId = `${itemId}_${fieldName}`;
            const required = fieldDef.required ? 'required' : '';
            const requiredMark = fieldDef.required ? '<span class="text-danger">*</span>' : '';
            
            itemHTML += `
                <div class="${colClass}">
                    <label for="${fieldId}" class="form-label">${fieldDef.label} ${requiredMark}</label>
                    <input 
                        type="${fieldDef.type}" 
                        class="form-control" 
                        id="${fieldId}" 
                        name="items[${itemIndex}][${fieldName}]" 
                        placeholder="${fieldDef.placeholder || ''}"
                        ${required}
                        ${fieldDef.readonly ? 'readonly' : ''}
                        ${fieldDef.min ? `min="${fieldDef.min}"` : ''}
                        ${fieldDef.step ? `step="${fieldDef.step}"` : ''}
                        ${fieldDef.defaultValue ? `value="${fieldDef.defaultValue}"` : ''}
                        ${fieldDef.onchange ? `onchange="${fieldDef.onchange}"` : ''}
                    />
                </div>
            `;
        });
        
        itemHTML += `
                </div>
            </div>
        `;
        
        container.insertAdjacentHTML('beforeend', itemHTML);
    }
    
    /**
     * Get list of all Indian states and union territories
     */
    getIndianStates() {
        return [
            'Andhra Pradesh',
            'Arunachal Pradesh',
            'Assam',
            'Bihar',
            'Chhattisgarh',
            'Goa',
            'Gujarat',
            'Haryana',
            'Himachal Pradesh',
            'Jharkhand',
            'Karnataka',
            'Kerala',
            'Madhya Pradesh',
            'Maharashtra',
            'Manipur',
            'Meghalaya',
            'Mizoram',
            'Nagaland',
            'Odisha',
            'Punjab',
            'Rajasthan',
            'Sikkim',
            'Tamil Nadu',
            'Telangana',
            'Tripura',
            'Uttar Pradesh',
            'Uttarakhand',
            'West Bengal',
            'Andaman and Nicobar Islands',
            'Chandigarh',
            'Dadra and Nagar Haveli and Daman and Diu',
            'Delhi',
            'Jammu and Kashmir',
            'Ladakh',
            'Lakshadweep',
            'Puducherry'
        ];
    }

    /**
     * Collect form data
     */
    collectFormData(formId) {
        const form = document.getElementById(formId);
        if (!form) {
            console.error('Form not found:', formId);
            return null;
        }
        
        const formData = new FormData(form);
        const data = {};
        
        // Collect regular form fields
        for (let [key, value] of formData.entries()) {
            if (!key.startsWith('items[')) {
                data[key] = value;
            }
        }
        
        // Collect items data
        const items = [];
        const itemElements = document.querySelectorAll('.invoice-item');
        
        itemElements.forEach((itemElement, index) => {
            const item = {};
            const inputs = itemElement.querySelectorAll('input, select, textarea');
            
            inputs.forEach(input => {
                const fieldName = input.name.match(/\[(\w+)\]$/)?.[1];
                if (fieldName) {
                    item[fieldName] = input.value;
                }
            });
            
            // Only add item if it has valid data
            if (Object.keys(item).length > 0 && (item.description || item.quantity || item.unit_price)) {
                items.push(item);
            }
        });
        
        data.items = items;
        
        // Debug logging
        console.log('Collected form data:', data);
        
        return data;
    }
}

// Global functions for form interaction
function addInvoiceItem() {
    if (window.invoiceFormGenerator) {
        window.invoiceFormGenerator.addInvoiceItem();
    }
}

function removeInvoiceItem(index) {
    const item = document.querySelector(`[data-item-index="${index}"]`);
    if (item) {
        item.remove();
        calculateTotals();
    }
}

function calculateItemTotal(input) {
    const itemContainer = input.closest('.invoice-item');
    if (!itemContainer) return;
    
    const quantityInput = itemContainer.querySelector('[name*="[quantity]"]');
    const priceInput = itemContainer.querySelector('[name*="[unit_price]"]');
    const totalInput = itemContainer.querySelector('[name*="[total_price]"]');
    
    if (quantityInput && priceInput && totalInput) {
        const quantity = parseFloat(quantityInput.value) || 0;
        const price = parseFloat(priceInput.value) || 0;
        const total = quantity * price;
        
        totalInput.value = total.toFixed(2);
        calculateTotals();
    }
}

function calculateGSTBasedOnState() {
    const billingState = document.querySelector('[name="billing_state"]')?.value;
    const cgstRateInput = document.querySelector('[name="cgst_rate"]');
    const sgstRateInput = document.querySelector('[name="sgst_rate"]');
    const igstRateInput = document.querySelector('[name="igst_rate"]');
    
    if (!billingState) return;
    
    // Reset all rates to 0
    if (cgstRateInput) cgstRateInput.value = '0';
    if (sgstRateInput) sgstRateInput.value = '0';
    if (igstRateInput) igstRateInput.value = '0';
    
    // Apply GST logic based on state
    if (billingState === 'Uttar Pradesh') {
        // Same state - apply CGST and SGST
        if (cgstRateInput) cgstRateInput.value = '9';
        if (sgstRateInput) sgstRateInput.value = '9';
    } else {
        // Different state - apply IGST
        if (igstRateInput) igstRateInput.value = '18';
    }
    
    // Recalculate totals
    calculateTotals();
}

function calculateTotals() {
    // Calculate subtotal from items
    const itemTotals = document.querySelectorAll('[name*="[total_price]"]');
    let subtotal = 0;
    
    itemTotals.forEach(input => {
        subtotal += parseFloat(input.value) || 0;
    });
    
    // Update subtotal field
    const subtotalInput = document.querySelector('[name="subtotal"]');
    if (subtotalInput) {
        subtotalInput.value = subtotal.toFixed(2);
    }
    
    // Get tax rates
    const cgstRate = parseFloat(document.querySelector('[name="cgst_rate"]')?.value || 0);
    const sgstRate = parseFloat(document.querySelector('[name="sgst_rate"]')?.value || 0);
    const igstRate = parseFloat(document.querySelector('[name="igst_rate"]')?.value || 0);
    const otherTax = parseFloat(document.querySelector('[name="tax_amount"]')?.value || 0);
    
    // Calculate taxes
    const cgstAmount = (subtotal * cgstRate) / 100;
    const sgstAmount = (subtotal * sgstRate) / 100;
    const igstAmount = (subtotal * igstRate) / 100;
    
    // Update tax fields
    const cgstAmountInput = document.querySelector('[name="cgst_amount"]');
    const sgstAmountInput = document.querySelector('[name="sgst_amount"]');
    const igstAmountInput = document.querySelector('[name="igst_amount"]');
    
    if (cgstAmountInput) cgstAmountInput.value = cgstAmount.toFixed(2);
    if (sgstAmountInput) sgstAmountInput.value = sgstAmount.toFixed(2);
    if (igstAmountInput) igstAmountInput.value = igstAmount.toFixed(2);
    
    // Calculate total
    const total = subtotal + cgstAmount + sgstAmount + igstAmount + otherTax;
    
    // Update total field
    const totalInput = document.querySelector('[name="total_amount"]');
    if (totalInput) {
        totalInput.value = total.toFixed(2);
    }
}

function generatePdfFromForm() {
    const formData = window.invoiceFormGenerator?.collectFormData('dynamicInvoiceForm');
    if (!formData) {
        alert('Unable to collect form data');
        return;
    }
    
    console.log('Form data collected:', formData);
    
    // Here you would call your PDF generation API
    // For now, just show an alert
    alert('PDF generation would be triggered here with the collected data');
}

function saveDraft() {
    const formData = window.invoiceFormGenerator?.collectFormData('dynamicInvoiceForm');
    if (!formData) {
        alert('Unable to collect form data');
        return;
    }
    
    // Save to localStorage as draft
    localStorage.setItem('invoiceDraft', JSON.stringify(formData));
    alert('Draft saved successfully!');
}

function resetForm() {
    showDeleteConfirmation(
        'Are you sure you want to reset the form? All data will be lost.',
        'form data',
        function() {
            document.getElementById('dynamicInvoiceForm')?.reset();
            
            // Clear items
            const itemsContainer = document.getElementById('itemsContainer');
            if (itemsContainer) {
                itemsContainer.innerHTML = '';
                addInvoiceItem(); // Add one item back
            }
            
            // Reset default values
            window.invoiceFormGenerator?.setDefaultValues('dynamicInvoiceForm');
        }
    );
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    window.invoiceFormGenerator = new InvoiceFormGenerator();
});