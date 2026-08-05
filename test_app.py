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

if __name__ == '__main__':
    unittest.main()
