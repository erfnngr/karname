import unittest
from unittest.mock import patch
from org_client import Client
from org_store import DomainError

class Response:
    ok=False;status_code=404
    def json(self):return {'error':'مسیر پیدا نشد.'}

class OldHostTest(unittest.TestCase):
    def test_missing_inventory_route_explains_host_update(self):
        client=Client('http://127.0.0.1:12345')
        try:
            with patch.object(client.session,'request',return_value=Response()):
                with self.assertRaises(DomainError) as e:client.request('inventory',company='mana')
            self.assertIn('میزبان',str(e.exception));self.assertEqual(e.exception.status,404)
        finally:client.session.close()
