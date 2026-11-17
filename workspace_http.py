"""HTTP handlers shared by the native client and browser workspace."""
import time
from org_store import DomainError

def dispatch(store,actor,path,method,p,q):
    post=method=='POST'
    if path=='/api/workspace/saved-chat' and post:return store.workspace_saved_chat(actor)
    if path=='/api/workspace/direct':return store.workspace_direct(actor,**p) if post else store.workspace_direct(actor,q['company'])
    if path=='/api/workspace/group-people' and method=='GET':return store.workspace_group_people(actor,q['company'])
    if path=='/api/workspace/group' and post:return store.workspace_group_create(actor,**p)
    if path=='/api/workspace/chat-hide' and post:return store.workspace_hide_room(actor,**p)
    if path=='/api/workspace/chat-restore-group' and post:return store.workspace_restore_group(actor,**p)
    if path=='/api/workspace/chat-clear' and post:return store.workspace_clear_chat(actor,**p)
    if path=='/api/workspace/records-delta' and post:return store.workspace_records_delta(actor,**p)
    if path=='/api/workspace/today':return store.workspace_today(actor)
    if path=='/api/workspace/views':return store.workspace_views(actor,**p) if post else store.workspace_views(actor)
    if path=='/api/workspace/save' and post:return store.workspace_save(actor,**p)
    if path=='/api/workspace/search':return store.workspace_search(actor,q.get('q',''),q.get('limit',50))
    if path=='/api/workspace/requests':return store.workspace_request_save(actor,**p) if post else store.workspace_requests(actor,q.get('company'))
    if path=='/api/workspace/review' and post:return store.workspace_request_review(actor,**p)
    if path=='/api/workspace/policy':return store.workspace_policy(actor,**p) if post else store.workspace_policy(actor,q['company'],q['key'])
    if path=='/api/workspace/balance':return store.workspace_leave_balance(actor,q['company'],q['year'],q.get('user'))
    if path=='/api/workspace/workload':return store.workspace_workload(actor,q['company'],q['month'])
    if path=='/api/workspace/attendance':return store.workspace_attendance_issues(actor,q['company'],q['month'])
    if path=='/api/workspace/attendance-people':return store.attendance_people(actor,q['company'])
    if path=='/api/workspace/attendance-report':return store.attendance_report(actor,q['company'],q['month'],q['employee_code'])
    if path=='/api/workspace/trash':return store.workspace_trash(actor,**p) if post else store.workspace_trash(actor)
    if path=='/api/workspace/notifications':return store.workspace_notifications(actor,**p) if post else store.workspace_notifications(actor)
    if path=='/api/workspace/target':return store.workspace_target(actor,q['id'])
    if path=='/api/workspace/message-task' and post:return store.workspace_task_from_message(actor,**p)
    if path=='/api/workspace/changes':
        after=max(0,int(q.get('after',0)));wait=max(0,min(float(q.get('wait',12)),15));deadline=time.monotonic()+wait
        while store.revision()<=after and time.monotonic()<deadline and not (q.get('_closing') and q['_closing'].is_set()):time.sleep(.25)
        return dict(revision=store.revision())
    raise DomainError('مسیر فضای کار پیدا نشد.',404)
