'use strict';
// Presentation reflects the shared server registry. Server checks remain authoritative.
window.KarnamePermissions=(()=>{
 let actor=null,registry={};
 function baseline(role,key,action){const m=registry[key];if(!m||!m.actions.some(a=>a.key===action))return false;if(['group_admin','company_manager','system_admin'].includes(role))return true;return (m.defaults?.[role]||[]).includes(action)}
 function one(company,key,action){if(company==='__shared_chat__')return key==='chat'&&allow(key,action);const m=registry[key];if(!m||!m.actions.some(a=>a.key===action))return false;if(actor?.global_role==='group_admin')return true;const member=(actor?.memberships||[]).find(x=>x.company_id===company);if(!member)return actor?.global_role==='system_admin'&&baseline('system_admin',key,action);const role=member.role,permissions=member.permissions||{};const value=op=>typeof permissions['module.'+key+'.'+op]==='boolean'?permissions['module.'+key+'.'+op]:baseline(role,key,op);return value('view')&&value(action)}
 function allow(key,action='view',company=null){if(!actor)return false;if(company)return one(company,key,action);if(['group_admin','system_admin'].includes(actor.global_role))return baseline(actor.global_role,key,action);return (actor.memberships||[]).some(m=>one(m.company_id,key,action))}
 function apply(root=document,company=null){for(const e of root.querySelectorAll('[data-permission]')){const [key,action='view']=e.dataset.permission.split('.');const scope=(e.tagName==='A'||e.dataset.permissionGlobal==='true')?null:e.dataset.company||company;e.hidden=!allow(key,action,scope)}}
 async function init(user,meta){actor=user;if(!meta){const r=await fetch('/api/schema',{credentials:'same-origin'});if(!r.ok)throw Error('دریافت فهرست دسترسی‌ها انجام نشد.');meta=await r.json()}if(!Array.isArray(meta.permissions))throw Error('مرکز شرکت برای تنظیم دسترسی به نسخه جدید نیاز دارد.');registry=Object.fromEntries(meta.permissions.map(m=>[m.key,m]));apply();return api}
 function update(user,company=null){actor=user;apply(document,company)}
 function denyPage(moduleKey,container){if(allow(moduleKey))return false;document.getElementById('login').hidden=true;document.getElementById(container).hidden=true;const denial=document.getElementById('permissionDenied');if(denial)denial.hidden=false;return true}
 const api={init,update,allow,apply,denyPage,get actor(){return actor}};return api;
})();
