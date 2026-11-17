import unittest
from unittest.mock import patch
from types import SimpleNamespace
from react_chat_delivery import ReactDelivery

class DeliveryTests(unittest.TestCase):
    @patch('chat_delivery.save')
    @patch('chat_delivery.load',return_value={'drafts':{},'outbox':[]})
    def test_send_and_draft_removal_commit_together(self,load,save):
        delivery=ReactDelivery('unused','http://127.0.0.1','u',lambda:None)
        delivery.save_draft('c','r','draft',[],None)
        body={'company':'c','room':'r','text':'draft','request_id':'1234567890123456'}
        save.reset_mock()
        with patch('chat_delivery.save',side_effect=OSError('disk')):
            with self.assertRaises(OSError):delivery.enqueue_and_clear_draft(body)
        self.assertEqual(delivery.draft('c','r')['text'],'draft')
        self.assertIsNone(delivery.queue.pending())
        self.assertEqual(delivery.enqueue_and_clear_draft(body),body['request_id'])
        self.assertEqual(save.call_count,1)
        self.assertFalse(delivery.draft('c','r').get('text'))
        self.assertEqual(delivery.queue.pending()['payload'],body)
        self.assertEqual(delivery.enqueue_and_clear_draft(body),body['request_id'])
        self.assertEqual(len(delivery.queue.value['outbox']),1)
    @patch('chat_delivery.save')
    @patch('chat_delivery.load',return_value={'drafts':{},'outbox':[]})
    def test_network_failure_keeps_same_request_until_acknowledged(self,load,save):
        client=SimpleNamespace(url='http://127.0.0.1',token='token',user={'id':'u'},fingerprint=None,session=SimpleNamespace(verify=True))
        delivery=ReactDelivery('unused','http://127.0.0.1','u',lambda:client)
        body={'company':'c','room':'r','text':'test','request_id':'1234567890123456'};key=delivery.enqueue(body);self.assertEqual(delivery.enqueue(body),key);self.assertEqual(len(delivery.queue.value['outbox']),1)
        class Worker:
            def __init__(self,*args):self.session=SimpleNamespace(close=lambda:None)
            def request(self,path,payload):raise OSError('offline')
        with patch('org_client.Client',Worker):self.assertEqual(delivery.flush_one()['status'],'offline')
        self.assertEqual(delivery.queue.pending()['payload']['request_id'],key)
        class Success(Worker):
            def request(self,path,payload):return {'id':'m'}
        with patch('org_client.Client',Success):self.assertEqual(delivery.flush_one()['status'],'sent')
        self.assertIsNone(delivery.queue.pending())
    @patch('chat_delivery.save')
    @patch('chat_delivery.load',return_value={'drafts':{},'outbox':[]})
    def test_account_change_never_flushes_another_users_queue(self,load,save):
        client=SimpleNamespace(url='http://127.0.0.1',token='token',user={'id':'other'},fingerprint=None,session=SimpleNamespace(verify=True))
        delivery=ReactDelivery('unused','http://127.0.0.1','u',lambda:client);delivery.enqueue({'company':'c','room':'r','text':'test'})
        self.assertEqual(delivery.flush_one()['status'],'offline');self.assertIsNotNone(delivery.queue.pending())
    @patch('chat_delivery.load',return_value={'drafts':{},'outbox':[]})
    def test_failed_persistence_does_not_fake_queued_message(self,load):
        delivery=ReactDelivery('unused','http://127.0.0.1','u',lambda:None);body={'company':'c','room':'r','text':'test','request_id':'1234567890123456'}
        with patch('chat_delivery.save',side_effect=OSError('disk')):
            with self.assertRaises(OSError):delivery.enqueue(body)
        self.assertIsNone(delivery.queue.pending())
        with patch('chat_delivery.save'):self.assertEqual(delivery.enqueue(body),body['request_id'])
