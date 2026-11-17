import base64,unittest
import test_v8 as fixtures
from org_store import DomainError

class MessageAttachmentPurge(unittest.TestCase):
    setUp=fixtures.WorkspaceTests.setUp
    tearDown=fixtures.WorkspaceTests.tearDown
    make=fixtures.WorkspaceTests.make
    def test_attachment_can_be_restored_and_permanently_deleted(self):
        message=self.s.chat_send(self.staff,self.scope,self.room,text='پیوست آزمایشی',attachments=[{'name':'sample.txt','data':base64.b64encode(b'private example').decode()}])
        file_id=self.s.chat_list(self.staff,self.scope,self.room)['items'][-1]['files'][0]['id'];file=self.s.files/(file_id+'.bin');self.assertTrue(file.exists())
        self.s.chat_action(self.staff,message['id'],'delete')
        with self.assertRaises(DomainError):self.s.workspace_trash(self.other,'message',message['id'],1,purge=True)
        self.assertTrue(file.exists());self.s.workspace_trash(self.staff,'message',message['id'],1,restore=True);self.assertTrue(file.exists())
        self.s.chat_action(self.staff,message['id'],'delete');self.s.workspace_trash(self.staff,'message',message['id'],1,purge=True)
        self.assertFalse(file.exists());self.assertFalse(list(self.s.files.glob(file_id+'.purging-*')))
        self.assertFalse(any(x['id']==message['id'] for x in self.s.workspace_trash(self.staff)))

if __name__=='__main__':unittest.main()
