import unittest
from unittest.mock import patch
from avalai_client import avalai_url,credential_path,save_credentials,AvalAIClient
from lmstudio_client import LMError

class AvalAITests(unittest.TestCase):
    def test_only_official_https_endpoint_accepts_secrets(self):
        self.assertEqual(avalai_url('https://api.avalai.ir/user/v1/'),'https://api.avalai.ir/user/v1')
        for url in ['http://api.avalai.ir/v1','https://api.avalai.ir.evil.test/v1','https://api.avalai.ir/v1?x=1','https://user:pass@api.avalai.ir/v1']:
            with self.assertRaises(LMError):avalai_url(url)
    def test_credentials_separated_per_user_and_not_in_plain_settings(self):
        self.assertNotEqual(credential_path('user-1'),credential_path('user-2'))
        with patch('local_vault.save') as save:
            save_credentials('user-1','example-key','model-id');self.assertEqual(save.call_args.args[1]['model'],'model-id')
        with self.assertRaises(LMError):credential_path('standalone')
    def test_cloud_client_uses_official_endpoint(self):
        client=AvalAIClient(token='example-key');self.assertEqual(client.url,'https://api.avalai.ir/v1');client.close()
    def test_model_beyond_first_200_is_available(self):
        from unittest.mock import MagicMock
        response=MagicMock();response.content=b'{}';response.json.return_value={'data':[{'id':'model-'+str(i)} for i in range(350)]}
        response.__enter__.return_value=response
        client=AvalAIClient(token='example-key')
        with patch.object(client,'request',return_value=response):self.assertIn('model-349',client.models())
        client.close()

if __name__=='__main__':unittest.main()
