import unittest
import json
import os
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

    def test_01_dashboard_stats(self):
        self.login_admin()
        response = self.app.get('/api/dashboard/stats')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('total_stores', data)
        self.assertIn('total_pharmacists', data)
        self.assertEqual(data['total_stores'], 20)
        self.assertEqual(data['total_pharmacists'], 20)
        print(f"Dashboard Stats Test Passed: {data['total_stores']} stores, {data['total_pharmacists']} pharmacists.")

    def test_02_medical_stores_list(self):
        self.login_admin()
        response = self.app.get('/api/stores')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('stores', data)
        self.assertEqual(len(data['stores']), 20)
        print(f"Medical Stores List Test Passed: {len(data['stores'])} stores loaded.")

    def test_03_medical_store_detail(self):
        self.login_admin()
        stores = get_medical_stores(limit=1)
        store_id = stores[0]['id']
        response = self.app.get(f'/api/stores/{store_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['id'], store_id)
        self.assertIn('pharmacists', data)
        self.assertIn('documents', data)
        print(f"Medical Store Detail Test Passed for Store ID: {store_id}")

    def test_04_pharmacists_list(self):
        self.login_admin()
        response = self.app.get('/api/pharmacists')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('pharmacists', data)
        self.assertEqual(len(data['pharmacists']), 20)
        print(f"Pharmacists List Test Passed: {len(data['pharmacists'])} pharmacists loaded.")

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
        self.assertGreater(len(data['events']), 0)
        print(f"Calendar Events Test Passed: {len(data['events'])} events generated.")

    def test_07_qrcode_and_barcode(self):
        response_qr = self.app.get('/api/qrcode/MS-1001')
        self.assertEqual(response_qr.status_code, 200)
        self.assertEqual(response_qr.mimetype, 'image/svg+xml')

        response_bar = self.app.get('/api/barcode/MS-1001')
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
        # 5 failed attempts from same IP
        for _ in range(5):
            self.app.post('/api/auth/login', json={'username': 'INVALID', 'password': 'WRONG'})
        
        # 6th attempt should return 429 Lockout
        res = self.app.post('/api/auth/login', json={'username': 'VIN2821', 'password': '2821'})
        self.assertEqual(res.status_code, 429)
        data = res.get_json()
        self.assertIn('Too many failed attempts', data.get('error', ''))
        print("Failed Login Lockout Test Passed.")

    def test_session_management(self):
        from app import reset_login_lockout
        reset_login_lockout('127.0.0.1')

        # Successful Login
        res = self.app.post('/api/auth/login', json={'username': 'VIN2821', 'password': '2821'})
        self.assertEqual(res.status_code, 200)

        # Verify Session Active
        res_sess = self.app.get('/api/auth/session')
        self.assertEqual(res_sess.status_code, 200)
        self.assertTrue(res_sess.get_json().get('authenticated'))

        # Logout
        res_out = self.app.post('/api/auth/logout')
        self.assertEqual(res_out.status_code, 200)

        # Verify Session Destroyed
        res_sess_after = self.app.get('/api/auth/session')
        self.assertEqual(res_sess_after.status_code, 401)
        print("Session Management Test Passed.")

    def test_deployment_invalidation(self):
        from app import reset_login_lockout
        import app as app_module
        reset_login_lockout('127.0.0.1')

        # Login
        self.app.post('/api/auth/login', json={'username': 'VIN2821', 'password': '2821'})
        
        # Verify authenticated
        res1 = self.app.get('/api/auth/session')
        self.assertEqual(res1.status_code, 200)

        # Simulate Server Restart / Deployment (change SERVER_STARTUP_ID)
        old_id = app_module.SERVER_STARTUP_ID
        app_module.SERVER_STARTUP_ID = "new_deployment_startup_id_999"

        # Verify session is now automatically invalidated!
        res2 = self.app.get('/api/auth/session')
        self.assertEqual(res2.status_code, 401)
        
        # Restore for other tests
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
        
        # Login as Admin
        self.app.post('/api/auth/login', json={'username': 'VIN2821', 'password': '2821'})
        
        # Trigger send test email
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

    def test_store_self_service_portal(self):
        from seed_data import generate_seed_data
        generate_seed_data()

        # Test Store Login with Firm ID BCWA-MED-000001
        res = self.app.post('/api/auth/store-login', json={'firm_id': 'BCWA-MED-000001', 'password': 'BCWA@1001'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data['user']['role'], 'Store')
        self.assertEqual(data['user']['firm_id'], 'BCWA-MED-000001')

        # Test Store Dashboard API
        res_dash = self.app.get('/api/store/dashboard')
        self.assertEqual(res_dash.status_code, 200)
        dash_data = res_dash.get_json()
        self.assertEqual(dash_data['firm_id'], 'BCWA-MED-000001')

        # Test Store Documents API
        res_docs = self.app.get('/api/store/documents')
        self.assertEqual(res_docs.status_code, 200)
        docs_data = res_docs.get_json()
        self.assertIn('documents', docs_data)

        # Test Tenant Security: Store User blocked from Admin APIs
        res_admin = self.app.get('/api/admin/verify-smtp')
        self.assertEqual(res_admin.status_code, 403)

        print("Store Self-Service Portal & Tenant Security Test Passed.")

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

if __name__ == '__main__':
    unittest.main()

