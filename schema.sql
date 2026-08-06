-- ============================================================================
-- BOISAR WELFARE CHEMIST ASSOCIATION (BCWA) PORTAL - SUPABASE SCHEMA
-- Database: Supabase PostgreSQL
-- ============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. USERS TABLE
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT DEFAULT 'Administrator',
    status TEXT DEFAULT 'Active',
    last_login TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. MEDICAL STORES TABLE
CREATE TABLE IF NOT EXISTS medical_stores (
    id TEXT PRIMARY KEY,
    store_name TEXT NOT NULL,
    shop_code TEXT UNIQUE NOT NULL,
    business_type TEXT DEFAULT 'Retail Pharmacy',
    drug_license_category TEXT DEFAULT '20B / 21B',
    owner_name TEXT NOT NULL,
    owner_mobile TEXT NOT NULL,
    owner_whatsapp TEXT,
    owner_email TEXT,
    owner_pan TEXT,
    owner_aadhaar TEXT,
    owner_address TEXT,
    owner_photo TEXT,
    store_logo TEXT,
    store_photo TEXT,
    contact_phone TEXT,
    contact_email TEXT,
    address_line1 TEXT NOT NULL,
    address_line2 TEXT,
    area TEXT DEFAULT 'Boisar',
    city TEXT DEFAULT 'Palghar',
    state TEXT DEFAULT 'Maharashtra',
    pincode TEXT DEFAULT '401501',
    google_map_url TEXT,
    gps_coordinates TEXT,
    dl_20b_number TEXT NOT NULL,
    dl_21b_number TEXT NOT NULL,
    dl_issue_date DATE NOT NULL,
    dl_expiry_date DATE NOT NULL,
    dl_issuing_authority TEXT DEFAULT 'FDA Maharashtra',
    dl_renewal_date DATE,
    fssai_number TEXT NOT NULL,
    fssai_issue_date DATE NOT NULL,
    fssai_expiry_date DATE NOT NULL,
    status TEXT DEFAULT 'Active',
    compliance_score INTEGER DEFAULT 100,
    compliance_status TEXT DEFAULT 'Excellent',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. PHARMACISTS TABLE
CREATE TABLE IF NOT EXISTS pharmacists (
    id TEXT PRIMARY KEY,
    store_id TEXT REFERENCES medical_stores(id) ON DELETE SET NULL,
    full_name TEXT NOT NULL,
    photo TEXT,
    mspc_number TEXT UNIQUE NOT NULL,
    ppp_number TEXT UNIQUE NOT NULL,
    ppp_expiry DATE NOT NULL,
    reg_expiry DATE NOT NULL,
    qualification TEXT DEFAULT 'B.Pharm',
    joining_date DATE,
    leaving_date DATE,
    mobile TEXT NOT NULL,
    email TEXT,
    status TEXT DEFAULT 'Active',
    ppp_card_url TEXT,
    degree_cert_url TEXT,
    reg_cert_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. DOCUMENTS TABLE
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    store_id TEXT REFERENCES medical_stores(id) ON DELETE CASCADE,
    category TEXT DEFAULT 'Drug License',
    title TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_url TEXT NOT NULL,
    file_size_kb INTEGER DEFAULT 300,
    version INTEGER DEFAULT 1,
    issue_date DATE,
    expiry_date DATE,
    quality_status TEXT DEFAULT 'Passed',
    quality_notes TEXT,
    uploaded_by TEXT DEFAULT 'Office Staff',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. RENEWALS TABLE
CREATE TABLE IF NOT EXISTS renewals (
    id TEXT PRIMARY KEY,
    store_id TEXT REFERENCES medical_stores(id) ON DELETE CASCADE,
    license_type TEXT NOT NULL,
    license_number TEXT NOT NULL,
    old_expiry_date DATE NOT NULL,
    new_expiry_date DATE,
    renewal_status TEXT DEFAULT 'Pending',
    applied_date DATE,
    approval_date DATE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. NOTIFICATIONS TABLE
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    store_id TEXT REFERENCES medical_stores(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT DEFAULT 'Warning',
    target_date DATE,
    days_remaining INTEGER,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. ACTIVITY LOGS TABLE
CREATE TABLE IF NOT EXISTS activity_logs (
    id TEXT PRIMARY KEY,
    user_name TEXT DEFAULT 'System',
    action TEXT NOT NULL,
    details TEXT NOT NULL,
    store_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. SETTINGS TABLE
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. NOTIFICATION LOGS TABLE (Automated Renewal Engine History)
CREATE TABLE IF NOT EXISTS notification_logs (
    id TEXT PRIMARY KEY,
    store_id TEXT REFERENCES medical_stores(id) ON DELETE CASCADE,
    pharmacist_id TEXT REFERENCES pharmacists(id) ON DELETE SET NULL,
    document_id TEXT,
    recipient_email TEXT NOT NULL,
    recipient_name TEXT NOT NULL,
    document_type TEXT NOT NULL,
    document_number TEXT,
    days_remaining INTEGER NOT NULL,
    email_subject TEXT,
    email_status TEXT DEFAULT 'Sent',
    status TEXT DEFAULT 'Sent',
    smtp_response TEXT,
    retry_count INTEGER DEFAULT 0,
    channel TEXT DEFAULT 'email',
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    delivery_status TEXT DEFAULT 'Success',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 10. NOTIFICATION QUEUE TABLE (Decoupled Queue & Retry System)
CREATE TABLE IF NOT EXISTS notification_queue (
    id TEXT PRIMARY KEY,
    store_id TEXT REFERENCES medical_stores(id) ON DELETE CASCADE,
    pharmacist_id TEXT REFERENCES pharmacists(id) ON DELETE SET NULL,
    document_id TEXT,
    recipient_email TEXT NOT NULL,
    recipient_name TEXT NOT NULL,
    document_type TEXT NOT NULL,
    document_number TEXT,
    days_remaining INTEGER NOT NULL,
    email_subject TEXT NOT NULL,
    email_body_html TEXT,
    channel TEXT DEFAULT 'email',
    status TEXT DEFAULT 'Pending',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    smtp_response TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP WITH TIME ZONE
);

-- 11. STORE ACCOUNTS TABLE (Firm Self-Service Portal)
CREATE TABLE IF NOT EXISTS store_accounts (
    firm_id TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    store_id TEXT REFERENCES medical_stores(id) ON DELETE CASCADE,
    owner_name TEXT NOT NULL,
    store_name TEXT NOT NULL,
    email TEXT NOT NULL,
    mobile TEXT NOT NULL,
    status TEXT DEFAULT 'Active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- INDEXES FOR OPTIMIZED QUERY PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_stores_shop_code ON medical_stores(shop_code);
CREATE INDEX IF NOT EXISTS idx_stores_dl_expiry ON medical_stores(dl_expiry_date);
CREATE INDEX IF NOT EXISTS idx_stores_fssai_expiry ON medical_stores(fssai_expiry_date);
CREATE INDEX IF NOT EXISTS idx_pharmacists_store_id ON pharmacists(store_id);
CREATE INDEX IF NOT EXISTS idx_pharmacists_mspc ON pharmacists(mspc_number);
CREATE INDEX IF NOT EXISTS idx_pharmacists_ppp ON pharmacists(ppp_number);
CREATE INDEX IF NOT EXISTS idx_documents_store_id ON documents(store_id);
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
CREATE INDEX IF NOT EXISTS idx_notifications_store_id ON notifications(store_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_created_at ON activity_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notif_logs_store ON notification_logs(store_id);
CREATE INDEX IF NOT EXISTS idx_notif_logs_dup ON notification_logs(store_id, document_type, days_remaining);
CREATE INDEX IF NOT EXISTS idx_notif_queue_status ON notification_queue(status);
CREATE INDEX IF NOT EXISTS idx_notif_queue_retry ON notification_queue(status, next_retry_at);
CREATE INDEX IF NOT EXISTS idx_store_accounts_store_id ON store_accounts(store_id);

-- ============================================================================
-- GRANT TABLE PERMISSIONS & DISABLE RLS FOR BACKEND ACCESS
-- ============================================================================
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;

ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE medical_stores DISABLE ROW LEVEL SECURITY;
ALTER TABLE pharmacists DISABLE ROW LEVEL SECURITY;
ALTER TABLE documents DISABLE ROW LEVEL SECURITY;
ALTER TABLE renewals DISABLE ROW LEVEL SECURITY;
ALTER TABLE notifications DISABLE ROW LEVEL SECURITY;
ALTER TABLE activity_logs DISABLE ROW LEVEL SECURITY;
ALTER TABLE settings DISABLE ROW LEVEL SECURITY;
ALTER TABLE notification_logs DISABLE ROW LEVEL SECURITY;
ALTER TABLE notification_queue DISABLE ROW LEVEL SECURITY;
ALTER TABLE store_accounts DISABLE ROW LEVEL SECURITY;

