'use strict';
// Drafts and the outbox contain no session token. Encryption is bound to this browser profile.
window.KarnameDelivery=(()=>{
 let db,key,person,state={drafts:{},outbox:[]},chain=Promise.resolve();
 const request=r=>new Promise((resolve,reject)=>{r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});
 const locked=fn=>navigator.locks?navigator.locks.request('karname-drafts-v8:'+person,fn):fn();
 function write(store,id,value){return new Promise((resolve,reject)=>{const tx=db.transaction(store,'readwrite');tx.objectStore(store).put(value,id);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error)})}
 async function read(){const saved=await request(db.transaction('data').objectStore('data').get(person));return saved?JSON.parse(new TextDecoder().decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:saved.iv},key,saved.data))):{drafts:{},outbox:[]}}
 async function init(id){
  person=id;indexedDB.deleteDatabase('karname-private-drafts-v8');indexedDB.deleteDatabase('karname-private-drafts-v9-empty-chat');db=await new Promise((resolve,reject)=>{const r=indexedDB.open('karname-private-drafts-v9-saved-chat',1);r.onupgradeneeded=()=>{r.result.createObjectStore('keys');r.result.createObjectStore('data')};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});
  return locked(async()=>{key=await request(db.transaction('keys').objectStore('keys').get(id));if(!key){key=await crypto.subtle.generateKey({name:'AES-GCM',length:256},false,['encrypt','decrypt']);await write('keys',id,key)}state=await read();return state});
 }
 // Serialize mutations across tabs and reload the current state before changing it.
 function update(change){chain=chain.catch(()=>{}).then(()=>locked(async()=>{const latest=await read();const result=change(latest);const iv=crypto.getRandomValues(new Uint8Array(12));const data=await crypto.subtle.encrypt({name:'AES-GCM',iv},key,new TextEncoder().encode(JSON.stringify(latest)));await write('data',person,{iv,data});state=latest;return result}));return chain}
 const room=s=>s.company+':'+s.room;
 return {
  init,draft:s=>structuredClone(state.drafts[room(s)]||{}),
  async setDraft(s,value){const name=room(s),draft=structuredClone(value);return update(v=>{if(draft.text||draft.files?.length)v.drafts[name]=draft;else delete v.drafts[name]})},
  async enqueue(payload){payload=structuredClone(payload);payload.request_id=payload.request_id||crypto.randomUUID();return update(v=>{if(v.outbox.length>=30)throw Error('صف ارسال پر است.');v.outbox.push({payload,status:'queued',error:''});return payload.request_id})},
  pending:()=>state.outbox.find(x=>x.status==='queued'),items:()=>structuredClone(state.outbox),
  async ack(id){return update(v=>{v.outbox=v.outbox.filter(x=>x.payload.request_id!==id)})},
  async fail(id,error,permanent){return update(v=>{const x=v.outbox.find(x=>x.payload.request_id===id);if(x){x.error=error;x.status=permanent?'needs_review':'queued'}})},
  async retry(id){return update(v=>{const x=v.outbox.find(x=>x.payload.request_id===id);if(x){x.status='queued';x.error=''}})}
 };
})();
