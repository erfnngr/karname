import os,sys,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen');sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QWidget
from permission_policy import MODULE_REGISTRY,allowed,any_allowed,baseline_allowed,validate_overrides,schema
from access_ui import PermissionDialog

def account(id='employee',role='employee',permissions=None,company='mana',global_role='employee'):
    return dict(id=id,username=id,fullname=id,global_role=global_role,memberships=[dict(company_id=company,role=role,permissions=permissions or {})])

class PermissionPolicyTests(unittest.TestCase):
    def test_employee_attendance_is_readonly_by_default(self):
        actor=account();self.assertTrue(allowed(actor,'mana','attendance','view'))
        for action in ('create','edit','import','approve','manage_schedule'):self.assertFalse(allowed(actor,'mana','attendance',action))
    def test_unknown_capabilities_are_denied_even_for_global_admin(self):
        admin=account(global_role='group_admin');self.assertFalse(allowed(admin,'mana','new_future_feature','view'));self.assertFalse(allowed(admin,'mana','chat','unknown'));self.assertTrue(allowed(admin,'mana','chat','send'))
    def test_restriction_is_company_scoped_and_view_is_prerequisite(self):
        actor=account(permissions={'module.chat.view':False,'module.chat.send':True});actor['memberships'].append(dict(company_id='arka',role='employee',permissions={}));self.assertFalse(allowed(actor,'mana','chat','view'));self.assertFalse(allowed(actor,'mana','chat','send'));self.assertTrue(allowed(actor,'arka','chat','send'));self.assertTrue(any_allowed(actor,'chat','send'))
    def test_invalid_module_or_non_boolean_override_rejected(self):
        for value in ({'module.chat.send':'true'},{'module.unknown.view':True},{'module.chat.nope':True},{'module.bad':False}):
            with self.assertRaises(ValueError):validate_overrides(value)
        self.assertEqual(validate_overrides({'work.view':True,'module.chat.send':False}),{'work.view':True,'module.chat.send':False})
    def test_registry_exposes_all_roles_and_operations(self):
        result={m['key']:m for m in schema()};self.assertEqual(set(result),set(MODULE_REGISTRY));self.assertIn('employee',result['attendance']['defaults']);self.assertIn('view',{a['key'] for a in result['chat']['actions']})

class PermissionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.panel=QWidget();self.panel.actor=account('manager','company_manager');self.panel.companies=[dict(id='mana',name='مانا'),dict(id='arka',name='آرکا')];self.person=account(permissions={'work.view':True});self.person['memberships'].append(dict(company_id='arka',role='employee',permissions={}));self.dialog=PermissionDialog(self.panel,self.person)
    def tearDown(self):self.dialog.close();self.panel.close()
    def test_manager_only_sees_companies_they_manage(self):self.assertEqual([co['id'] for co,_ in self.dialog.scopes],['mana'])
    def test_visibility_disables_child_operations_and_serializes_override(self):
        items=self.dialog.items['chat'];items['view'].setCheckState(1,Qt.Unchecked);self.assertTrue(items['send'].isDisabled());self.dialog.validate();self.assertEqual(self.dialog.result_payload['company'],'mana');self.assertEqual(self.dialog.result_payload['permissions']['module.chat.view'],False);self.assertTrue(self.dialog.result_payload['permissions']['work.view'])
    def test_role_defaults_restored_without_deleting_legacy_permissions(self):
        self.dialog.items['attendance']['create'].setCheckState(1,Qt.Checked);self.dialog.defaults();self.dialog.validate();self.assertNotIn('module.attendance.create',self.dialog.result_payload['permissions']);self.assertTrue(self.dialog.result_payload['permissions']['work.view'])

if __name__=='__main__':unittest.main()
