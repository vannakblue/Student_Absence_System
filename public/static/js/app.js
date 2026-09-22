/**
 * Student & Teacher Absence Management System
 * Client-Side JavaScript Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Set Live Khmer Date in Top Navbar
    initKhmerDate();

    // 2. Sidebar Toggle for Mobile / Small Screens
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            if (window.innerWidth <= 768) {
                sidebar.classList.toggle('mobile-open');
            }
        });
    }
});

/**
 * Format and display Current Date in Khmer
 */
function initKhmerDate() {
    const liveDateEl = document.getElementById('headerLiveDate');
    if (!liveDateEl) return;

    const daysKh = ['អាទិត្យ', 'ច័ន្ទ', 'អង្គារ', 'ពុធ', 'ព្រហស្បតិ៍', 'សុក្រ', 'សៅរ៍'];
    const monthsKh = [
        'មករា', 'កុម្ភៈ', 'មីនា', 'មេសា', 'ឧសភា', 'មិថុនា',
        'កក្កដា', 'សីហា', 'កញ្ញា', 'តុលា', 'វិច្ឆិកា', 'ធ្នូ'
    ];

    const now = new Date();
    const dayName = daysKh[now.getDay()];
    const dateNum = now.getDate();
    const monthName = monthsKh[now.getMonth()];
    const year = now.getFullYear();

    liveDateEl.innerText = `ថ្ងៃ${dayName} ទី${dateNum} ខែ${monthName} ឆ្នាំ${year}`;
}

/**
 * Global Toast Notification (supports both showToast(msg, type) and showToast(title, msg, type))
 */
function showToast(arg1, arg2 = 'info', arg3 = null) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    let title = '';
    let message = '';
    let type = 'info';
    let duration = 4500;

    if (arg3 !== null && typeof arg3 === 'string') {
        title = arg1;
        message = arg2;
        type = arg3;
    } else if (typeof arg2 === 'number') {
        message = arg1;
        duration = arg2;
    } else {
        message = arg1;
        type = arg2 || 'info';
        if (typeof arg3 === 'number') duration = arg3;
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = 'fa-circle-info';
    if (type === 'success') icon = 'fa-circle-check';
    else if (type === 'danger') icon = 'fa-triangle-exclamation';
    else if (type === 'warning') icon = 'fa-circle-exclamation';

    let contentHtml = `<i class="fa-solid ${icon}"></i>`;
    if (title) {
        contentHtml += `<div><strong style="display:block; font-size:0.9rem;">${title}</strong><span style="font-size:0.84rem;">${message}</span></div>`;
    } else {
        contentHtml += `<span>${message}</span>`;
    }

    toast.innerHTML = contentHtml;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/**
 * Trigger Google Sheets Sync via AJAX
 */
function triggerGoogleSheetsSync() {
    const btn = document.getElementById('btnSyncNow');
    const originalContent = btn ? btn.innerHTML : '';
    if (btn) {
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> កំពុង Sync...';
        btn.disabled = true;
    }

    showToast('កំពុងចាប់ផ្ដើម Sync ទិន្នន័យទៅកាន់ Google Sheets...', 'info');

    fetch('/api/sync/push-sheets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success', 6000);
            const display = document.getElementById('lastSyncDisplay');
            if (display && data.sync_time) {
                display.innerText = data.sync_time;
            }
        } else {
            showToast(data.message, 'warning', 6000);
        }
    })
    .catch(err => {
        showToast('កំហុសក្នុងការ Sync ទៅ Google Sheets៖ ' + err, 'danger', 6000);
    })
    .finally(() => {
        if (btn) {
            btn.innerHTML = originalContent;
            btn.disabled = false;
        }
    });
}
