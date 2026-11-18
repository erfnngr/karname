import React from 'react';
import {HomeState} from './home-bridge';

export function HomeMiniCalendar({state,act}:{state:HomeState;act:(action:string,args?:Record<string,unknown>)=>unknown}) {
  const calendar=state.mini_calendar;
  if(!state.permissions.calendar||!calendar)return null;
  return <section aria-label="تقویم ماه جاری" className="rounded-2xl border border-[var(--color-border)] bg-[var(--glass-bg-strong)] px-3 py-2.5 min-w-0 text-[var(--color-foreground)]">
    <header className="flex items-center justify-between gap-2 mb-2"><strong className="text-xs font-extrabold">{calendar.title}</strong><button type="button" className="rounded-lg px-2 py-1 text-[11px] font-semibold text-[var(--color-primary)] hover:bg-[var(--color-accent)]" onClick={()=>act('open_module',{key:'calendar'})}>تقویم کامل</button></header>
    <div className="grid grid-cols-7 text-center text-[10px] font-bold text-[var(--color-muted-foreground)] border-b border-[var(--color-border)] pb-1 mb-1">{['ش','ی','د','س','چ','پ','ج'].map((day,i)=><span key={i}>{day}</span>)}</div>
    <div className="grid grid-cols-7 text-center gap-y-0.5">{Array.from({length:calendar.offset},(_,i)=><span key={'empty'+i}/>)}{calendar.days.map(day=><button type="button" key={day.date} onClick={()=>act('open_calendar_day',{date:day.date})} aria-label={`${day.date}${day.has_events?'، دارای رویداد':''}`} aria-current={day.today?'date':undefined} className={`relative mx-auto w-7 h-6 rounded-md text-[11px] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-primary)] ${day.today?'bg-[var(--color-primary)] text-[var(--color-primary-foreground)]':day.holiday?'text-rose-600 dark:text-rose-300 hover:bg-[var(--color-accent)]':'text-[var(--color-foreground)] hover:bg-[var(--color-accent)]'}`}>{day.label}{day.has_events&&<span className={`absolute bottom-0 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full ${day.today?'bg-current':'bg-[var(--color-primary)]'}`}/>}</button>)}</div>
  </section>;
}
