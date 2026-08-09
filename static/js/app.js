document.addEventListener('DOMContentLoaded', () => {
    BCWAApp.init();
});

const BCWAApp = {
    inactivityTimer: null,
    INACTIVITY_TIMEOUT_MS: 300000, // 5 minutes (300 seconds) inactivity auto-logout
    
    init() {
        this.bindAuth();
        this.bindNavigation();
        this.bindGlobalSearch();
        this.bindModals();
        this.bindFormSubmissions();
        this.bindOCRScanner();
        this.bindInactivityTracker();
        this.preventBackNavigation();
        this.checkAuth();
    },

    bindInactivityTracker() {
        const events = ['mousemove', 'mousedown', 'click', 'keydown', 'scroll', 'touchstart', 'pointermove'];
        events.forEach(evt => {
            window.addEventListener(evt, () => this.resetInactivityTimer(), { passive: true });
        });
    },

    resetInactivityTimer() {
        if (!this.currentUser) return;
        clearTimeout(this.inactivityTimer);
        this.inactivityTimer = setTimeout(() => {
            this.handleSessionTimeout();
        }, this.INACTIVITY_TIMEOUT_MS);
    },

    async handleSessionTimeout() {
        clearTimeout(this.inactivityTimer);
        try {
            await fetch('/api/auth/timeout', { method: 'POST' });
        } catch (e) {}
        
        this.currentUser = null;
        this.showLoginScreen('You have been automatically signed out due to 5 minutes of inactivity. Please sign in again.');
    },

    preventBackNavigation() {
        window.addEventListener('pageshow', (event) => {
            if (event.persisted) {
                window.location.reload();
            }
        });
    },

    // -------------------------------------------------------------------------
    // AUTHENTICATION & LOGIN HANDLERS
    // -------------------------------------------------------------------------
    switchLoginTab(mode) {
        const adminTab = document.getElementById('tab-login-admin');
        const storeTab = document.getElementById('tab-login-store');
        const modeInput = document.getElementById('login-mode');
        const labelUser = document.getElementById('lbl-login-user');
        const userInput = document.getElementById('login-username');
        const submitTxt = document.getElementById('txt-login-submit');
        const footerTxt = document.getElementById('login-footer-text');
        const alertBox = document.getElementById('login-error-alert');

        if (alertBox) alertBox.classList.add('hidden');

        if (mode === 'store') {
            if (adminTab) adminTab.classList.remove('active');
            if (storeTab) storeTab.classList.add('active');
            if (modeInput) modeInput.value = 'store';
            if (labelUser) labelUser.textContent = 'Firm ID *';
            if (userInput) { userInput.value = ''; }
            if (submitTxt) submitTxt.textContent = 'Sign In to Store Portal';
            if (footerTxt) footerTxt.innerHTML = 'Registered Medical Store Access. Demo Accounts: <code>MED0001</code> to <code>MED0005</code> (Pass: <code>BCWA@123</code>)';
        } else {
            if (storeTab) storeTab.classList.remove('active');
            if (adminTab) adminTab.classList.add('active');
            if (modeInput) modeInput.value = 'admin';
            if (labelUser) labelUser.textContent = 'Officer ID / Username *';
            if (userInput) { userInput.value = ''; }
            if (submitTxt) submitTxt.textContent = 'Sign In to Admin Portal';
            if (footerTxt) footerTxt.innerHTML = 'Only authorized BCWA administrators and registered medical stores can access this portal.';
        }
        lucide.createIcons();
    },

    bindAuth() {
        const loginForm = document.getElementById('form-login');
        const logoutBtn = document.getElementById('btn-logout');

        loginForm?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const mode = document.getElementById('login-mode')?.value || 'admin';
            const usernameInput = document.getElementById('login-username');
            const passwordInput = document.getElementById('login-password');
            const submitBtn = document.getElementById('btn-login-submit');
            const submitTxt = document.getElementById('txt-login-submit');
            const username = usernameInput ? usernameInput.value.trim() : '';
            const password = passwordInput ? passwordInput.value.trim() : '';
            const alertBox = document.getElementById('login-error-alert');

            if (alertBox) alertBox.classList.add('hidden');
            if (submitBtn) submitBtn.disabled = true;
            if (submitTxt) submitTxt.textContent = 'Authenticating...';

            const endpoint = mode === 'store' ? '/api/auth/store-login' : '/api/auth/login';
            const payload = mode === 'store' ? { firm_id: username, password } : { officer_id: username, username, password };

            try {
                const res = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await res.json();

                if (res.ok && data.success) {
                    this.currentUser = data.user;
                    this.renderAuthenticatedUI();
                    return;
                } else if (alertBox) {
                    alertBox.textContent = data.error || 'Invalid Credentials';
                    alertBox.classList.remove('hidden');
                    return;
                }
            } catch (err) {
                if (alertBox) {
                    alertBox.textContent = 'Server connection error. Please try again.';
                    alertBox.classList.remove('hidden');
                }
            } finally {
                if (submitBtn) submitBtn.disabled = false;
                if (submitTxt) submitTxt.textContent = mode === 'store' ? 'Sign In to Store Portal' : 'Sign In to Admin Portal';
            }
        });

        logoutBtn?.addEventListener('click', async () => {
            await this.logout();
        });
    },

    async checkAuth() {
        try {
            const res = await fetch('/api/auth/session');
            const data = await res.json();
            if (res.ok && data.authenticated && data.user) {
                this.currentUser = data.user;
                this.renderAuthenticatedUI();
                return;
            } else if (data && data.reason === 'timeout') {
                this.currentUser = null;
                this.showLoginScreen('Session expired due to inactivity.');
                return;
            }
        } catch (e) {}

        this.currentUser = null;
        this.showLoginScreen();
    },

    async logout() {
        clearTimeout(this.inactivityTimer);
        try {
            await fetch('/api/auth/logout', { method: 'POST' });
        } catch (e) {}
        this.currentUser = null;
        this.showLoginScreen();
    },

    showLoginScreen(message = null) {
        clearTimeout(this.inactivityTimer);
        const usernameInput = document.getElementById('login-username');
        const passwordInput = document.getElementById('login-password');
        const alertBox = document.getElementById('login-error-alert');

        if (usernameInput) usernameInput.value = '';
        if (passwordInput) passwordInput.value = '';

        if (message && alertBox) {
            alertBox.textContent = message;
            alertBox.classList.remove('hidden');
        } else if (alertBox) {
            alertBox.classList.add('hidden');
        }

        document.getElementById('login-screen')?.classList.remove('hidden');
        document.querySelector('.app-layout')?.classList.add('hidden');
        lucide.createIcons();
    },

    renderAuthenticatedUI() {
        document.getElementById('login-screen')?.classList.add('hidden');
        document.querySelector('.app-layout')?.classList.remove('hidden');

        const adminNav = document.getElementById('admin-nav-menu');
        const storeNav = document.getElementById('store-nav-menu');

        if (this.currentUser) {
            const avatarEl = document.getElementById('sidebar-avatar');
            const userNameEl = document.getElementById('sidebar-user-name') || document.getElementById('current-user-name');
            const userRoleEl = document.getElementById('sidebar-user-role') || document.getElementById('current-user-role');
            
            if (avatarEl) avatarEl.textContent = this.currentUser.name ? this.currentUser.name.charAt(0).toUpperCase() : 'U';
            if (userNameEl) userNameEl.textContent = this.currentUser.name || 'User';

            if (this.currentUser.role === 'Store') {
                if (userRoleEl) userRoleEl.textContent = `Firm ID: ${this.currentUser.firm_id} • Store Owner`;
                if (adminNav) adminNav.classList.add('hidden');
                if (storeNav) storeNav.classList.remove('hidden');
                this.switchTab('store-dashboard');
                this.loadStoreDashboardData();
            } else {
                if (userRoleEl) userRoleEl.textContent = `Officer ID: ${this.currentUser.officer_id || 'VIN2821'} • Administrator`;
                if (storeNav) storeNav.classList.add('hidden');
                if (adminNav) adminNav.classList.remove('hidden');
                this.switchTab('dashboard');
                this.loadDashboardData();
            }
        }

        this.resetInactivityTimer();
        lucide.createIcons();
    },


    // -------------------------------------------------------------------------
    // NAVIGATION & TAB ROUTING (STRICTLY 8 PANES)
    // -------------------------------------------------------------------------
    bindNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const tab = item.dataset.tab;
                this.switchTab(tab);
            });
        });

        document.getElementById('btn-nav-stores')?.addEventListener('click', () => {
            this.switchTab('medical-stores');
        });
    },

    switchTab(tabId) {
        this.currentTab = tabId;
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));

        const targetNav = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
        const targetPane = document.getElementById(`pane-${tabId}`);

        if (targetNav) targetNav.classList.add('active');
        if (targetPane) targetPane.classList.add('active');

        switch (tabId) {
            case 'dashboard':
                this.loadDashboardData();
                break;
            case 'medical-stores':
                this.loadMedicalStores();
                break;
            case 'pharmacists':
                this.loadPharmacists();
                break;
            case 'document-vault':
                this.loadDocumentVault();
                break;
            case 'renewal-calendar':
                this.loadRenewalCalendar();
                break;
            case 'notifications':
                this.loadNotifications();
                break;
            case 'activity-logs':
                this.loadActivityLogs();
                break;
            case 'admin':
                this.loadAdminUsers();
                break;
            case 'store-dashboard':
                this.loadStoreDashboardData();
                break;
            case 'store-documents':
                this.loadStoreDocuments();
                break;
            case 'store-renewals':
                this.loadStoreRenewals();
                break;
            case 'store-notifications':
                this.loadStoreNotifications();
                break;
            case 'store-profile':
                this.loadStoreProfile();
                break;
        }

        lucide.createIcons();
    },

    // -------------------------------------------------------------------------
    // STORE SELF-SERVICE PORTAL FUNCTIONS
    // -------------------------------------------------------------------------
    async loadStoreDashboardData() {
        try {
            const res = await fetch('/api/store/dashboard');
            if (res.status === 403) return;
            const data = await res.json();

            const nameEl = document.getElementById('sd-store-name');
            const badgeEl = document.getElementById('sd-firm-badge');
            const scoreEl = document.getElementById('sd-compliance-score');
            const dlStatusEl = document.getElementById('sd-dl-status');
            const dlExpEl = document.getElementById('sd-dl-expiry');
            const fssaiStatusEl = document.getElementById('sd-fssai-status');
            const fssaiExpEl = document.getElementById('sd-fssai-expiry');
            const pppStatusEl = document.getElementById('sd-ppp-status');
            const pppExpEl = document.getElementById('sd-ppp-expiry');

            if (nameEl) nameEl.textContent = data.store_name || 'Medical Store Dashboard';
            if (badgeEl) badgeEl.textContent = `Firm ID: ${data.firm_id}`;
            if (scoreEl) scoreEl.textContent = `${data.compliance_score}%`;
            if (dlStatusEl) dlStatusEl.textContent = data.dl_status;
            if (dlExpEl) dlExpEl.textContent = `Exp: ${data.dl_expiry_date}`;
            if (fssaiStatusEl) fssaiStatusEl.textContent = data.fssai_status;
            if (fssaiExpEl) fssaiExpEl.textContent = `Exp: ${data.fssai_expiry_date}`;
            if (pppStatusEl) pppStatusEl.textContent = data.ppp_status;
            if (pppExpEl) pppExpEl.textContent = `Exp: ${data.ppp_expiry_date}`;

            const notifContainer = document.getElementById('sd-notifications-list');
            if (notifContainer && data.notifications) {
                if (data.notifications.length === 0) {
                    notifContainer.innerHTML = '<div class="text-center text-muted p-3">No pending notifications. All license compliance active.</div>';
                } else {
                    notifContainer.innerHTML = data.notifications.map(n => `
                        <div class="p-3 mb-2" style="border-left: 4px solid ${n.type === 'Danger' ? '#EF4444' : '#F59E0B'}; background:#F8FAFC; border-radius:4px;">
                            <strong>${n.title}</strong>
                            <p class="text-secondary mb-1" style="font-size:12px;">${n.message}</p>
                            <small class="text-muted">${n.created_at}</small>
                        </div>
                    `).join('');
                }
            }
            lucide.createIcons();
        } catch (e) {
            console.error('Error loading store dashboard:', e);
        }
    },

    async deleteDocument(docId) {
        if (!confirm('Are you sure you want to delete this document from Supabase Storage?')) return;
        try {
            const res = await fetch(`/api/documents/${docId}`, { method: 'DELETE' });
            const data = await res.json();
            if (res.ok && data.success) {
                if (typeof this.showToast === 'function') {
                    this.showToast('Document deleted successfully from Supabase Storage.', 'success');
                } else {
                    alert('Document deleted successfully from Supabase Storage.');
                }
                this.loadDocumentVault();
            } else {
                alert(data.error || 'Failed to delete document.');
            }
        } catch (err) {
            alert('Error deleting document: ' + err.message);
        }
    },

    async loadStoreDocuments() {
        try {
            const res = await fetch('/api/store/documents');
            const data = await res.json();
            const grid = document.getElementById('sd-document-grid');
            if (!grid) return;

            if (!data.documents || data.documents.length === 0) {
                grid.innerHTML = '<div class="text-center text-muted p-4 col-span-full">No documents found in vault.</div>';
                return;
            }

            grid.innerHTML = data.documents.map(d => `
                <div class="card p-3 shadow-sm" style="display:flex; flex-direction:column; justify-content:space-between;">
                    <div>
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <span class="badge badge-info">${d.category}</span>
                            <span class="badge ${d.quality_status === 'Passed' ? 'badge-success' : 'badge-warning'}">${d.quality_status}</span>
                        </div>
                        <h4 style="font-size:15px; margin-bottom:4px;">${d.title}</h4>
                        <div class="text-secondary" style="font-size:12px; margin-bottom:8px;">Ref #: <code>${d.document_number || 'N/A'}</code></div>
                        <div class="text-secondary" style="font-size:12px;">Expiry Date: <strong>${d.expiry_date || 'N/A'}</strong></div>
                    </div>
                    <div class="d-flex gap-2 mt-3 pt-2" style="border-top:1px solid #F1F5F9;">
                        <a href="/api/documents/${d.id}/preview" target="_blank" class="action-btn btn-action-preview" style="width:48%;"><i data-lucide="eye"></i> Preview</a>
                        <a href="/api/store/documents/${d.id}/download" class="action-btn btn-action-download" style="width:48%;"><i data-lucide="download"></i> Download PDF</a>
                    </div>
                </div>
            `).join('');
            lucide.createIcons();
        } catch (e) {
            console.error('Error loading store documents:', e);
        }
    },

    async loadStoreRenewals() {
        try {
            const res = await fetch('/api/store/renewals');
            const data = await res.json();
            const tbody = document.querySelector('#table-store-renewals tbody');
            if (!tbody) return;

            if (!data.renewals || data.renewals.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted p-3">No active renewal records.</td></tr>';
                return;
            }

            tbody.innerHTML = data.renewals.map(r => {
                const badgeClass = r.color === 'Green' ? 'badge-success' : (r.color === 'Yellow' ? 'badge-info' : (r.color === 'Orange' ? 'badge-warning' : 'badge-danger'));
                return `
                    <tr>
                        <td><strong>${r.document}</strong></td>
                        <td>${r.expiry_date}</td>
                        <td><strong>${r.days_remaining} Days</strong></td>
                        <td><span class="badge ${badgeClass}">${r.status}</span></td>
                    </tr>
                `;
            }).join('');
            lucide.createIcons();
        } catch (e) {}
    },

    async loadStoreNotifications() {
        try {
            const res = await fetch('/api/store/dashboard');
            const data = await res.json();
            const feed = document.getElementById('sd-full-notifications-feed');
            if (feed && data.notifications) {
                feed.innerHTML = data.notifications.map(n => `
                    <div class="p-3 mb-2 card" style="border-left: 4px solid ${n.type === 'Danger' ? '#EF4444' : '#F59E0B'};">
                        <strong>${n.title}</strong>
                        <p class="text-secondary mb-1" style="font-size:12px;">${n.message}</p>
                        <small class="text-muted">${n.created_at}</small>
                    </div>
                `).join('');
            }
            lucide.createIcons();
        } catch (e) {}
    },

    async loadStoreProfile() {
        try {
            const res = await fetch('/api/store/profile');
            const data = await res.json();

            const fid = document.getElementById('sp-firm-id');
            const sname = document.getElementById('sp-store-name');
            const oname = document.getElementById('sp-owner-name');
            const email = document.getElementById('sp-email');
            const mobile = document.getElementById('sp-mobile');
            const addr = document.getElementById('sp-address');

            if (fid) fid.textContent = data.firm_id || '--';
            if (sname) sname.textContent = data.store_name || '--';
            if (oname) oname.textContent = data.owner_name || '--';
            if (email) email.textContent = data.email || '--';
            if (mobile) mobile.textContent = data.mobile || '--';
            if (addr) addr.textContent = data.address || '--';
        } catch (e) {}
    },

    async requestStorePasswordReset() {
        try {
            const res = await fetch('/api/store/request-password-reset', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                alert('🔑 Password Reset Request Submitted!\n\nYour request has been logged. The BCWA System Administrator will issue updated credentials.');
            }
        } catch (e) {
            alert('Failed submitting password reset request.');
        }
    },

    async submitChangePassword() {
        const oldPw = document.getElementById('cp-old-password').value.trim();
        const newPw = document.getElementById('cp-new-password').value.trim();
        const confirmPw = document.getElementById('cp-confirm-password').value.trim();
        const errEl = document.getElementById('cp-error-msg');
        const successEl = document.getElementById('cp-success-msg');

        errEl.style.display = 'none';
        successEl.style.display = 'none';

        if (!oldPw || !newPw || !confirmPw) {
            errEl.textContent = 'All fields are required.';
            errEl.style.display = 'block';
            return;
        }
        if (newPw.length < 4) {
            errEl.textContent = 'New password must be at least 4 characters.';
            errEl.style.display = 'block';
            return;
        }
        if (newPw !== confirmPw) {
            errEl.textContent = 'New password and confirmation do not match.';
            errEl.style.display = 'block';
            return;
        }

        try {
            const res = await fetch('/api/auth/change-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    old_password: oldPw,
                    new_password: newPw,
                    confirm_password: confirmPw
                })
            });
            const data = await res.json();
            if (data.success) {
                successEl.textContent = '✅ ' + data.message;
                successEl.style.display = 'block';
                document.getElementById('cp-old-password').value = '';
                document.getElementById('cp-new-password').value = '';
                document.getElementById('cp-confirm-password').value = '';
                setTimeout(() => closeModal('modal-change-password'), 2000);
            } else {
                errEl.textContent = data.error || 'Failed to change password.';
                errEl.style.display = 'block';
            }
        } catch (e) {
            errEl.textContent = 'Server error. Please try again.';
            errEl.style.display = 'block';
        }
    },

    bindGlobalSearch() {
        const input = document.getElementById('global-search-input');
        if (!input) return;

        let debounceTimer;
        input.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                const query = e.target.value.trim();
                if (this.currentTab === 'medical-stores') {
                    this.loadMedicalStores(query);
                } else if (this.currentTab === 'pharmacists') {
                    this.loadPharmacists(query);
                } else {
                    this.switchTab('medical-stores');
                    this.loadMedicalStores(query);
                }
            }, 300);
        });
    },

    async loadDashboardData() {
        try {
            const res = await fetch('/api/dashboard/stats');
            const data = await res.json();

            document.getElementById('kpi-total-stores').textContent = data.total_stores;
            document.getElementById('kpi-total-pharmacists').textContent = data.total_pharmacists;
            document.getElementById('kpi-dl-expiring').textContent = data.dl_expiring;
            document.getElementById('kpi-fssai-expiring').textContent = data.fssai_expiring;
            document.getElementById('kpi-ppp-expiring').textContent = data.ppp_expiring;
            document.getElementById('kpi-expired-docs').textContent = data.expired_documents;
            document.getElementById('kpi-compliance-score').textContent = `${data.compliance_score}%`;
            document.getElementById('kpi-upcoming-renewals').textContent = data.upcoming_renewals;
            document.getElementById('notif-badge-count').textContent = data.todays_notifications;

            const emailsSentEl = document.getElementById('kpi-emails-sent-today');
            const pendingEmailsEl = document.getElementById('kpi-pending-emails');
            const failedEmailsEl = document.getElementById('kpi-failed-emails');
            const lastRunEl = document.getElementById('kpi-last-reminder-run');

            if (emailsSentEl) emailsSentEl.textContent = data.emails_sent_today || 0;
            if (pendingEmailsEl) pendingEmailsEl.textContent = data.pending_emails || 0;
            if (failedEmailsEl) failedEmailsEl.textContent = data.failed_emails || 0;
            if (lastRunEl) lastRunEl.textContent = data.last_reminder_run || 'Never';

            const feed = document.getElementById('dashboard-activity-feed');
            if (feed && data.recent_activity) {
                feed.innerHTML = data.recent_activity.map(act => `
                    <div class="activity-item" style="display:flex; gap:10px; margin-bottom:12px; font-size:12px;">
                        <i data-lucide="check-circle" style="width:16px; color:#2563EB;"></i>
                        <div>
                            <strong>${act.action}</strong> - ${act.details}
                            <div class="text-secondary" style="font-size:11px;">${act.user_name} &bull; ${act.created_at}</div>
                        </div>
                    </div>
                `).join('');
            }

            const storesBody = document.querySelector('#table-recent-stores tbody');
            if (storesBody && data.recent_stores) {
                storesBody.innerHTML = data.recent_stores.map(st => `
                    <tr>
                        <td><strong>${st.store_name}</strong></td>
                        <td><code>${st.shop_code}</code></td>
                        <td>${st.owner_name}</td>
                        <td><span class="badge ${st.compliance_score >= 90 ? 'badge-success' : 'badge-warning'}">${st.compliance_score}% - ${st.compliance_status}</span></td>
                        <td><span class="badge badge-info">Active</span></td>
                        <td><button class="btn btn-secondary btn-sm" onclick="BCWAApp.openStoreProfile('${st.id}')">View</button></td>
                    </tr>
                `).join('');
            }

            lucide.createIcons();
        } catch (err) {
            console.error('Error loading dashboard stats:', err);
        }
    },

    pages: {
        stores: 1,
        pharmacists: 1,
        documents: 1,
        notifications: 1,
        activity: 1
    },

    renderPagination(containerId, moduleName, page, totalPages, totalItems) {
        const container = document.getElementById(containerId);
        if (!container) return;
        if (!totalPages || totalPages <= 1) {
            container.innerHTML = `<div class="text-secondary text-end" style="font-size:12px; padding:6px 0;">Showing ${totalItems} records</div>`;
            return;
        }
        container.innerHTML = `
            <div class="d-flex justify-content-between align-items-center w-100 py-2" style="font-size:13px;">
                <div class="text-secondary">
                    Page <strong>${page}</strong> of <strong>${totalPages}</strong> (${totalItems} total)
                </div>
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-secondary ${page <= 1 ? 'disabled' : ''}" ${page <= 1 ? 'disabled' : ''} onclick="BCWAApp.changePage('${moduleName}', ${page - 1})">
                        <i data-lucide="chevron-left"></i> Prev
                    </button>
                    <button class="btn btn-secondary ${page >= totalPages ? 'disabled' : ''}" ${page >= totalPages ? 'disabled' : ''} onclick="BCWAApp.changePage('${moduleName}', ${page + 1})">
                        Next <i data-lucide="chevron-right"></i>
                    </button>
                </div>
            </div>
        `;
        lucide.createIcons();
    },

    changePage(moduleName, newPage) {
        if (newPage < 1) return;
        this.pages[moduleName] = newPage;
        if (moduleName === 'stores') this.loadMedicalStores('', newPage);
        else if (moduleName === 'pharmacists') this.loadPharmacists('', newPage);
        else if (moduleName === 'documents') this.loadDocumentVault('All', newPage);
        else if (moduleName === 'notifications') this.loadNotifications(newPage);
        else if (moduleName === 'activity') this.loadActivityLogs(newPage);
    },

    async loadMedicalStores(query = '', page = 1) {
        try {
            this.pages.stores = page;
            const comp = document.getElementById('filter-store-compliance')?.value || '';
            const status = document.getElementById('filter-store-status')?.value || '';

            const res = await fetch(`/api/stores?query=${encodeURIComponent(query)}&compliance=${comp}&status=${status}&page=${page}&limit=25`);
            const data = await res.json();
            const storeItems = data.items || data.stores || [];
            this.storesCache = storeItems;

            const tbody = document.querySelector('#table-medical-stores tbody');
            if (!tbody) return;

            if (storeItems.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" class="text-center text-secondary py-4">No matching Medical Stores found.</td></tr>`;
                this.renderPagination('pagination-medical-stores', 'stores', 1, 1, 0);
                return;
            }

            tbody.innerHTML = storeItems.map(st => {
                const badgeClass = st.compliance_score >= 90 ? 'badge-success' : (st.compliance_score >= 75 ? 'badge-info' : (st.compliance_score >= 50 ? 'badge-warning' : 'badge-danger'));
                return `
                    <tr>
                        <td>
                            <div><strong>${st.store_name}</strong></div>
                            <small class="text-secondary">Code: <code>${st.shop_code}</code></small>
                        </td>
                        <td>
                            <div>${st.owner_name}</div>
                            <small class="text-secondary">${st.owner_mobile}</small>
                        </td>
                        <td>
                            <div>20B: ${st.dl_20b_number}</div>
                            <small class="text-secondary">Exp: ${st.dl_expiry_date}</small>
                        </td>
                        <td>
                            <div>FSSAI: ${st.fssai_number}</div>
                            <small class="text-secondary">Exp: ${st.fssai_expiry_date}</small>
                        </td>
                        <td>
                            <span class="badge badge-info">${st.pharmacist_count} Pharmacists</span>
                        </td>
                        <td>
                            <span class="badge ${badgeClass}">${st.compliance_score}% &bull; ${st.compliance_status}</span>
                        </td>
                        <td>
                            <button class="btn btn-secondary btn-sm" onclick="BCWAApp.openStoreProfile('${st.id}')">Profile</button>
                            <button class="btn btn-secondary btn-sm" onclick="BCWAApp.editStore('${st.id}')">Edit</button>
                            <button class="btn btn-danger btn-sm" onclick="BCWAApp.deleteStore('${st.id}')">Delete</button>
                        </td>
                    </tr>
                `;
            }).join('');

            if (data.pages) {
                this.renderPagination('pagination-medical-stores', 'stores', page, data.pages, data.total);
            }

            lucide.createIcons();
        } catch (err) {
            console.error('Error loading medical stores:', err);
        }
    },

    async loadPharmacists(query = '', page = 1) {
        try {
            this.pages.pharmacists = page;
            const res = await fetch(`/api/pharmacists?query=${encodeURIComponent(query)}&page=${page}&limit=25`);
            const data = await res.json();
            const phItems = data.items || data.pharmacists || [];
            this.pharmacistsCache = phItems;

            const tbody = document.querySelector('#table-pharmacists tbody');
            if (!tbody) return;

            if (phItems.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" class="text-center text-secondary py-4">No registered Pharmacists found.</td></tr>`;
                this.renderPagination('pagination-pharmacists', 'pharmacists', 1, 1, 0);
                return;
            }

            tbody.innerHTML = phItems.map(ph => `
                <tr>
                    <td>
                        <strong>${ph.full_name}</strong>
                        <div class="text-secondary" style="font-size:11px;">Status: ${ph.status}</div>
                    </td>
                    <td>
                        <div><code>${ph.mspc_number}</code></div>
                        <small class="text-secondary">Reg Exp: <strong>${ph.reg_expiry || ph.ppp_expiry || 'N/A'}</strong></small>
                    </td>
                    <td>
                        <div><code>${ph.ppp_number}</code></div>
                        <small class="text-secondary">PPP Exp: <strong>${ph.ppp_expiry || 'N/A'}</strong></small>
                    </td>
                    <td>${ph.store_name ? `<strong>${ph.store_name}</strong>` : '<span class="text-muted">Unassigned</span>'}</td>
                    <td><span class="badge badge-info">${ph.qualification}</span></td>
                    <td>${ph.mobile}</td>
                    <td>
                        <button class="btn btn-secondary btn-sm" onclick="BCWAApp.openTransferModal('${ph.id}', '${ph.full_name}')">Transfer</button>
                        <button class="btn btn-danger btn-sm" onclick="BCWAApp.deletePharmacist('${ph.id}')">Delete</button>
                    </td>
                </tr>
            `).join('');

            if (data.pages) {
                this.renderPagination('pagination-pharmacists', 'pharmacists', page, data.pages, data.total);
            }

            lucide.createIcons();
        } catch (err) {
            console.error('Error loading pharmacists:', err);
        }
    },

    async loadDocumentVault(category = 'All', page = 1) {
        try {
            this.pages.documents = page;
            const catParam = category === 'All' ? '' : category;
            const res = await fetch(`/api/documents?category=${encodeURIComponent(catParam)}&page=${page}&limit=25`);
            const data = await res.json();
            const docItems = data.items || data.documents || [];

            const catEl = document.getElementById('vault-current-category');
            const countEl = document.getElementById('vault-doc-count');
            if (catEl) catEl.textContent = category === 'All' ? 'All Document Categories' : category;
            if (countEl) countEl.textContent = `${data.total || docItems.length} files`;

            const tbody = document.querySelector('#table-documents tbody');
            if (!tbody) return;

            if (docItems.length === 0) {
                tbody.innerHTML = `<tr><td colspan="6" class="text-center text-secondary py-4">No documents found in folder.</td></tr>`;
                this.renderPagination('pagination-documents', 'documents', 1, 1, 0);
                return;
            }

            tbody.innerHTML = docItems.map(doc => {
                const expBadge = doc.expiry_status === 'Expired'
                    ? `<span class="badge badge-danger">Expired</span>`
                    : (doc.expiry_status === 'Expiring in 30 Days'
                        ? `<span class="badge badge-warning">Expiring Soon (${doc.days_remaining}d)</span>`
                        : `<span class="badge badge-success">${doc.expiry_date || 'N/A'}</span>`);

                return `
                <tr>
                    <td>
                        <strong>${doc.title}</strong>
                        <div class="text-secondary" style="font-size:11px;">${doc.file_name} &bull; ${doc.file_size_kb} KB</div>
                    </td>
                    <td>${doc.store_name || 'System Doc'} <br><small class="text-secondary">${doc.shop_code || ''}</small></td>
                    <td><span class="badge badge-info">${doc.category}</span></td>
                    <td>
                        <span class="badge ${doc.quality_status === 'Passed' ? 'badge-success' : 'badge-warning'}">
                            ${doc.quality_status}
                        </span>
                        <div class="text-secondary" style="font-size:10px;">${doc.quality_notes}</div>
                    </td>
                    <td>${expBadge}</td>
                    <td>
                        <div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap;">
                            <a href="/api/documents/${doc.id}/preview" target="_blank" class="action-btn btn-action-preview"><i data-lucide="eye"></i> Preview</a>
                            <a href="/api/documents/${doc.id}/download" download class="action-btn btn-action-download" style="background:var(--primary-color, #0f172a); color:white;"><i data-lucide="download"></i> Download</a>
                            <button class="action-btn btn-action-resend" onclick="BCWAApp.viewDocumentVersions('${doc.id}')"><i data-lucide="history"></i> v${doc.version || 1}</button>
                            <button class="action-btn btn-action-delete" style="background:#ef4444; color:white;" onclick="BCWAApp.deleteDocument('${doc.id}')"><i data-lucide="trash-2"></i> Delete</button>
                        </div>
                    </td>
                </tr>
            `;}).join('');

            if (data.pages) {
                this.renderPagination('pagination-documents', 'documents', page, data.pages, data.total);
            }

            lucide.createIcons();
        } catch (err) {
            console.error('Error loading document vault:', err);
        }
    },

    async viewDocumentVersions(docId) {
        try {
            const res = await fetch(`/api/documents/${docId}/versions`);
            const data = await res.json();
            if (!res.ok || !data.success) {
                alert(data.error || 'Failed loading document versions.');
                return;
            }

            const current = data.current || {};
            const versions = data.versions || [];

            const titleEl = document.getElementById('ver-doc-title');
            const metaEl = document.getElementById('ver-doc-meta');
            const badgeEl = document.getElementById('ver-doc-badge');
            const tbody = document.getElementById('tbody-doc-versions');

            if (titleEl) titleEl.textContent = current.title || current.file_name || 'Document Details';
            if (metaEl) metaEl.textContent = `Firm ID: ${current.firm_id || 'BCWA-MED-000001'} | Category: ${current.category || 'Standard'}`;
            if (badgeEl) badgeEl.textContent = `v${current.version || 1} (Latest)`;

            if (tbody) {
                tbody.innerHTML = versions.map(v => `
                    <tr>
                        <td><span class="badge ${v.is_latest ? 'badge-primary' : 'badge-secondary'}">v${v.version || 1}</span></td>
                        <td><strong>${v.file_name || 'document.pdf'}</strong></td>
                        <td>${v.file_size_kb ? v.file_size_kb + ' KB' : '250 KB'}</td>
                        <td>${v.uploaded_by || 'Administrator'}</td>
                        <td><small>${v.upload_time || v.created_at || 'Just now'}</small></td>
                        <td>
                            <span class="badge ${v.is_latest ? 'badge-success' : 'badge-info'}">
                                ${v.is_latest ? 'Active' : 'Archived'}
                            </span>
                        </td>
                        <td>
                            <a href="${v.file_url}" target="_blank" class="action-btn btn-action-download">
                                <i data-lucide="download"></i> Download PDF
                            </a>
                        </td>
                    </tr>
                `).join('');
            }

            openModal('modal-doc-versions');
            lucide.createIcons();
        } catch (e) {
            alert('Error fetching document versions.');
        }
    },

    async loadRenewalCalendar() {
        try {
            const res = await fetch('/api/calendar/events');
            const data = await res.json();

            const grid = document.getElementById('calendar-grid');
            if (!grid) return;

            grid.innerHTML = '';
            for (let day = 1; day <= 31; day++) {
                const dayStr = `2026-08-${day < 10 ? '0' + day : day}`;
                const dayEvents = data.events.filter(e => e.date === dayStr);

                const cell = document.createElement('div');
                cell.className = 'calendar-cell';
                cell.innerHTML = `
                    <div class="calendar-cell-date">${day} Aug</div>
                    ${dayEvents.map(ev => `
                        <div class="calendar-event event-${ev.status.toLowerCase()}" onclick="BCWAApp.openStoreProfile('${ev.store_id}')">
                            ${ev.type}: ${ev.store_name}
                        </div>
                    `).join('')}
                `;
                grid.appendChild(cell);
            }
        } catch (err) {
            console.error('Error loading calendar:', err);
        }
    },

    async loadNotifications(page = 1) {
        try {
            this.pages.notifications = page;
            const [notifRes, qRes, logRes] = await Promise.all([
                fetch('/api/notifications'),
                fetch('/api/notifications/queue'),
                fetch(`/api/notifications/logs?page=${page}&limit=25`)
            ]);

            if (notifRes.status === 401 || logRes.status === 401) return;

            const [data, qData, logData] = await Promise.all([
                notifRes.json(),
                qRes.json(),
                logRes.json()
            ]);

            const container = document.getElementById('notifications-list');
            if (container && data.notifications) {
                if (data.notifications.length === 0) {
                    container.innerHTML = `<div class="text-center text-muted p-3">No unread notifications.</div>`;
                } else {
                    container.innerHTML = data.notifications.slice(0, 20).map(n => `
                        <div class="notif-item card mb-2 p-3" style="border-left: 4px solid ${n.type === 'Danger' ? '#EF4444' : '#F59E0B'}; display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <strong>${n.title}</strong>
                                <p class="text-secondary" style="font-size:12px; margin-top:2px;">${n.message}</p>
                                <small class="text-muted">${n.created_at}</small>
                            </div>
                            <button class="btn btn-secondary btn-sm" onclick="BCWAApp.markRead('${n.id}')">Dismiss</button>
                        </div>
                    `).join('');
                }
            }

            // Fetch Notification Queue Items
            const qTbody = document.querySelector('#table-notification-queue tbody');
            if (qTbody && qData.queue) {
                if (qData.queue.length === 0) {
                    qTbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted p-3">Queue is empty. All reminder emails processed.</td></tr>';
                } else {
                    qTbody.innerHTML = qData.queue.map(q => `
                        <tr>
                            <td><code>${q.id}</code></td>
                            <td><strong>${q.recipient_name}</strong><br><small class="text-muted">${q.recipient_email}</small></td>
                            <td><span class="badge badge-info">${q.document_type}</span></td>
                            <td><strong>${q.days_remaining} Days</strong></td>
                            <td><span class="badge ${q.status === 'Sent' ? 'badge-success' : (q.status === 'Pending' ? 'badge-warning' : 'badge-danger')}">${q.status}</span></td>
                            <td>${q.retry_count || 0} / ${q.max_retries || 3}</td>
                            <td><small class="text-muted">${q.next_retry_at ? q.next_retry_at.split('T')[0] : 'Immediate'}</small></td>
                            <td>
                                <button class="btn btn-secondary btn-sm" onclick="BCWAApp.retryQueueItem('${q.id}')" title="Retry Queue Item"><i data-lucide="rotate-cw"></i> Retry</button>
                            </td>
                        </tr>
                    `).join('');
                }
            }

            // Fetch Automated Email Notification Dispatch Logs
            const logTbody = document.querySelector('#table-notification-logs tbody');
            const logsList = logData.logs || logData.items || [];
            if (logTbody) {
                if (logsList.length === 0) {
                    logTbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted p-3">No notification logs recorded.</td></tr>';
                    this.renderPagination('pagination-notification-logs', 'notifications', 1, 1, 0);
                } else {
                    logTbody.innerHTML = logsList.map(l => `
                        <tr>
                            <td><code>${l.id}</code></td>
                            <td><strong>${l.recipient_name}</strong><br><small class="text-muted">${l.recipient_email}</small></td>
                            <td><span class="badge badge-info">${l.document_type}</span></td>
                            <td><strong>${l.days_remaining} Days</strong></td>
                            <td><span class="badge ${l.delivery_status === 'Success' ? 'badge-success' : 'badge-danger'}">${l.delivery_status}</span></td>
                            <td><small class="text-muted">${l.sent_at}</small></td>
                            <td>
                                <div class="action-btn-group">
                                    <button class="action-btn btn-action-resend" onclick="BCWAApp.resendEmailNotice('${l.id}')" title="Resend Email"><i data-lucide="send"></i> Resend</button>
                                    <button class="action-btn btn-action-preview" onclick="window.open('/api/notifications/logs/${l.id}/preview', '_blank')" title="Preview Email HTML"><i data-lucide="eye"></i> Preview</button>
                                    <button class="action-btn btn-action-download" onclick="window.open('/api/notifications/logs/${l.id}/pdf', '_blank')" title="Download PDF Notice"><i data-lucide="download"></i> PDF</button>
                                </div>
                            </td>
                        </tr>
                    `).join('');
                }
            }

            if (logData.pages) {
                this.renderPagination('pagination-notification-logs', 'notifications', page, logData.pages, logData.total);
            }

            lucide.createIcons();
        } catch (err) {
            console.error('Error loading notifications:', err);
        }
    },

    async retryQueueItem(queueId) {
        try {
            const res = await fetch(`/api/notifications/queue/${queueId}/retry`, { method: 'POST' });
            if (res.status === 401) {
                alert('Session expired due to inactivity or server restart. Please sign in again.');
                this.showLoginModal();
                return;
            }
            const data = await res.json();
            if (data.success) {
                alert('Queue item retried successfully!');
                this.loadNotifications();
                this.loadDashboardData();
            } else {
                alert(`Retry failed: ${data.error}`);
            }
        } catch (e) {
            alert('Error connecting to server.');
        }
    },

    async runNotificationEngineScan() {
        const btn = document.getElementById('btn-run-notification-engine');
        if (btn) btn.disabled = true;
        try {
            const res = await fetch('/api/notifications/engine/run', { method: 'POST' });
            if (res.status === 401) {
                alert('Session expired due to inactivity or server restart. Please sign in again.');
                this.showLoginModal();
                if (btn) btn.disabled = false;
                return;
            }
            const data = await res.json();
            alert(`Renewal Engine Scan Complete:\n• ${data.summary.queued || 0} Email(s) Queued\n• ${data.summary.sent || 0} Email(s) Dispatched\n• ${data.summary.skipped || 0} Skipped (Duplicates Prevention)\n• ${data.summary.failed || 0} Failed`);
            this.loadNotifications();
            this.loadDashboardData();
        } catch (e) {
            alert('Failed to trigger Notification Engine scan.');
        }
        if (btn) btn.disabled = false;
    },

    async resendEmailNotice(logId) {
        try {
            const res = await fetch(`/api/notifications/logs/${logId}/resend`, { method: 'POST' });
            if (res.status === 401) {
                alert('Session expired due to inactivity or server restart. Please sign in again.');
                this.showLoginModal();
                return;
            }
            const data = await res.json();
            if (data.success) {
                alert('Notification email resent successfully!');
                this.loadNotifications();
                this.loadDashboardData();
            } else {
                alert(`Resend failed: ${data.error}`);
            }
        } catch (e) {
            alert('Error connecting to server.');
        }
    },

    async sendTestEmail() {
        const btn = document.getElementById('btn-send-test-email');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = 'Sending...';
        }

        try {
            const res = await fetch('/api/admin/send-test-email', { method: 'POST' });
            const data = await res.json();

            if (res.ok && data.success) {
                alert(`✅ Success!\n\n${data.message}\n\nSMTP Status: ${data.details.response}`);
            } else {
                alert(`❌ Email Dispatch Failed!\n\n${data.error || 'SMTP Connection Error'}`);
            }
        } catch (e) {
            alert(`❌ Exception: Could not connect to backend server (${e.message})`);
        }

        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i data-lucide="send"></i> Send Test Email';
            lucide.createIcons();
        }
    },

    async markRead(id) {
        await fetch(`/api/notifications/${id}/read`, { method: 'PUT' });
        this.loadNotifications();
    },

    async loadActivityLogs(page = 1) {
        try {
            this.pages.activity = page;
            const res = await fetch(`/api/activity-logs?page=${page}&limit=25`);
            const data = await res.json();
            const logItems = data.items || data.logs || [];
            const tbody = document.querySelector('#table-activity-logs tbody');

            if (!tbody) return;

            if (logItems.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" class="text-center text-secondary py-4">No activity logs recorded.</td></tr>`;
                this.renderPagination('pagination-activity-logs', 'activity', 1, 1, 0);
                return;
            }

            tbody.innerHTML = logItems.map(log => `
                <tr>
                    <td><code>${log.id || log.created_at}</code></td>
                    <td><strong>${log.user_name}</strong></td>
                    <td><span class="badge badge-info">${log.action}</span></td>
                    <td>${log.details}</td>
                    <td><small class="text-muted">${log.created_at}</small></td>
                </tr>
            `).join('');

            if (data.pages) {
                this.renderPagination('pagination-activity-logs', 'activity', page, data.pages, data.total);
            }

            lucide.createIcons();
        } catch (err) {
            console.error('Error loading activity logs:', err);
        }
    },

    async loadAdminUsers() {
        try {
            const res = await fetch('/api/admin/users');
            const data = await res.json();
            const tbody = document.querySelector('#table-admin-users tbody');

            if (!tbody) return;

            tbody.innerHTML = data.users.map(u => `
                <tr>
                    <td><strong>${u.name}</strong></td>
                    <td>${u.email}</td>
                    <td><span class="badge badge-info">${u.role}</span></td>
                    <td><span class="badge badge-success">${u.status}</span></td>
                    <td>${u.last_login}</td>
                    <td><button class="btn btn-secondary btn-sm">Edit Role</button></td>
                </tr>
            `).join('');
        } catch (err) {
            console.error('Error loading admin users:', err);
        }
    },

    async openStoreProfile(storeId) {
        try {
            const res = await fetch(`/api/stores/${storeId}`);
            if (!res.ok) return;

            const st = await res.json();
            const body = document.getElementById('store-profile-body');

            const badgeClass = st.compliance_score >= 90 ? 'badge-success' : (st.compliance_score >= 75 ? 'badge-info' : (st.compliance_score >= 50 ? 'badge-warning' : 'badge-danger'));

            body.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                    <div>
                        <h2 style="font-size:20px;">${st.store_name}</h2>
                        <p class="text-secondary">Shop Code: <code>${st.shop_code}</code> &bull; ID: ${st.id}</p>
                    </div>
                    <span class="badge ${badgeClass}" style="font-size:14px; padding:6px 12px;">${st.compliance_score}% &bull; ${st.compliance_status}</span>
                </div>

                <div style="background:#F8FAFC; padding:16px; border-radius:12px; margin-bottom:20px; border:1px solid #E5E7EB; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <h4 style="margin:0; font-size:15px; color:#0F172A; font-weight:600;">🪪 BCWA Smart Member Card</h4>
                        <small class="text-secondary">Official digital chemist membership card for ${st.store_name}</small>
                    </div>
                    <button class="btn btn-primary" onclick="BCWAApp.openSmartCardModal('${st.id}')" style="background:#2563eb; color:#fff; padding:8px 16px; border-radius:8px; font-weight:600;">
                        <i data-lucide="credit-card" style="width:16px; height:16px; vertical-align:middle;"></i> View Smart Card
                    </button>
                </div>

                <div class="card mb-3 p-3">
                    <h4 style="color:#2563EB; font-size:14px; margin-bottom:10px;">Owner Details</h4>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:13px;">
                        <div><strong>Owner Name:</strong> ${st.owner_name}</div>
                        <div><strong>Mobile:</strong> ${st.owner_mobile}</div>
                        <div><strong>Email:</strong> ${st.owner_email || 'N/A'}</div>
                        <div><strong>PAN:</strong> <code>${st.owner_pan || 'N/A'}</code></div>
                        <div style="grid-column:span 2;"><strong>Address:</strong> ${st.address_line1}, ${st.area}, Palghar - ${st.pincode}</div>
                    </div>
                </div>

                <div class="card mb-3 p-3">
                    <h4 style="color:#2563EB; font-size:14px; margin-bottom:10px;">Drug &amp; Food Licenses</h4>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:13px;">
                        <div><strong>20B Number:</strong> <code>${st.dl_20b_number}</code></div>
                        <div><strong>21B Number:</strong> <code>${st.dl_21b_number}</code></div>
                        <div><strong>DL Expiry:</strong> ${st.dl_expiry_date}</div>
                        <div><strong>FSSAI Number:</strong> <code>${st.fssai_number}</code></div>
                        <div><strong>FSSAI Expiry:</strong> ${st.fssai_expiry_date}</div>
                    </div>
                </div>

                <div class="card mb-3 p-3">
                    <h4 style="color:#2563EB; font-size:14px; margin-bottom:10px;">Assigned Pharmacists (${st.pharmacists ? st.pharmacists.length : 0})</h4>
                    ${st.pharmacists && st.pharmacists.length > 0 ? `
                        <ul style="list-style:none; padding:0;">
                            ${st.pharmacists.map(p => `
                                <li style="padding:6px 0; border-bottom:1px solid #E5E7EB; display:flex; justify-content:space-between;">
                                    <span><strong>${p.full_name}</strong> (MSPC: ${p.mspc_number})</span>
                                    <span class="badge badge-info">PPP Exp: ${p.ppp_expiry}</span>
                                </li>
                            `).join('')}
                        </ul>
                    ` : '<p class="text-secondary">No active pharmacists assigned.</p>'}
                </div>

                <div style="display:flex; gap:12px; margin-top:20px;">
                    <button class="btn btn-primary" onclick="BCWAApp.generateProfilePDF('${st.id}')">Download Profile PDF</button>
                    <button class="btn btn-danger" onclick="BCWAApp.deleteStore('${st.id}')">Delete Store</button>
                </div>
            `;

            document.getElementById('drawer-store-profile').classList.add('active');
            lucide.createIcons();
        } catch (err) {
            console.error('Error loading store profile:', err);
        }
    },

    bindOCRScanner() {
        const btnScan = document.getElementById('btn-ocr-scan');
        const dropzone = document.getElementById('ocr-dropzone');
        const fileInput = document.getElementById('ocr-file-input');

        btnScan?.addEventListener('click', () => {
            openModal('modal-ocr');
        });

        dropzone?.addEventListener('click', () => fileInput.click());

        fileInput?.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);
            formData.append('doc_type', 'Drug License');

            try {
                const res = await fetch('/api/ocr/extract', { method: 'POST', body: formData });
                const json = await res.json();

                if (json.success) {
                    const ext = json.data;
                    const output = document.getElementById('ocr-fields-output');
                    output.innerHTML = `
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:13px; text-align:left; background:#F8FAFC; padding:12px; border-radius:6px;">
                            <div><strong>Extracted Store:</strong> ${ext.store_name || 'N/A'}</div>
                            <div><strong>Owner:</strong> ${ext.owner_name || 'N/A'}</div>
                            <div><strong>20B License:</strong> ${ext.dl_20b_number || 'N/A'}</div>
                            <div><strong>21B License:</strong> ${ext.dl_21b_number || 'N/A'}</div>
                            <div><strong>Expiry Date:</strong> ${ext.expiry_date || 'N/A'}</div>
                        </div>
                    `;
                    document.getElementById('ocr-result-box').classList.remove('hidden');
                    document.getElementById('btn-apply-ocr').classList.remove('hidden');

                    document.getElementById('btn-apply-ocr').onclick = () => {
                        closeModal('modal-ocr');
                        this.openAddStoreModal(ext);
                    };
                }
            } catch (err) {
                console.error('OCR Error:', err);
            }
        });
    },

    bindModals() {
        document.getElementById('btn-add-store')?.addEventListener('click', () => this.openAddStoreModal());
        document.getElementById('btn-add-store-tab')?.addEventListener('click', () => this.openAddStoreModal());
        document.getElementById('btn-add-pharmacist')?.addEventListener('click', () => this.openAddPharmacistModal());
        document.getElementById('btn-upload-document')?.addEventListener('click', () => this.openUploadDocumentModal());
        document.getElementById('btn-generate-report')?.addEventListener('click', () => openModal('modal-report'));
        document.getElementById('btn-download-pdf-report')?.addEventListener('click', () => this.downloadPDFReport());

        document.querySelectorAll('#vault-folder-list li').forEach(li => {
            li.addEventListener('click', () => {
                document.querySelectorAll('#vault-folder-list li').forEach(el => el.classList.remove('active'));
                li.classList.add('active');
                this.loadDocumentVault(li.dataset.category);
            });
        });
    },

    toggleUploadExpiryFields() {
        const catSelect = document.getElementById('upload-doc-category');
        const expiryBox = document.getElementById('upload-expiry-fields');
        if (!catSelect || !expiryBox) return;

        const cat = catSelect.value;
        const permanentCategories = [
            "Electricity Bill (Light Bill)", "Light Bill", "Namuna 8", "Owner Aadhaar",
            "Owner PAN", "Owner Photo", "Owner Photograph", "Shop Photo", "Shop Photograph",
            "Store Photos", "Cancelled Cheque", "Bank Passbook", "Partnership Deed",
            "Property Documents", "Affidavits", "Other Documents", "Other Supporting Documents"
        ];

        if (permanentCategories.includes(cat)) {
            expiryBox.style.display = 'none';
            const issueInput = document.getElementById('upload-doc-issue-date');
            const expInput = document.getElementById('upload-doc-expiry-date');
            if (issueInput) issueInput.required = false;
            if (expInput) expInput.required = false;
        } else {
            expiryBox.style.display = 'block';
            const issueInput = document.getElementById('upload-doc-issue-date');
            const expInput = document.getElementById('upload-doc-expiry-date');
            if (issueInput) issueInput.required = true;
            if (expInput) expInput.required = true;
        }
    },

    async openUploadDocumentModal() {
        const storeSelect = document.getElementById('upload-doc-store-id');
        if (storeSelect) {
            storeSelect.innerHTML = '<option value="">Loading medical stores...</option>';
            try {
                const res = await fetch('/api/stores?limit=100');
                const data = await res.json();
                const stores = data.stores || [];
                storeSelect.innerHTML = stores.map(s => `<option value="${s.id}">${s.store_name} (${s.firm_id || s.shop_code})</option>`).join('');
            } catch (e) {
                storeSelect.innerHTML = '<option value="">Failed loading stores</option>';
            }
        }
        const form = document.getElementById('form-upload-document');
        if (form) form.reset();
        this.toggleUploadExpiryFields();
        openModal('modal-upload-document');
    },

    async submitUploadDocument(e) {
        if (e) e.preventDefault();
        const errEl = document.getElementById('upload-doc-error');
        if (errEl) errEl.style.display = 'none';

        const storeId = document.getElementById('upload-doc-store-id').value;
        const category = document.getElementById('upload-doc-category').value;
        const title = document.getElementById('upload-doc-title').value.trim();
        const docNumber = document.getElementById('upload-doc-number').value.trim();
        const issueDate = document.getElementById('upload-doc-issue-date').value;
        const expiryDate = document.getElementById('upload-doc-expiry-date').value;
        const reminderEnabled = document.getElementById('upload-doc-reminder').checked;
        const renewalRequired = document.getElementById('upload-doc-renewal-req').checked;
        const fileInput = document.getElementById('upload-doc-file');

        if (!fileInput || !fileInput.files.length) {
            if (errEl) { errEl.textContent = 'Please select a document file to upload.'; errEl.style.display = 'block'; }
            return;
        }

        const formData = new FormData();
        formData.append('store_id', storeId);
        formData.append('category', category);
        formData.append('title', title);
        formData.append('document_number', docNumber);
        formData.append('issue_date', issueDate);
        formData.append('expiry_date', expiryDate);
        formData.append('reminder_enabled', reminderEnabled ? 'true' : 'false');
        formData.append('renewal_required', renewalRequired ? 'true' : 'false');
        formData.append('file', fileInput.files[0]);

        const btnSubmit = document.getElementById('btn-submit-upload-doc');
        if (btnSubmit) btnSubmit.disabled = true;

        try {
            const res = await fetch('/api/documents/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (res.ok && data.success) {
                closeModal('modal-upload-document');
                this.loadDocumentVault();
                alert('✅ Document uploaded successfully!');
            } else {
                if (errEl) { errEl.textContent = data.error || 'Upload failed.'; errEl.style.display = 'block'; }
            }
        } catch (err) {
            if (errEl) { errEl.textContent = 'Network error uploading document.'; errEl.style.display = 'block'; }
        } finally {
            if (btnSubmit) btnSubmit.disabled = false;
        }
    },

    openAddStoreModal(ocrData = null) {
        document.getElementById('form-store').reset();
        document.getElementById('store-form-id').value = '';
        document.getElementById('modal-store-title').textContent = 'Register Medical Store';

        if (ocrData) {
            if (ocrData.store_name) document.getElementById('store-form-name').value = ocrData.store_name;
            if (ocrData.owner_name) document.getElementById('store-form-owner-name').value = ocrData.owner_name;
            if (ocrData.dl_20b_number) document.getElementById('store-form-dl-20b').value = ocrData.dl_20b_number;
            if (ocrData.dl_21b_number) document.getElementById('store-form-dl-21b').value = ocrData.dl_21b_number;
            if (ocrData.expiry_date) document.getElementById('store-form-dl-expiry').value = ocrData.expiry_date;
            if (ocrData.fssai_number) document.getElementById('store-form-fssai').value = ocrData.fssai_number;
        }

        openModal('modal-store');
    },

    async editStore(id) {
        const res = await fetch(`/api/stores/${id}`);
        const st = await res.json();

        document.getElementById('store-form-id').value = st.id;
        document.getElementById('store-form-name').value = st.store_name;
        document.getElementById('store-form-owner-name').value = st.owner_name;
        document.getElementById('store-form-owner-mobile').value = st.owner_mobile;
        document.getElementById('store-form-dl-20b').value = st.dl_20b_number;
        document.getElementById('store-form-dl-21b').value = st.dl_21b_number;
        document.getElementById('store-form-dl-issue').value = st.dl_issue_date;
        document.getElementById('store-form-dl-expiry').value = st.dl_expiry_date;
        document.getElementById('store-form-fssai').value = st.fssai_number;
        document.getElementById('store-form-fssai-expiry').value = st.fssai_expiry_date;
        document.getElementById('store-form-address').value = st.address_line1;

        document.getElementById('modal-store-title').textContent = 'Edit Medical Store';
        openModal('modal-store');
    },

    async deleteStore(id) {
        if (!confirm('Are you sure you want to delete this Medical Store record?')) return;
        try {
            const res = await fetch(`/api/stores/${id}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                if (typeof closeDrawer === 'function') closeDrawer('drawer-store-profile');
                this.loadMedicalStores();
                this.loadDashboardStats();
                if (typeof this.showToast === 'function') this.showToast('Medical Store deleted successfully', 'success');
            } else {
                alert(data.error || 'Failed to delete Medical Store');
            }
        } catch (e) {
            console.error('Error deleting store:', e);
            alert('Failed to delete Medical Store');
        }
    },

    openAddPharmacistModal() {
        document.getElementById('form-pharmacist').reset();
        document.getElementById('ph-form-id').value = '';

        const select = document.getElementById('ph-form-store-id');
        select.innerHTML = '<option value="">-- Select Store --</option>' +
            this.storesCache.map(s => `<option value="${s.id}">${s.store_name} (${s.shop_code})</option>`).join('');

        openModal('modal-pharmacist');
    },

    openTransferModal(phId, phName) {
        document.getElementById('transfer-ph-id').value = phId;
        document.getElementById('transfer-ph-name').textContent = phName;

        const select = document.getElementById('transfer-new-store-id');
        select.innerHTML = this.storesCache.map(s => `<option value="${s.id}">${s.store_name} (${s.shop_code})</option>`).join('');

        openModal('modal-transfer-pharmacist');

        document.getElementById('btn-confirm-transfer').onclick = async () => {
            const newStoreId = select.value;
            const joiningDate = document.getElementById('transfer-joining-date').value || new Date().toISOString().split('T')[0];

            await fetch(`/api/pharmacists/${phId}/transfer`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_store_id: newStoreId, joining_date: joiningDate })
            });

            closeModal('modal-transfer-pharmacist');
            this.loadPharmacists();
        };
    },

    async deletePharmacist(id) {
        if (!confirm('Delete this pharmacist record?')) return;
        await fetch(`/api/pharmacists/${id}`, { method: 'DELETE' });
        this.loadPharmacists();
    },

    bindFormSubmissions() {
        document.getElementById('form-store')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('store-form-id').value;

            const payload = {
                store_name: document.getElementById('store-form-name')?.value || '',
                business_type: document.getElementById('store-form-business-type')?.value || 'Retail Pharmacy',
                drug_license_category: document.getElementById('store-form-dl-cat')?.value || '20B / 21B',
                owner_name: document.getElementById('store-form-owner-name')?.value || '',
                owner_mobile: document.getElementById('store-form-owner-mobile')?.value || '',
                owner_whatsapp: document.getElementById('store-form-owner-whatsapp')?.value || '',
                owner_email: document.getElementById('store-form-owner-email')?.value || '',
                owner_pan: document.getElementById('store-form-owner-pan')?.value || '',
                owner_aadhaar: document.getElementById('store-form-owner-aadhaar')?.value || '',
                dl_20b_number: document.getElementById('store-form-dl-20b')?.value || '',
                dl_21b_number: document.getElementById('store-form-dl-21b')?.value || '',
                dl_issue_date: document.getElementById('store-form-dl-issue')?.value || '',
                dl_expiry_date: document.getElementById('store-form-dl-expiry')?.value || '',
                fssai_number: document.getElementById('store-form-fssai')?.value || '',
                fssai_expiry_date: document.getElementById('store-form-fssai-expiry')?.value || '',
                fssai_issue_date: document.getElementById('store-form-dl-issue')?.value || '',
                address_line1: document.getElementById('store-form-address')?.value || '',
                area: document.getElementById('store-form-area')?.value || 'Boisar'
            };

            const url = id ? `/api/stores/${id}` : '/api/stores';
            const method = id ? 'PUT' : 'POST';

            try {
                const res = await fetch(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await res.json();
                if (res.ok && data.success) {
                    closeModal('modal-store');
                    alert(id ? 'Medical Store updated successfully!' : 'Medical Store registered successfully!');
                    await this.loadMedicalStores();
                    await this.loadDashboardStats();
                    if (typeof this.loadActivityLogs === 'function') await this.loadActivityLogs();
                } else {
                    const warnBox = document.getElementById('store-duplicate-warning');
                    if (warnBox) {
                        warnBox.textContent = data.error || 'Failed to save Medical Store.';
                        warnBox.classList.remove('hidden');
                    } else {
                        alert(data.error || 'Failed to save Medical Store.');
                    }
                }
            } catch (err) {
                console.error('Store Registration Error:', err);
                alert('Network or server error occurred during registration.');
            }
        });

        document.getElementById('form-pharmacist')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                full_name: document.getElementById('ph-form-name').value,
                mspc_number: document.getElementById('ph-form-mspc').value,
                reg_expiry: document.getElementById('ph-form-reg-expiry').value,
                ppp_number: document.getElementById('ph-form-ppp').value,
                ppp_expiry: document.getElementById('ph-form-ppp-expiry').value,
                store_id: document.getElementById('ph-form-store-id').value,
                qualification: document.getElementById('ph-form-qualification').value,
                mobile: document.getElementById('ph-form-mobile').value,
                joining_date: new Date().toISOString().split('T')[0]
            };

            await fetch('/api/pharmacists', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            closeModal('modal-pharmacist');
            this.loadPharmacists();
        });
    },

    downloadPDFReport() {
        const type = document.getElementById('report-select-type').value;
        window.open(`/api/reports/generate?report_type=${encodeURIComponent(type)}`, '_blank');
        closeModal('modal-report');
    },

    generateProfilePDF(storeId) {
        window.open(`/api/reports/generate?report_type=Medical Store Profile PDF&store_id=${storeId}`, '_blank');
    },

    toggleSmartCardTab(tab) {
        const frontView = document.getElementById('smart-card-view-front');
        const backView = document.getElementById('smart-card-view-back');
        const btnFront = document.getElementById('btn-card-tab-front');
        const btnBack = document.getElementById('btn-card-tab-back');

        if (tab === 'back') {
            if (frontView) frontView.style.display = 'none';
            if (backView) backView.style.display = 'flex';
            if (btnFront) { btnFront.style.background = 'transparent'; btnFront.style.color = '#64748B'; }
            if (btnBack) { btnBack.style.background = '#0F172A'; btnBack.style.color = '#FFFFFF'; }
        } else {
            if (frontView) frontView.style.display = 'flex';
            if (backView) backView.style.display = 'none';
            if (btnFront) { btnFront.style.background = '#0F172A'; btnFront.style.color = '#FFFFFF'; }
            if (btnBack) { btnBack.style.background = 'transparent'; btnBack.style.color = '#64748B'; }
        }
    },

    openSmartCardModal(storeId) {
        const store = (this.stores || []).find(s => s.id === storeId || s.shop_code === storeId || s.shopCode === storeId);
        if (!store) return;

        document.getElementById('card-front-store-name').innerText = store.store_name || store.storeName || '-';
        document.getElementById('card-front-owner-name').innerText = store.owner_name || store.ownerName || '-';
        document.getElementById('card-front-mobile').innerText = store.owner_mobile || store.ownerMobile || '-';
        document.getElementById('card-front-store-id').innerText = store.id || '-';
        
        const addr = store.address_line1 || store.address || 'Boisar, Palghar - 401501';
        document.getElementById('card-front-address').innerText = addr;

        const loginId = store.id || store.shop_code || store.shopCode || '-';
        const initPass = store.initial_password || store.initialPassword || `${loginId.replace('-', '')}@2026`;
        
        document.getElementById('card-front-login-id').innerText = loginId;
        document.getElementById('card-front-password').innerText = initPass;

        this.toggleSmartCardTab('front');

        const waBtn = document.getElementById('btn-card-whatsapp');
        if (waBtn) {
            waBtn.onclick = () => {
                const mob = (store.owner_mobile || store.ownerMobile || '').replace(/[^0-9]/g, '');
                const cleanMob = mob.length === 10 ? '91' + mob : mob;
                const msg = `BCWA Smart Member Card for ${store.store_name} (${store.id})\nLogin ID: ${loginId}\nPassword: ${initPass}`;
                window.open(`https://api.whatsapp.com/send?phone=${cleanMob}&text=${encodeURIComponent(msg)}`, '_blank');
            };
        }

        openModal('modal-smart-card');
    }
};

function openModal(id) { document.getElementById(id)?.classList.add('active'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('active'); }
function closeDrawer(id) { document.getElementById(id)?.classList.remove('active'); }
