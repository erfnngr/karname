import { useEffect, useRef, useState } from 'react';
import { request } from './bridge';

type Room = {company:string;room:string};
type FileData = {name:string;data:string;size:number};
type Reply = {id:string;text:string};
type Draft = {text?:string;files?:FileData[];reply_to?:string|null};
type Snapshot = {company:string;room:string;text:string;files:FileData[];reply_to:string|null};

/** Preserves independent rooms and never overwrites edits made while loading. */
export function useRoomDrafts(room:Room|null, key:string, snapshot:Snapshot|null,
  apply:(key:string,draft:Draft)=>void, report:(message:string)=>void) {
  const loaded=useRef(new Set<string>());const touched=useRef(new Set<string>());
  const timers=useRef(new Map<string,number>());const lastSaved=useRef(new Map<string,string>());
  const counter=useRef(Date.now()*1000);const activeKey=useRef(key);activeKey.current=key;
  const [revision,setRevision]=useState(0);const [failed,setFailed]=useState('');
  const markEdited=(target:string)=>{if(target)touched.current.add(target);};
  useEffect(()=>{
    if(!room||!key||loaded.current.has(key))return;
    let active=true;const target=key;setFailed('');
    request<Draft>('draft_get',{company:room.company,room:room.room}).then(value=>{
      if(!active)return;
      if(!touched.current.has(target)) {apply(target,value);lastSaved.current.set(target,JSON.stringify({company:room.company,room:room.room,text:value.text||'',files:value.files||[],reply_to:value.reply_to||null}));}
      loaded.current.add(target);setRevision(x=>x+1);
    }).catch(e=>{if(active){setFailed(target);report('بازیابی پیش‌نویس انجام نشد: '+String(e));}});
    return()=>{active=false;};
  },[key,room?.company,room?.room,revision]);
  useEffect(()=>{
    if(!snapshot||!key||!loaded.current.has(key))return;
    const target=key;const encoded=JSON.stringify(snapshot);if(lastSaved.current.get(target)===encoded)return;
    const previous=timers.current.get(target);if(previous)window.clearTimeout(previous);
    const version=++counter.current;
    const timer=window.setTimeout(()=>{
      timers.current.delete(target);
      request<{saved:boolean}>('draft_save',{...snapshot,version}).then(result=>{if(result.saved)lastSaved.current.set(target,encoded);}).catch(e=>report('ذخیره پیش‌نویس انجام نشد: '+String(e)));
    },500);
    timers.current.set(target,timer);
  },[key,snapshot?.text,snapshot?.files,snapshot?.reply_to,revision]);
  const retry=()=>{setFailed('');setRevision(x=>x+1);};
  const nextVersion=(target:string)=>{const timer=timers.current.get(target);if(timer)window.clearTimeout(timer);timers.current.delete(target);return ++counter.current;};
  return {markEdited,ready:!room||loaded.current.has(key),failed:failed===key,retry,nextVersion};
}
