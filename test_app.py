import unittest
import json
import os
from app import app
from database import get_db_connection, get_dashboard_stats, get_medical_stores, get_pharmacists

class BCWAPortalTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_dashboard_stats(self):
        response = self.app.get('/api/dashboard/stats')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('total_stores', data)
        self.assertIn('total_pharmacists', data)
        self.assertEqual(data['total_stores'], 20)
        self.assertGreaterEqual(data['total_pharmacists'], 40)
        print(f"Dashboard Stats Test Passed: {data['total_stores']} stores, {data['total_pharmacists']} pharmacists.")

    def test_02_medical_stores_list(self):
        response = self.app.get('/api/stores')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('stores', data)
        self.assertEqual(len(data['stores']), 20)
        print(f"Medical Stores List Test Passed: {len(data['stores'])} stores loaded.")

    def test_03_medical_store_detail(self):
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
        response = self.app.get('/api/pharmacists')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('pharmacists', data)
        self.assertGreaterEqual(len(data['pharmacists']), 40)
        print(f"Pharmacists List Test Passed: {len(data['pharmacists'])} pharmacists loaded.")

    def test_05_ocr_extraction(self):
        response = self.app.post('/api/ocr/extract', data={'doc_type': 'Drug License'})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('dl_20b_number', data['data'])
        print(f"OCR Extraction Test Passed: Extracted 20B License {data['data']['dl_20b_number']}")

    def test_06_calendar_events(self):
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

if __name__ == '__main__':
    unittest.main()

