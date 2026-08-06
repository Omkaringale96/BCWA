import unittest
import json
import os
os.environ['TESTING'] = 'true'
from app import app
from database import get_db_connection, get_dashboard_stats, get_medical_stores, get_pharmacists

class BCWAPortalTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        from app import reset_login_lockout
        reset_login_lockout('127.0.0.1')

    def login_admin(self):
        return self.app.post('/api/auth/login', json={'username': 'VIN2821', 'password': '2821'})

    def test_00_unauthorized_access_blocked(self):
        """Verify that protected API endpoints return 401 when accessed without logging in."""
        res1 = self.app.get('/api/dashboard/stats')
        self.assertEqual(res1.status_code, 401)
        res2 = self.app.get('/api/stores')
        self.assertEqual(res2.status_code, 401)
        res3 = self.app.get('/api/pharmacists')
        self.assertEqual(res3.status_code, 401)
        res4 = self.app.get('/api/calendar/events')
        self.assertEqual(res4.status_code, 401)
        print("Unauthorized Access Guard Test Passed: Unauthenticated requests correctly return 401.")

    def test_01_production_zero_state_dashboard(self):
        from seed_data import clear_production_database
        clear_production_database()
        self.login_admin()
        response = self.app.get('/api/dashboard/stats')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('total_stores', data)
        self.assertIn('total_pharmacists', data)
        self.assertEqual(data['total_stores'], 0)
        self.assertEqual(data['total_pharmacists'], 0)
        self.assertEqual(data['upcoming_renewals'], 0)
        self.assertEqual(data['compliance_score'], 0.0)
        print("Production Zero State Dashboard Test Passed: 0 stores, 0 pharmacists, 0 renewals, 0.0% compliance.")

    def test_02_medical_stores_empty_list(self):
        from seed_data import clear_production_database
        clear_production_database()
        self.login_admin()
        response = self.app.get('/api/stores')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('stores', data)
        self.assertEqual(len(data['stores']), 0)
        print("Medical Stores Empty Production List Test Passed.")

    def test_03_store_and_pharmacist_registration_workflow(self):
        from seed_data import clear_production_database
        clear_production_database()

        with self.app as c:
            # 0. Login as Admin
            c.post('/api/auth/login', json={'username': 'VIN2821', 'password': '2821'})

            # 1. Register a new Medical Store
            store_payload = {
                'id': 'MS-1001',
                'firm_id': 'BCWA-MED-000001',
                'store_name': 'Boisar Apex Pharmacy',
                'owner_name': 'Vinayak Patil',
                'owner_mobile': '8766759824',
                'owner_email': 'bhosalevinayakwe@gmail.com',
                'address_line1': 'Shop No. 1, Ostwal Empire',
                'area': 'Boisar',
                'city': 'Palghar',
                'state': 'Maharashtra',
                'pincode': '401501',
                'dl_20b_number': 'MH-TZ4-123456',
                'dl_21b_number': 'MH-TZ4-654321',
                'dl_expiry_date': '2028-12-31',
                'fssai_number': '21524100000000',
                'fssai_expiry_date': '2028-12-31'
            }
            res_store = c.post('/api/stores', json=store_payload)
            self.assertEqual(res_store.status_code, 200)

            # 2. Register a Pharmacist for this store
            ph_payload = {
                'store_id': 'MS-1001',
                'full_name': 'Rahul Sharma',
                'mspc_number': 'MSPC-999888',
                'reg_expiry': '2029-12-31',
                'ppp_number': 'PPP-MH-112233',
                'ppp_expiry': '2028-12-31',
                'qualification': 'B.Pharm',
                'joining_date': '2025-01-01',
                'mobile': '8766759824',
                'email': 'bhosalevinayakwe@gmail.com'
            }
            res_ph = c.post('/api/pharmacists', json=ph_payload)
            self.assertEqual(res_ph.status_code, 200)

            # 3. Create Store Login Credentials
            from database import create_or_update_store_account
            create_or_update_store_account(
                firm_id='BCWA-MED-000001',
                password='BCWA@1001',
                store_id='MS-1001',
                owner_name='Vinayak Patil',
                store_name='Boisar Apex Pharmacy',
                email='bhosalevinayakwe@gmail.com',
                mobile='8766759824'
            )

            # 4. Test Store Portal Login & Tenant Dashboard Access
            res_login = c.post('/api/auth/store-login', json={'firm_id': 'BCWA-MED-000001', 'password': 'BCWA@1001'})
            self.assertEqual(res_login.status_code, 200)

            res_dash = c.get('/api/store/dashboard')
            self.assertEqual(res_dash.status_code, 200)
            dash_data = res_dash.get_json()
            self.assertEqual(dash_data['firm_id'], 'BCWA-MED-000001')
        print("Store & Pharmacist Registration Workflow Test Passed.")

    def test_04_pharmacists_empty_list(self):
        from seed_data import clear_production_database
        clear_production_database()
        self.login_admin()
        response = self.app.get('/api/pharmacists')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('pharmacists', data)
        self.assertEqual(len(data['pharmacists']), 0)
        print("Pharmacists Empty Production List Test Passed.")

    def test_05_ocr_extraction(self):
        self.login_admin()
        response = self.app.post('/api/ocr/extract', data={'doc_type': 'Drug License'})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('dl_20b_number', data['data'])
        print(f"OCR Extraction Test Passed: Extracted 20B License {data['data']['dl_20b_number']}")

    def test_06_calendar_events(self):
        self.login_admin()
        response = self.app.get('/api/calendar/events')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('events', data)
        print(f"Calendar Events API Test Passed: {len(data['events'])} events.")

    def test_07_qrcode_and_barcode(self):
        response_qr = self.app.get('/api/qrcode/BCWA-MED-000001')
        self.assertEqual(response_qr.status_code, 200)
        self.assertEqual(response_qr.mimetype, 'image/svg+xml')

        response_bar = self.app.get('/api/barcode/BCWA-MED-000001')
        self.assertEqual(response_bar.status_code, 200)
        self.assertEqual(response_bar.mimetype, 'image/svg+xml')
        print("QR Code & Barcode SVG Generator Test Passed.")

    def test_security_headers(self):
        res = self.app.get('/')
        self.assertEqual(res.headers.get('X-Frame-Options'), 'DENY')
        self.assertEqual(res.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertIn('no-store', res.headers.get('Cache-Control', ''))
        print("Security Headers Test Passed.")

    def test_failed_login_lockout(self):
        from app import reset_login_lockout
        reset_login_lockout('127.0.0.1')
        for _ in range(5):
            self.app.post('/api/auth/login', json={'username': 'INVALID', 'password': 'WRONG'})
        
        res = self.app.post('/api/auth/login', json={'username': 'VIN2821', 'password': '2821'})
        self.assertEqual(res.status_code, 429)
        data = res.get_json()
        self.assertIn('Too many failed attempts', data.get('error', ''))
        print("Failed Login Lockout Test Passed.")

    def test_session_management(self):
        from app import reset_login_lockout
        reset_login_lockout('127.0.0.1')

        res = self.app.post('/api/auth/login', json={'username': 'VIN2821', 'password': '2821'})
        self.assertEqual(res.status_code, 200)

        res_sess = self.app.get('/api/auth/session')
        self.assertEqual(res_sess.status_code, 200)
        self.assertTrue(res_sess.get_json().get('authenticated'))

        res_out = self.app.post('/api/auth/logout')
        self.assertEqual(res_out.status_code, 200)

        res_sess_after = self.app.get('/api/auth/session')
        self.assertEqual(res_sess_after.status_code, 401)
        print("Session Management Test Passed.")

    def test_deployment_invalidation(self):
        from app import reset_login_lockout
        import app as app_module
        reset_login_lockout('127.0.0.1')

        self.app.post('/api/auth/login', json={'username': 'VIN2821', 'password': '2821'})
        res1 = self.app.get('/api/auth/session')
        self.assertEqual(res1.status_code, 200)

        old_id = app_module.SERVER_STARTUP_ID
        app_module.SERVER_STARTUP_ID = "new_deployment_startup_id_999"

        res2 = self.app.get('/api/auth/session')
        self.assertEqual(res2.status_code, 401)
        
        app_module.SERVER_STARTUP_ID = old_id
        print("Deployment Invalidation Test Passed.")

    def test_renewal_notification_engine(self):
        from notification_engine import run_reminder_engine
        summary = run_reminder_engine()
        self.assertIn('queued', summary)
        self.assertIn('sent', summary)

        self.login_admin()
        res_logs = self.app.get('/api/notifications/logs')
        self.assertEqual(res_logs.status_code, 200)
        logs_data = res_logs.get_json()
        self.assertIn('logs', logs_data)

        res_q = self.app.get('/api/notifications/queue')
        self.assertEqual(res_q.status_code, 200)
        q_data = res_q.get_json()
        self.assertIn('queue', q_data)

        print("Automated Renewal Notification Engine & Queue Test Passed.")

    def test_send_test_email(self):
        from app import reset_login_lockout
        reset_login_lockout('127.0.0.1')
        
        self.app.post('/api/auth/login', json={'username': 'VIN2821', 'password': '2821'})
        res = self.app.post('/api/admin/send-test-email')
        self.assertIn(res.status_code, [200, 500])
        data = res.get_json()
        self.assertIn('success', data)
        print("Admin Send Test Email Test Passed.")

    def test_email_service_and_queue(self):
        import email_service
        import notification_service
        ok, msg = email_service.send_html_email('test@example.com', 'Test Subject', '<h1>HTML</h1>')
        self.assertTrue(ok)

        ok2, msg2 = notification_service.send({'recipient_email': 'test@example.com', 'email_subject': 'Subject', 'email_body_html': '<p>Body</p>'})
        self.assertTrue(ok2)
        print("Email & Notification Service Multi-Channel Abstraction Test Passed.")

    def test_smart_document_classification(self):
        from database import is_expiry_document
        self.assertTrue(is_expiry_document('Drug License'))
        self.assertTrue(is_expiry_document('Food License (FSSAI)'))
        self.assertTrue(is_expiry_document('PPP Card'))
        self.assertFalse(is_expiry_document('Electricity Bill (Light Bill)'))
        self.assertFalse(is_expiry_document('Namuna 8'))
        self.assertFalse(is_expiry_document('Owner Aadhaar'))
        self.assertFalse(is_expiry_document('Owner PAN'))
        print("Smart Document Classification Test Passed: Expiry vs Permanent categories correctly identified.")

    def test_store_registration_failure_activity_log_guard(self):
        from seed_data import clear_production_database
        from database import get_activity_logs
        clear_production_database()

        with self.app as c:
            c.post('/api/auth/login', json={'username': 'VIN2821', 'password': '2821'})
            # Submit invalid store payload missing store_name
            res = c.post('/api/stores', json={'owner_name': 'Test Owner'})
            self.assertEqual(res.status_code, 400)
            data = res.get_json()
            self.assertFalse(data.get('success'))
            self.assertIn('Medical Store Name is required', data.get('error', ''))

            # Verify NO activity log entry was created for failed store registration
            logs = get_activity_logs()
            reg_logs = [l for l in logs if 'Store Registered' in l.get('action', '')]
            self.assertEqual(len(reg_logs), 0)
            print("Store Registration Failure Activity Log Guard Test Passed: Activity Log NOT created on failure.")

    def test_notification_engine_expired_document_workflow(self):
        from datetime import datetime, timedelta
        from seed_data import clear_production_database
        from app import reset_login_lockout
        reset_login_lockout('127.0.0.1')
        clear_production_database()

        with self.app as c:
            c.post('/api/auth/login', json={'username': 'VIN2821', 'password': '2821'})

            # 1. Register Medical Store with Drug License expiry set to yesterday (-1 day)
            yesterday_str = (datetime.now().date() - timedelta(days=1)).strftime('%Y-%m-%d')
            store_payload = {
                'id': 'MS-EXPIRED-99',
                'firm_id': 'BCWA-MED-000099',
                'store_name': 'Expired License Pharmacy',
                'owner_name': 'Test Owner',
                'owner_mobile': '9876543210',
                'owner_email': 'expiredtest@bcwa.org',
                'dl_20b_number': 'MH-TZ4-999999',
                'dl_21b_number': 'MH-TZ4-999999',
                'dl_expiry_date': yesterday_str,
                'fssai_number': '21524999999999',
                'fssai_expiry_date': '2028-12-31'
            }
            res_reg = c.post('/api/stores', json=store_payload)
            self.assertEqual(res_reg.status_code, 200)

            # 2. Run Notification Engine Scan Now
            res_scan = c.post('/api/notifications/engine/run')
            self.assertEqual(res_scan.status_code, 200)
            scan_data = res_scan.get_json()
            self.assertTrue(scan_data.get('success'))
            self.assertGreaterEqual(scan_data['summary']['queued'] + scan_data['summary']['skipped'], 1)

            # 3. Verify Active System Alert was created
            res_notif = c.get('/api/notifications')
            self.assertEqual(res_notif.status_code, 200)
            notif_list = res_notif.get_json().get('notifications', [])
            self.assertGreaterEqual(len(notif_list), 1)
            expired_alerts = [n for n in notif_list if 'Drug License' in n.get('title', '') or 'Expired' in n.get('title', '')]
            self.assertGreaterEqual(len(expired_alerts), 1)

            # 4. Verify Notification Queue contains Sent item
            res_q = c.get('/api/notifications/queue')
            self.assertEqual(res_q.status_code, 200)
            q_items = res_q.get_json().get('queue', [])
            self.assertGreaterEqual(len(q_items), 1)
            sent_items = [q for q in q_items if q.get('document_type') == 'Drug License']
            self.assertGreaterEqual(len(sent_items), 1)

            # 5. Verify Notification Log created
            res_logs = c.get('/api/notifications/logs')
            self.assertEqual(res_logs.status_code, 200)
            logs = res_logs.get_json().get('logs', [])
            self.assertGreaterEqual(len(logs), 1)
            dl_logs = [l for l in logs if l.get('document_type') == 'Drug License']
            self.assertGreaterEqual(len(dl_logs), 1)

            # 6. Verify Dashboard Notification Counter and Critical Compliance Status
            res_dash = c.get('/api/dashboard/stats')
            self.assertEqual(res_dash.status_code, 200)
            dash = res_dash.get_json()
            self.assertGreaterEqual(dash.get('todays_notifications', 0), 1)
            self.assertEqual(dash.get('compliance_status'), 'Critical')

            print("Notification Engine Expired Document End-to-End Workflow Test Passed: Alert created, Queue processed, Email sent, Log recorded, Notification counter updated, Compliance Critical.")

    def test_document_upload_and_preview_workflow(self):
        import io
        with self.app as c:
            c.post('/api/auth/login', json={'username': 'VIN2821', 'password': '2821'})
            
            # 1. Upload sample PDF document
            data = {
                'store_id': 'MS-1001',
                'category': 'Drug License',
                'title': 'Test Drug License 20B',
                'document_number': 'MH-TZ4-998877',
                'issue_date': '2026-08-01',
                'expiry_date': '2028-12-31',
                'file': (io.BytesIO(b"%PDF-1.4 sample PDF content"), "test_dl_license.pdf")
            }
            res_up = c.post('/api/documents/upload', data=data, content_type='multipart/form-data')
            self.assertEqual(res_up.status_code, 200)
            up_data = res_up.get_json()
            self.assertTrue(up_data.get('success'))
            doc_id = up_data.get('id')

            # 2. Query preview endpoint with redirect=false
            res_prev = c.get(f'/api/documents/{doc_id}/preview?redirect=false')
            self.assertEqual(res_prev.status_code, 200)
            prev_data = res_prev.get_json()
            self.assertTrue(prev_data.get('success'))
            self.assertEqual(prev_data.get('bucket_name'), 'documents')
            self.assertIn('documents', prev_data.get('preview_url', ''))

            # 3. Query preview endpoint with redirect=true (HTTP 302 Redirect or HTTP 200 HTML Viewer)
            res_redir = c.get(f'/api/documents/{doc_id}/preview')
            self.assertIn(res_redir.status_code, [200, 302])
            print("Document Vault Upload & Preview Single Bucket Test Passed (JSON & 302/200 Preview).")

if __name__ == '__main__':
    unittest.main()

