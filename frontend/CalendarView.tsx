import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowUpRight,
  Cake,
  Calculator,
  Calendar as CalendarIcon,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Circle,
  Download,
  Edit3,
  FileSpreadsheet,
  Filter,
  List,
  Plus,
  Search,
  Sparkles,
  Tag,
  Trash2,
  X,
} from 'lucide-react';
import { CalendarDayCell, CalendarEventItem, CalendarState, calendarRequest, onCalendarState } from './calendar-bridge';

type ViewMode = 'month' | 'week' | 'day' | 'list';
type EventColor = CalendarEventItem['color'];

const COLOR_MAP: Record<EventColor, { label: string; bg: string; border: string; text: string; dot: string }> = {
  sky: {
    label: 'آبی آسمانی',
    bg: 'bg-sky-100/90 dark:bg-sky-900/65',
    border: 'border-sky-300 dark:border-sky-400/45',
    text: 'text-sky-950 dark:text-sky-100',
    dot: 'bg-sky-500',
  },
  emerald: {
    label: 'سبز نعنایی',
    bg: 'bg-emerald-100/90 dark:bg-emerald-900/65',
    border: 'border-emerald-300 dark:border-emerald-400/45',
    text: 'text-emerald-950 dark:text-emerald-100',
    dot: 'bg-emerald-500',
  },
  amber: {
    label: 'طلایی / بیمه',
    bg: 'bg-amber-100/90 dark:bg-amber-900/60',
    border: 'border-amber-300 dark:border-amber-400/45',
    text: 'text-amber-950 dark:text-amber-100',
    dot: 'bg-amber-500',
  },
  rose: {
    label: 'گلبهی / تولد و تعطیل',
    bg: 'bg-rose-100/90 dark:bg-rose-900/65',
    border: 'border-rose-300 dark:border-rose-400/45',
    text: 'text-rose-950 dark:text-rose-100',
    dot: 'bg-rose-500',
  },
  indigo: {
    label: 'کوبالت شرکتی',
    bg: 'bg-indigo-100/90 dark:bg-indigo-900/65',
    border: 'border-indigo-300 dark:border-indigo-400/45',
    text: 'text-indigo-950 dark:text-indigo-100',
    dot: 'bg-indigo-500',
  },
  teal: {
    label: 'فیروزه‌ای',
    bg: 'bg-teal-100/90 dark:bg-teal-900/65',
    border: 'border-teal-300 dark:border-teal-400/45',
    text: 'text-teal-950 dark:text-teal-100',
    dot: 'bg-teal-500',
  },
};

type CalendarThemeSkin = {
  shell: string;
  panel: string;
  cellRadius: string;
  weekday: string;
  weekdayHoliday: string;
  cellNormal: string;
  cellOut: string;
  cellHoliday: string;
  cellSelected: string;
  cellToday: string;
  todayDot: string;
  occNormal: string;
  occHoliday: string;
};

const CALENDAR_SKINS: Record<string, CalendarThemeSkin> = {
  default: {
    shell: 'bg-[var(--color-background)]',
    panel: 'rounded-2xl border-[var(--color-border)] bg-[var(--color-card)] shadow-sm',
    cellRadius: 'rounded-xl',
    weekday: 'bg-[var(--color-muted)]/75 text-[var(--color-foreground)] border border-[var(--color-border)]/70',
    weekdayHoliday: 'bg-rose-500/12 text-rose-700 dark:text-rose-200 border border-rose-400/35',
    cellNormal: 'bg-[var(--color-background)] border-[var(--color-border)] hover:border-[var(--color-primary)]/70',
    cellOut: 'bg-[var(--color-muted)]/35 border-[var(--color-border)]/50 opacity-50',
    cellHoliday: 'bg-rose-50/95 dark:bg-[#2E1724]/85 border-rose-300/80 dark:border-rose-400/35 hover:border-rose-400',
    cellSelected: 'bg-sky-100/85 dark:bg-[#193A5C]/85 border-[var(--color-primary)] ring-2 ring-[var(--color-primary)]/45',
    cellToday: 'bg-teal-50/95 dark:bg-[#123E3B]/90 border-2 border-[var(--color-primary)] ring-2 ring-[var(--color-primary)]/35',
    todayDot: 'bg-[var(--color-primary)] text-[var(--color-primary-foreground)]',
    occNormal: 'bg-teal-100/90 dark:bg-teal-900/65 text-teal-950 dark:text-teal-100 border border-teal-300/60 dark:border-teal-400/35',
    occHoliday: 'bg-rose-100/95 dark:bg-rose-900/70 text-rose-900 dark:text-rose-100 border border-rose-300/70 dark:border-rose-400/40',
  },
  emerald_ivory: {
    shell: 'bg-[var(--color-background)]',
    panel: 'rounded-2xl border-[#D8D6C8] dark:border-[#395D4B] border-t-[3px] border-t-[var(--color-primary)] bg-[var(--color-card)] shadow-sm',
    cellRadius: 'rounded-xl',
    weekday: 'bg-[#ECEBE0] dark:bg-[#1E3B2E] text-[var(--color-foreground)] border border-[#D8D6C8] dark:border-[#395D4B]',
    weekdayHoliday: 'bg-rose-500/12 text-rose-700 dark:text-rose-200 border border-rose-400/35',
    cellNormal: 'bg-[#FAF9F3] dark:bg-[#0F241B] border-[#DFDDD0] dark:border-[#335444] hover:border-emerald-500/70 dark:hover:border-emerald-400/60',
    cellOut: 'bg-[#EFECE1]/60 dark:bg-[#0B1913]/70 border-[#DFDDD0]/55 dark:border-[#2B4739]/55 opacity-50',
    cellHoliday: 'bg-rose-50/90 dark:bg-[#2F1822]/85 border-rose-300/85 dark:border-rose-400/35 hover:border-rose-400',
    cellSelected: 'bg-amber-50/95 dark:bg-[#214536] border-[var(--color-primary)] ring-2 ring-[var(--color-primary)]/45',
    cellToday: 'bg-emerald-100/90 dark:bg-[#194A37] border-2 border-[var(--color-primary)] ring-2 ring-emerald-500/35',
    todayDot: 'bg-[var(--color-primary)] text-[var(--color-primary-foreground)]',
    occNormal: 'bg-emerald-100/90 dark:bg-emerald-900/70 text-emerald-950 dark:text-emerald-100 border border-emerald-300/70 dark:border-emerald-400/40',
    occHoliday: 'bg-rose-100/95 dark:bg-rose-900/70 text-rose-900 dark:text-rose-100 border border-rose-300/70 dark:border-rose-400/40',
  },
  glass_mist: {
    shell: 'bg-gradient-to-br from-[#E7F2FC] via-[#EFF7FE] to-[#DFF0FA] dark:from-[#091523] dark:via-[#0D1E32] dark:to-[#0A1828]',
    panel: 'rounded-3xl border-sky-300/65 dark:border-sky-400/25 bg-[var(--glass-bg-strong)] backdrop-blur-md shadow-[0_14px_34px_-16px_rgba(2,119,189,0.22)]',
    cellRadius: 'rounded-2xl',
    weekday: 'bg-sky-100/85 dark:bg-[#19334D] text-[var(--color-foreground)] border border-sky-200/90 dark:border-sky-400/25',
    weekdayHoliday: 'bg-rose-500/14 text-rose-700 dark:text-rose-200 border border-rose-400/35',
    cellNormal: 'bg-white/85 dark:bg-[#0F2135]/90 border-sky-200/85 dark:border-sky-400/22 hover:border-sky-400/80',
    cellOut: 'bg-sky-50/50 dark:bg-[#0B1726]/65 border-sky-200/45 dark:border-sky-400/12 opacity-50',
    cellHoliday: 'bg-rose-50/88 dark:bg-[#2B1728]/85 border-rose-300/80 dark:border-rose-400/35 hover:border-rose-400',
    cellSelected: 'bg-sky-100/95 dark:bg-[#1E4468] border-[var(--color-primary)] ring-2 ring-sky-400/50',
    cellToday: 'bg-cyan-100/90 dark:bg-[#16415E] border-2 border-[var(--color-primary)] ring-2 ring-sky-400/45',
    todayDot: 'bg-[var(--color-primary)] text-[var(--color-primary-foreground)]',
    occNormal: 'bg-sky-100/95 dark:bg-sky-900/65 text-sky-950 dark:text-sky-100 border border-sky-300/70 dark:border-sky-400/40',
    occHoliday: 'bg-rose-100/95 dark:bg-rose-900/70 text-rose-900 dark:text-rose-100 border border-rose-300/70 dark:border-rose-400/40',
  },
  violet_modular: {
    shell: 'bg-[var(--color-background)]',
    panel: 'rounded-xl border-[#C6CFE3] dark:border-[#465278] border-t-[3px] border-t-[var(--color-primary)] bg-[var(--color-card)] shadow-sm',
    cellRadius: 'rounded-lg',
    weekday: 'bg-[#E5EAF5] dark:bg-[#232C4A] text-[var(--color-foreground)] border border-[#C6CFE3] dark:border-[#465278]',
    weekdayHoliday: 'bg-rose-500/14 text-rose-700 dark:text-rose-200 border border-rose-400/35',
    cellNormal: 'bg-[#F8F9FD] dark:bg-[#141A2E] border-[#CDD5E8] dark:border-[#39446B] hover:border-[var(--color-primary)]/80',
    cellOut: 'bg-[#E8ECF6]/60 dark:bg-[#0E1322]/75 border-[#CDD5E8]/55 dark:border-[#313B5C]/55 opacity-50',
    cellHoliday: 'bg-rose-50/92 dark:bg-[#2F192B]/85 border-rose-300/80 dark:border-rose-400/35 hover:border-rose-400',
    cellSelected: 'bg-indigo-100/90 dark:bg-[#28386B] border-[var(--color-primary)] ring-2 ring-[var(--color-primary)]/50',
    cellToday: 'bg-blue-100/95 dark:bg-[#203266] border-2 border-[var(--color-primary)] ring-2 ring-[var(--color-primary)]/40',
    todayDot: 'bg-[var(--color-primary)] text-[var(--color-primary-foreground)]',
    occNormal: 'bg-indigo-100/90 dark:bg-indigo-900/65 text-indigo-950 dark:text-indigo-100 border border-indigo-300/70 dark:border-indigo-400/40',
    occHoliday: 'bg-rose-100/95 dark:bg-rose-900/70 text-rose-900 dark:text-rose-100 border border-rose-300/70 dark:border-rose-400/40',
  },
  bento_grid: {
    shell: 'bg-gradient-to-br from-[#E7F5FA] via-[#EFFAF8] to-[#E2F2F8] dark:from-[#091A25] dark:via-[#0D2330] dark:to-[#0A2229]',
    panel: 'rounded-2xl border-sky-200/85 dark:border-[#386075] bg-[var(--color-card)]/95 shadow-sm',
    cellRadius: 'rounded-xl',
    weekday: 'bg-sky-50/95 dark:bg-[#183547] text-[var(--color-foreground)] border border-sky-200/80 dark:border-[#386075]',
    weekdayHoliday: 'bg-rose-500/12 text-rose-700 dark:text-rose-200 border border-rose-400/35',
    cellNormal: 'bg-[#F5FBFE] dark:bg-[#0E222E] border-[#C7E2EC] dark:border-[#2C5165] hover:border-teal-500/75 dark:hover:border-teal-400/65',
    cellOut: 'bg-[#E5F2F7]/55 dark:bg-[#0A1822]/70 border-[#C7E2EC]/50 dark:border-[#244354]/50 opacity-50',
    cellHoliday: 'bg-rose-50/90 dark:bg-[#2D1726]/85 border-rose-300/80 dark:border-rose-400/35 hover:border-rose-400',
    cellSelected: 'bg-sky-100/90 dark:bg-[#174059] border-sky-500 dark:border-sky-400 ring-2 ring-sky-400/45',
    cellToday: 'bg-emerald-100/90 dark:bg-[#12423D] border-2 border-[var(--color-primary)] ring-2 ring-[var(--color-primary)]/40',
    todayDot: 'bg-[var(--color-primary)] text-[var(--color-primary-foreground)]',
    occNormal: 'bg-teal-100/90 dark:bg-teal-900/65 text-teal-950 dark:text-teal-100 border border-teal-300/70 dark:border-teal-400/40',
    occHoliday: 'bg-rose-100/95 dark:bg-rose-900/70 text-rose-900 dark:text-rose-100 border border-rose-300/70 dark:border-rose-400/40',
  },
};

function toFa(v: number | string): string {
  const digits = '۰۱۲۳۴۵۶۷۸۹';
  return String(v).replace(/\d/g, (d) => digits[Number(d)]);
}

function normalizeText(v: string): string {
  return v.replace(/ي/g, 'ی').replace(/ك/g, 'ک').trim().toLowerCase();
}

export function CalendarView() {
  const [state, setState] = useState<CalendarState | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('month');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('همه');
  const [selectedCompany, setSelectedCompany] = useState<string>('همه');
  const [selectedColor, setSelectedColor] = useState<string>('همه');
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending' | 'done'>('all');
  const [pickerOpen, setPickerOpen] = useState(false);
  const [dragEvent, setDragEvent] = useState<CalendarEventItem | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<CalendarEventItem | null>(null);
  const [formTitle, setFormTitle] = useState('');
  const [formDate, setFormDate] = useState('');
  const [formCompany, setFormCompany] = useState('شخصی');
  const [formCategory, setFormCategory] = useState('مالیات');
  const [formPriority, setFormPriority] = useState('مهم');
  const [formRecurrence, setFormRecurrence] = useState('بدون تکرار');
  const [formColor, setFormColor] = useState<EventColor>('sky');
  const [formTags, setFormTags] = useState('');
  const [formNotes, setFormNotes] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    return onCalendarState((next) => setState(next));
  }, []);

  const act = async (action: string, args: Record<string, unknown> = {}) => {
    setError('');
    setBusy(true);
    try {
      await calendarRequest(action, args);
    } catch (e) {
      setError((e as Error).message || 'خطا در عملیات تقویم');
    } finally {
      setBusy(false);
    }
  };

  const filteredEvents = useMemo(() => {
    if (!state) return [];
    const q = normalizeText(searchQuery);
    return state.events.filter((ev) => {
      if (selectedCategory !== 'همه' && ev.category !== selectedCategory) return false;
      if (selectedCompany !== 'همه' && ev.company !== selectedCompany) return false;
      if (selectedColor !== 'همه' && ev.color !== selectedColor) return false;
      if (statusFilter === 'pending' && ev.done) return false;
      if (statusFilter === 'done' && !ev.done) return false;
      if (q) {
        const hay = normalizeText(
          `${ev.title} ${ev.notes} ${ev.company} ${ev.category} ${(ev.tags || []).join(' ')}`
        );
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [state, searchQuery, selectedCategory, selectedCompany, selectedColor, statusFilter]);

  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEventItem[]>();
    for (const ev of filteredEvents) {
      if (!ev.date_jalali) continue;
      const list = map.get(ev.date_jalali) || [];
      list.push(ev);
      map.set(ev.date_jalali, list);
    }
    return map;
  }, [filteredEvents]);

  if (!state) {
    return (
      <div
        dir="rtl"
        className="h-full flex items-center justify-center bg-[var(--color-background)] text-[var(--color-muted-foreground)] text-sm"
      >
        در حال بارگذاری تقویم و مدیریت رویدادها…
      </div>
    );
  }

  const dark = state.theme === 'dark';
  const presetKey = state.theme_preset || 'default';
  const skin = CALENDAR_SKINS[presetKey] || CALENDAR_SKINS.default;
  const selectedDayEvents = eventsByDate.get(state.view.selected_jalali) || [];
  const selectedDayCell = state.days.find((d) => d.date_jalali === state.view.selected_jalali) || null;
  const activeWeekIdx = Math.max(0, Math.floor(state.days.findIndex((d) => d.date_jalali === state.view.selected_jalali) / 7));
  const weekDays: CalendarDayCell[] = state.days.slice(activeWeekIdx * 7, activeWeekIdx * 7 + 7);

  const openCreateModal = (dateJalali?: string) => {
    setEditingEvent(null);
    setFormTitle('');
    setFormDate(dateJalali || state.view.selected_jalali);
    setFormCompany(state.companies[0] || 'شخصی');
    setFormCategory('مالیات');
    setFormPriority('مهم');
    setFormRecurrence('بدون تکرار');
    setFormColor('sky');
    setFormTags('');
    setFormNotes('');
    setError('');
    setModalOpen(true);
  };

  const openEditModal = (ev: CalendarEventItem) => {
    if (!ev.editable && ev.source_kind !== 'birthday') {
      void act('open_native_edit', { id: ev.id });
      return;
    }
    setEditingEvent(ev);
    setFormTitle(ev.title);
    setFormDate(ev.date_jalali);
    setFormCompany(ev.company || 'شخصی');
    setFormCategory(ev.category || 'مالیات');
    setFormPriority(ev.priority || 'مهم');
    setFormRecurrence(ev.recurrence || 'بدون تکرار');
    setFormColor(ev.color || 'sky');
    setFormTags((ev.tags || []).join('، '));
    setFormNotes(ev.notes || '');
    setError('');
    setModalOpen(true);
  };

  const handleSaveModal = async (e: React.FormEvent) => {
    e.preventDefault();
    const tags = formTags
      .split(/[,،]/)
      .map((t) => t.trim())
      .filter(Boolean)
      .slice(0, 4);
    const payload = {
      title: formTitle.trim(),
      date_jalali: formDate.trim(),
      company: formCompany,
      category: formCategory,
      priority: formPriority,
      recurrence: formRecurrence,
      color: formColor,
      tags,
      notes: formNotes,
    };
    setError('');
    setBusy(true);
    try {
      if (editingEvent) {
        await calendarRequest('update_event', { id: editingEvent.id, ...payload });
      } else {
        await calendarRequest('create_event', payload);
      }
      setModalOpen(false);
    } catch (err) {
      setError((err as Error).message || 'ذخیره انجام نشد');
    } finally {
      setBusy(false);
    }
  };

  const handleDropOnDay = (day: CalendarDayCell) => {
    if (!dragEvent || dragEvent.date_jalali === day.date_jalali) {
      setDragEvent(null);
      return;
    }
    const moved = dragEvent;
    setDragEvent(null);
    void act('reschedule_event', { id: moved.id, date_jalali: day.date_jalali });
  };

  const categories = ['همه', 'مالیات', 'بیمه', 'شخصی', 'سایر', 'تولد'];

  return (
    <div
      dir="rtl"
      data-calendar-view="true"
      data-theme-preset={presetKey}
      className={`cal-shell ${skin.shell} text-[var(--color-foreground)] p-2 md:p-3 flex flex-col`}
    >
      <div className="w-full max-w-[1860px] mx-auto flex-1 flex flex-col gap-2 min-h-0">
        {error && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-500/14 px-4 py-1.5 text-xs text-rose-700 dark:text-rose-200 flex items-center justify-between gap-2">
            <span>{error}</span>
            <button type="button" onClick={() => setError('')} className="cursor-pointer">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Top EventManager Header Bar */}
        <header className={`border ${skin.panel} px-3 py-2 flex flex-wrap items-center justify-between gap-2 shrink-0`}>
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-[var(--color-primary)]/14 text-[var(--color-primary)] flex items-center justify-center shrink-0">
              <CalendarDays className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-base font-extrabold leading-6">{state.title} و مدیریت رویدادها</h1>
              <p className="text-[11px] text-[var(--color-muted-foreground)]">{state.view.greg_range}</p>
            </div>

            <div className="flex items-center gap-1 rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] p-1 mr-1 relative">
              <button
                type="button"
                onClick={() => act('shift_month', { delta: -1 })}
                title="ماه قبل"
                className="p-1.5 rounded-lg hover:bg-[var(--color-accent)] cursor-pointer transition"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => setPickerOpen((v) => !v)}
                className="px-3 py-1 rounded-lg hover:bg-[var(--color-accent)] text-xs font-extrabold cursor-pointer transition min-w-[115px] text-center"
              >
                {state.view.month_name} {state.view.year_fa}
              </button>
              <button
                type="button"
                onClick={() => act('shift_month', { delta: 1 })}
                title="ماه بعد"
                className="p-1.5 rounded-lg hover:bg-[var(--color-accent)] cursor-pointer transition"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              {pickerOpen && (
                <div className="absolute top-11 right-0 z-40 w-72 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] shadow-xl p-3 flex flex-col gap-2">
                  <div className="flex items-center justify-between text-xs font-bold">
                    <button
                      type="button"
                      onClick={() => act('jump_ym', { year: state.view.year - 1, month: state.view.month })}
                      className="px-2 py-1 rounded-lg border border-[var(--color-border)] cursor-pointer"
                    >
                      سال قبل
                    </button>
                    <span>سال {state.view.year_fa}</span>
                    <button
                      type="button"
                      onClick={() => act('jump_ym', { year: state.view.year + 1, month: state.view.month })}
                      className="px-2 py-1 rounded-lg border border-[var(--color-border)] cursor-pointer"
                    >
                      سال بعد
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-1.5">
                    {state.months.map((mName, idx) => (
                      <button
                        key={mName}
                        type="button"
                        onClick={() => {
                          setPickerOpen(false);
                          void act('jump_ym', { year: state.view.year, month: idx + 1 });
                        }}
                        className={`px-2 py-1.5 rounded-lg text-xs cursor-pointer transition ${
                          idx + 1 === state.view.month
                            ? 'bg-[var(--color-primary)] text-[var(--color-primary-foreground)] font-bold'
                            : 'hover:bg-[var(--color-accent)]'
                        }`}
                      >
                        {mName}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={() => act('goto_today')}
              className="px-3 py-1.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] hover:bg-[var(--color-accent)] text-xs font-semibold cursor-pointer transition"
            >
              امروز
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* EventManager View Mode Switcher */}
            <div className="inline-flex rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] p-1 text-xs">
              {(
                [
                  ['month', 'ماهانه'],
                  ['week', 'هفتگی'],
                  ['day', 'روزانه'],
                  ['list', 'فهرست'],
                ] as const
              ).map(([modeId, modeLabel]) => (
                <button
                  key={modeId}
                  type="button"
                  onClick={() => setViewMode(modeId)}
                  className={`px-3 py-1 rounded-lg cursor-pointer transition font-semibold ${
                    viewMode === modeId
                      ? 'bg-[var(--color-primary)] text-[var(--color-primary-foreground)]'
                      : 'text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]'
                  }`}
                >
                  {modeLabel}
                </button>
              ))}
            </div>

            {state.permissions.create && (
              <button
                type="button"
                onClick={() => openCreateModal()}
                className="px-3.5 py-2 rounded-xl bg-[var(--color-primary)] text-[var(--color-primary-foreground)] text-xs font-bold hover:opacity-90 cursor-pointer transition inline-flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>یادآور تازه</span>
              </button>
            )}
            {state.permissions.create && (
              <button
                type="button"
                onClick={() => act('import_excel')}
                title="ورود اکسل"
                className="p-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] hover:bg-[var(--color-accent)] cursor-pointer transition"
              >
                <FileSpreadsheet className="w-4 h-4" />
              </button>
            )}
            {state.permissions.export && (
              <button
                type="button"
                onClick={() => act('export_ics')}
                title="خروجی تقویم (.ics)"
                className="p-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] hover:bg-[var(--color-accent)] cursor-pointer transition"
              >
                <Download className="w-4 h-4" />
              </button>
            )}
            <button
              type="button"
              onClick={() => act('open_occasions')}
              className="px-3 py-1.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] hover:bg-[var(--color-accent)] text-xs font-semibold cursor-pointer transition inline-flex items-center gap-1"
            >
              <Sparkles className="w-3.5 h-3.5 text-[var(--color-primary)]" />
              <span>مناسبت‌ها</span>
            </button>
          </div>
        </header>

        {/* Search + Category + Color + Company Filter Strip (EventManager style) */}
        <div className={`border ${skin.panel} px-3 py-1.5 flex flex-wrap items-center gap-2 shrink-0`}>
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-3.5 h-3.5 text-[var(--color-muted-foreground)] absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="جستجو در رویدادها، شرکت‌ها، برچسب‌ها…"
              className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] pr-8 pl-3 py-1.5 text-xs focus:outline-none focus:border-[var(--color-primary)]"
            />
          </div>

          <div className="flex items-center gap-1 overflow-x-auto pb-0.5">
            {categories.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setSelectedCategory(cat)}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold whitespace-nowrap cursor-pointer transition border ${
                  selectedCategory === cat
                    ? 'bg-[var(--color-primary)] text-[var(--color-primary-foreground)] border-transparent'
                    : 'bg-[var(--color-card)] border-[var(--color-border)] hover:bg-[var(--color-accent)]'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-[var(--color-muted-foreground)]" />
            <select
              value={selectedCompany}
              onChange={(e) => setSelectedCompany(e.target.value)}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-input)] text-[var(--color-foreground)] px-2.5 py-1 text-xs"
            >
              <option value="همه" className="bg-[var(--color-card)] text-[var(--color-foreground)]">همه شرکت‌ها</option>
              {state.companies.map((c) => (
                <option key={c} value={c} className="bg-[var(--color-card)] text-[var(--color-foreground)]">
                  {c}
                </option>
              ))}
              <option value="همکاران" className="bg-[var(--color-card)] text-[var(--color-foreground)]">همکاران (تولدها)</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as 'all' | 'pending' | 'done')}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-input)] text-[var(--color-foreground)] px-2.5 py-1 text-xs"
            >
              <option value="all" className="bg-[var(--color-card)] text-[var(--color-foreground)]">همه وضعیت‌ها</option>
              <option value="pending" className="bg-[var(--color-card)] text-[var(--color-foreground)]">در انتظار</option>
              <option value="done" className="bg-[var(--color-card)] text-[var(--color-foreground)]">انجام‌شده</option>
            </select>
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setSelectedColor('همه')}
              className={`px-2 py-1 rounded-lg text-[10px] border cursor-pointer ${
                selectedColor === 'همه'
                  ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/12 font-bold'
                  : 'border-[var(--color-border)] bg-[var(--color-card)]'
              }`}
            >
              همه رنگ‌ها
            </button>
            {(Object.keys(COLOR_MAP) as EventColor[]).map((col) => (
              <button
                key={col}
                type="button"
                title={COLOR_MAP[col].label}
                onClick={() => setSelectedColor((prev) => (prev === col ? 'همه' : col))}
                className={`w-5 h-5 rounded-full ${COLOR_MAP[col].dot} cursor-pointer transition ${
                  selectedColor === col ? 'ring-2 ring-offset-2 ring-[var(--color-primary)] scale-110' : 'opacity-75 hover:opacity-100'
                }`}
              />
            ))}
          </div>
        </div>

        {/* Main Workspace Split: Calendar Surface + Selected Day Drawer */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-2.5 flex-1 min-h-0">
          <section className={`lg:col-span-9 border ${skin.panel} p-2.5 flex flex-col gap-1.5 min-h-0 min-w-0`}>
            {viewMode === 'month' && (
              <>
                <div className="grid grid-cols-7 gap-1.5 text-center text-xs font-extrabold pb-1.5 border-b border-[var(--color-border)] shrink-0">
                  {state.weekdays.map((wd, i) => (
                    <div key={wd} className={`truncate py-1 ${skin.cellRadius} ${i >= 5 ? skin.weekdayHoliday : skin.weekday}`}>
                      {wd}
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-7 grid-rows-6 gap-1.5 flex-1 min-h-0">
                  {state.days.map((day) => {
                    const dayEvents = eventsByDate.get(day.date_jalali) || [];
                    const hasOcc = Boolean(state.preferences.show_occasions && day.occasions[0]);
                    const maxVisibleEvents = hasOcc ? 1 : 2;
                    return (
                      <div
                        key={day.date_jalali}
                        onClick={() => void act('select_date', { date_jalali: day.date_jalali })}
                        onDragOver={(e) => e.preventDefault()}
                        onDrop={() => handleDropOnDay(day)}
                        className={`group ${skin.cellRadius} border px-1.5 py-1 flex flex-col justify-start gap-1 cursor-pointer transition-colors h-full min-h-0 min-w-0 overflow-hidden ${
                          day.is_today
                            ? skin.cellToday
                            : day.is_selected
                            ? skin.cellSelected
                            : day.is_holiday
                            ? skin.cellHoliday
                            : day.in_month
                            ? skin.cellNormal
                            : skin.cellOut
                        }`}
                      >
                        <div className="flex items-center justify-between gap-1 shrink-0 leading-4">
                          <div className="flex items-center gap-1 min-w-0">
                            <span
                              className={`text-xs font-extrabold leading-4 ${
                                day.is_today
                                  ? `px-1.5 py-0.5 rounded-md ${skin.todayDot}`
                                  : day.is_holiday
                                  ? 'text-rose-600 dark:text-rose-300'
                                  : 'text-[var(--color-foreground)]'
                              }`}
                            >
                              {day.day_fa}
                            </span>
                            {state.preferences.show_tasks && dayEvents.length > maxVisibleEvents && (
                              <span
                                title={`${toFa(dayEvents.length)} رویداد در این روز`}
                                className="text-[9px] leading-3.5 font-bold px-1 rounded bg-[var(--color-primary)]/18 text-[var(--color-primary)]"
                              >
                                +{toFa(dayEvents.length - maxVisibleEvents)}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            {state.preferences.show_gregorian && (
                              <span className="text-[9px] font-medium text-[var(--color-muted-foreground)]">{day.greg_label}</span>
                            )}
                            {state.permissions.create && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  openCreateModal(day.date_jalali);
                                }}
                                title="افزودن رویداد در این روز"
                                className="opacity-0 group-hover:opacity-100 p-0.5 rounded bg-[var(--color-primary)]/15 text-[var(--color-primary)] cursor-pointer transition"
                              >
                                <Plus className="w-2.5 h-2.5" />
                              </button>
                            )}
                          </div>
                        </div>

                        <div className="flex flex-col gap-0.5 min-w-0 flex-1 overflow-hidden">
                        {hasOcc && (
                          <div
                            title={day.occasions.map((o) => o.title).join('\n')}
                            className={`text-[9px] leading-[15px] font-semibold px-1.5 rounded truncate shrink-0 ${
                              day.occasions.some((o) => o.holiday)
                                ? skin.occHoliday
                                : skin.occNormal
                            }`}
                          >
                            {day.occasions[0].title}
                          </div>
                        )}

                        {state.preferences.show_tasks &&
                          dayEvents.slice(0, maxVisibleEvents).map((ev) => {
                            const style = COLOR_MAP[ev.color] || COLOR_MAP.sky;
                            return (
                              <div
                                key={ev.id}
                                draggable={ev.editable}
                                onDragStart={() => setDragEvent(ev)}
                                onDragEnd={() => setDragEvent(null)}
                                title={`${ev.title} (${ev.company} · ${ev.category})${ev.notes ? '\n' + ev.notes : ''}`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  openEditModal(ev);
                                }}
                                className={`rounded-md border px-1.5 text-[10px] leading-[15px] font-semibold flex items-center gap-1 truncate cursor-pointer shrink-0 ${style.bg} ${style.border} ${style.text} ${
                                  ev.done ? 'line-through opacity-60' : ''
                                }`}
                              >
                                {ev.source_kind === 'birthday' ? (
                                  <Cake className="w-2.5 h-2.5 shrink-0" />
                                ) : (
                                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${style.dot}`} />
                                )}
                                <span className="truncate">{ev.title}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}

            {viewMode === 'week' && (
              <div className="grid grid-cols-1 md:grid-cols-7 gap-2.5 flex-1">
                {weekDays.map((day) => {
                  const list = eventsByDate.get(day.date_jalali) || [];
                  return (
                    <div
                      key={day.date_jalali}
                      onClick={() => void act('select_date', { date_jalali: day.date_jalali })}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={() => handleDropOnDay(day)}
                      className={`${skin.cellRadius} border p-2.5 flex flex-col gap-2 cursor-pointer transition ${
                        day.is_today
                          ? skin.todayCell
                          : day.is_selected
                          ? skin.selectedCell
                          : skin.cellDefault
                      }`}
                    >
                      <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-1.5">
                        <div>
                          <div className={`text-xs font-bold ${day.is_holiday ? 'text-rose-600 dark:text-rose-300' : ''}`}>
                            {state.weekdays[day.weekday_idx]}
                          </div>
                          <div className="text-sm font-extrabold">{day.day_fa}</div>
                        </div>
                        {state.permissions.create && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              openCreateModal(day.date_jalali);
                            }}
                            className="p-1 rounded-lg bg-[var(--color-background)] border border-[var(--color-border)] cursor-pointer"
                          >
                            <Plus className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                      <div className="flex flex-col gap-1.5 flex-1 overflow-y-auto">
                        {list.map((ev) => {
                          const st = COLOR_MAP[ev.color] || COLOR_MAP.sky;
                          return (
                            <div
                              key={ev.id}
                              draggable={ev.editable}
                              onDragStart={() => setDragEvent(ev)}
                              onClick={(e) => {
                                e.stopPropagation();
                                openEditModal(ev);
                              }}
                              className={`rounded-xl border p-2 text-xs cursor-pointer ${st.bg} ${st.border} ${st.text}`}
                            >
                              <div className="font-bold truncate">{ev.title}</div>
                              <div className="text-[10px] opacity-80 mt-0.5">{ev.company}</div>
                            </div>
                          );
                        })}
                        {list.length === 0 && (
                          <div className="text-[11px] text-[var(--color-muted-foreground)]">بدون رویداد</div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {viewMode === 'day' && (
              <div className="flex flex-col gap-3 flex-1">
                <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-2.5">
                  <div>
                    <h2 className="text-base font-extrabold">{state.view.selected_fa}</h2>
                    <p className="text-xs text-[var(--color-muted-foreground)]">{state.view.selected_gregorian}</p>
                  </div>
                  {state.permissions.create && (
                    <button
                      type="button"
                      onClick={() => openCreateModal(state.view.selected_jalali)}
                      className="px-3 py-1.5 rounded-xl bg-[var(--color-primary)] text-[var(--color-primary-foreground)] text-xs font-bold cursor-pointer"
                    >
                      افزودن به امروز
                    </button>
                  )}
                </div>
                {selectedDayEvents.length === 0 ? (
                  <div className="flex-1 flex items-center justify-center text-sm text-[var(--color-muted-foreground)]">
                    رویدادی با فیلترهای فعلی برای این روز ثبت نشده است.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {selectedDayEvents.map((ev) => {
                      const st = COLOR_MAP[ev.color] || COLOR_MAP.sky;
                      return (
                        <div
                          key={ev.id}
                          className={`${skin.cellRadius} border p-3.5 flex flex-col gap-2 ${st.bg} ${st.border} ${st.text}`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="font-bold text-sm">{ev.title}</div>
                            <span className="text-[11px] px-2 py-0.5 rounded-full bg-[var(--color-card)] border border-[var(--color-border)]">
                              {ev.category}
                            </span>
                          </div>
                          {ev.notes && <p className="text-xs text-[var(--color-muted-foreground)]">{ev.notes}</p>}
                          <div className="flex flex-wrap items-center gap-1.5 pt-1">
                            {ev.tags.map((t) => (
                              <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--color-card)]">
                                #{t}
                              </span>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {viewMode === 'list' && (
              <div className="flex flex-col gap-2 flex-1 overflow-y-auto">
                <div className="flex items-center justify-between text-xs font-bold pb-1 border-b border-[var(--color-border)]">
                  <span className="inline-flex items-center gap-1.5">
                    <List className="w-4 h-4 text-[var(--color-primary)]" />
                    <span>فهرست رویدادها ({toFa(filteredEvents.length)})</span>
                  </span>
                </div>
                {filteredEvents.length === 0 ? (
                  <div className="py-10 text-center text-xs text-[var(--color-muted-foreground)]">
                    موردی یافت نشد.
                  </div>
                ) : (
                  filteredEvents
                    .slice()
                    .sort((a, b) => a.date_jalali.localeCompare(b.date_jalali))
                    .map((ev) => {
                      const st = COLOR_MAP[ev.color] || COLOR_MAP.sky;
                      return (
                        <div
                          key={ev.id}
                          className={`${skin.cellRadius} border ${skin.cellDefault} px-3.5 py-2.5 flex flex-wrap items-center justify-between gap-3 transition`}
                        >
                          <div className="flex items-center gap-2.5 min-w-0 flex-1">
                            {ev.source_kind !== 'birthday' && state.permissions.edit && (
                              <button
                                type="button"
                                onClick={() => void act('toggle_done', { id: ev.id, done: !ev.done, date_jalali: ev.date_jalali })}
                                className="cursor-pointer shrink-0"
                              >
                                {ev.done ? (
                                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                ) : (
                                  <Circle className="w-4 h-4 text-[var(--color-muted-foreground)]" />
                                )}
                              </button>
                            )}
                            <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${st.dot}`} />
                            <div className="min-w-0">
                              <div className={`text-xs font-bold truncate ${ev.done ? 'line-through opacity-60' : ''}`}>
                                {ev.title}
                              </div>
                              <div className="text-[11px] text-[var(--color-muted-foreground)]">
                                {toFa(ev.date_jalali)} · {ev.company} · {ev.category}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5">
                            {ev.editable && (
                              <button
                                type="button"
                                onClick={() => openEditModal(ev)}
                                className="p-1.5 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-accent)] cursor-pointer"
                              >
                                <Edit3 className="w-3.5 h-3.5" />
                              </button>
                            )}
                            {ev.source_kind !== 'birthday' && (
                              <button
                                type="button"
                                title="محاسبه جریمه"
                                onClick={() => void act('calculate_penalty', { id: ev.id })}
                                className="p-1.5 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-accent)] cursor-pointer"
                              >
                                <Calculator className="w-3.5 h-3.5" />
                              </button>
                            )}
                            {ev.editable && state.permissions.delete && (
                              <button
                                type="button"
                                onClick={() => void act('delete_event', { id: ev.id })}
                                className="p-1.5 rounded-lg border border-rose-300/60 text-rose-600 dark:text-rose-300 hover:bg-rose-500/12 cursor-pointer"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })
                )}
              </div>
            )}
          </section>

          {/* Right/Side Inspector for Selected Jalali Day */}
          <aside className={`lg:col-span-3 border ${skin.panel} p-3 flex flex-col gap-2 min-h-0 min-w-0`}>
            <div className="flex items-start justify-between gap-2 pb-2.5 border-b border-[var(--color-border)]">
              <div>
                <div className="text-sm font-extrabold">{state.view.selected_fa}</div>
                <div className="text-[11px] text-[var(--color-muted-foreground)]">
                  میلادی: {state.view.selected_gregorian}
                  {selectedDayCell?.is_holiday ? ' · تعطیل' : ''}
                </div>
              </div>
              {state.permissions.create && (
                <button
                  type="button"
                  onClick={() => openCreateModal(state.view.selected_jalali)}
                  className="p-1.5 rounded-lg bg-[var(--color-primary)]/14 text-[var(--color-primary)] hover:bg-[var(--color-primary)]/22 cursor-pointer"
                >
                  <Plus className="w-4 h-4" />
                </button>
              )}
            </div>

            {state.view.selected_occasions.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <div className="text-xs font-bold">مناسبت‌های روز</div>
                {state.view.selected_occasions.map((occ, idx) => (
                  <div
                    key={`${occ.title}-${idx}`}
                    className={`rounded-xl border px-2.5 py-1.5 text-[11px] flex items-center justify-between gap-2 ${
                      occ.holiday
                        ? skin.occHoliday
                        : skin.occNormal
                    }`}
                  >
                    <span className="truncate">• {occ.title}</span>
                    {occ.source && (
                      <button
                        type="button"
                        onClick={() => void act('open_occasion_source', { url: occ.source })}
                        className="shrink-0 opacity-75 hover:opacity-100 cursor-pointer"
                      >
                        <ArrowUpRight className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between text-xs font-bold">
              <span>رویدادهای روز ({toFa(selectedDayEvents.length)})</span>
              <span className="text-[10px] text-[var(--color-muted-foreground)]">
                کشیدن و رها کردن روی روزهای ماه فعال است
              </span>
            </div>

            <div className="flex flex-col gap-2 flex-1 overflow-y-auto">
              {selectedDayEvents.length === 0 ? (
                <p className="text-xs text-[var(--color-muted-foreground)]">
                  در این روز رویدادی ثبت نشده است.
                </p>
              ) : (
                selectedDayEvents.map((ev) => {
                  const st = COLOR_MAP[ev.color] || COLOR_MAP.sky;
                  return (
                    <div
                      key={ev.id}
                      className={`rounded-xl border p-2.5 flex flex-col gap-1.5 ${st.bg} ${st.border} ${st.text}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-1.5 min-w-0">
                          {ev.source_kind !== 'birthday' && state.permissions.edit && (
                            <button
                              type="button"
                              onClick={() => void act('toggle_done', { id: ev.id, done: !ev.done, date_jalali: ev.date_jalali })}
                              className="cursor-pointer shrink-0"
                            >
                              {ev.done ? (
                                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                              ) : (
                                <Circle className="w-4 h-4 opacity-70" />
                              )}
                            </button>
                          )}
                          <span className={`text-xs font-bold truncate ${ev.done ? 'line-through opacity-60' : ''}`}>
                            {ev.title}
                          </span>
                        </div>
                        {ev.editable && (
                          <button
                            type="button"
                            onClick={() => openEditModal(ev)}
                            className="p-1 rounded-lg hover:bg-[var(--color-card)]/60 cursor-pointer shrink-0"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                      <div className="text-[11px] opacity-80 flex flex-wrap items-center gap-2">
                        <span>{ev.company}</span>
                        <span>· {ev.category}</span>
                        {ev.recurrence !== 'بدون تکرار' && <span>· {ev.recurrence}</span>}
                      </div>
                      {ev.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {ev.tags.map((tag) => (
                            <span
                              key={tag}
                              className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-card)]/75"
                            >
                              <Tag className="w-2.5 h-2.5" />
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                      {ev.notes && <p className="text-[11px] opacity-85 line-clamp-2">{ev.notes}</p>}
                    </div>
                  );
                })
              )}
            </div>
          </aside>
        </div>
      </div>

      {/* Create / Edit EventModal (21st.dev EventManager Style) */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setModalOpen(false)}
        >
          <form
            onSubmit={handleSaveModal}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-lg rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] shadow-2xl p-5 flex flex-col gap-3.5"
          >
            <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-2.5">
              <h3 className="font-extrabold text-sm flex items-center gap-2">
                <CalendarIcon className="w-4 h-4 text-[var(--color-primary)]" />
                <span>{editingEvent ? 'ویرایش رویداد' : 'ثبت رویداد و یادآور تازه'}</span>
              </h3>
              <button type="button" onClick={() => setModalOpen(false)} className="cursor-pointer p-1 rounded-lg hover:bg-[var(--color-accent)]">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <label className="flex flex-col gap-1 sm:col-span-2">
                <span className="font-bold">عنوان رویداد *</span>
                <input
                  required
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  placeholder="مثلاً ارسال لیست بیمه یا اظهارنامه…"
                  className="rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="font-bold">تاریخ شمسی *</span>
                <input
                  required
                  dir="ltr"
                  value={formDate}
                  onChange={(e) => setFormDate(e.target.value)}
                  placeholder="1405/08/25"
                  className="rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-center"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="font-bold">شرکت / بخش</span>
                <select
                  value={formCompany}
                  onChange={(e) => setFormCompany(e.target.value)}
                  className="rounded-xl border border-[var(--color-border)] bg-[var(--color-input)] text-[var(--color-foreground)] px-3 py-2"
                >
                  {state.companies.map((c) => (
                    <option key={c} value={c} className="bg-[var(--color-card)] text-[var(--color-foreground)]">
                      {c}
                    </option>
                  ))}
                  {!state.companies.includes('شخصی') && (
                    <option value="شخصی" className="bg-[var(--color-card)] text-[var(--color-foreground)]">
                      شخصی
                    </option>
                  )}
                </select>
              </label>

              <label className="flex flex-col gap-1">
                <span className="font-bold">دسته‌بندی</span>
                <select
                  value={formCategory}
                  onChange={(e) => setFormCategory(e.target.value)}
                  className="rounded-xl border border-[var(--color-border)] bg-[var(--color-input)] text-[var(--color-foreground)] px-3 py-2"
                >
                  {['مالیات', 'بیمه', 'شخصی', 'سایر'].map((c) => (
                    <option key={c} value={c} className="bg-[var(--color-card)] text-[var(--color-foreground)]">
                      {c}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col gap-1">
                <span className="font-bold">تکرار</span>
                <select
                  value={formRecurrence}
                  onChange={(e) => setFormRecurrence(e.target.value)}
                  className="rounded-xl border border-[var(--color-border)] bg-[var(--color-input)] text-[var(--color-foreground)] px-3 py-2"
                >
                  {['بدون تکرار', 'ماهانه', 'فصلی', 'سالانه'].map((r) => (
                    <option key={r} value={r} className="bg-[var(--color-card)] text-[var(--color-foreground)]">
                      {r}
                    </option>
                  ))}
                </select>
              </label>

              <div className="flex flex-col gap-1 sm:col-span-2">
                <span className="font-bold">رنگ و برچسب</span>
                <div className="flex flex-wrap items-center gap-2">
                  {(Object.keys(COLOR_MAP) as EventColor[]).map((col) => (
                    <button
                      key={col}
                      type="button"
                      onClick={() => setFormColor(col)}
                      className={`w-6 h-6 rounded-full ${COLOR_MAP[col].dot} cursor-pointer transition ${
                        formColor === col ? 'ring-2 ring-offset-2 ring-[var(--color-primary)] scale-110' : 'opacity-70'
                      }`}
                    />
                  ))}
                  <input
                    value={formTags}
                    onChange={(e) => setFormTags(e.target.value)}
                    placeholder="برچسب‌ها (با ویرگول جدا کنید)"
                    className="flex-1 min-w-[160px] rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-1.5"
                  />
                </div>
              </div>

              <label className="flex flex-col gap-1 sm:col-span-2">
                <span className="font-bold">یادداشت</span>
                <textarea
                  rows={3}
                  value={formNotes}
                  onChange={(e) => setFormNotes(e.target.value)}
                  className="rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2"
                />
              </label>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[var(--color-border)]">
              <div className="flex items-center gap-2">
                {editingEvent && editingEvent.editable && state.permissions.delete && (
                  <button
                    type="button"
                    onClick={async () => {
                      setModalOpen(false);
                      await act('delete_event', { id: editingEvent.id });
                    }}
                    className="px-3 py-1.5 rounded-xl border border-rose-400/50 text-rose-600 dark:text-rose-300 text-xs font-semibold hover:bg-rose-500/10 cursor-pointer"
                  >
                    حذف
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setModalOpen(false);
                    void act(editingEvent ? 'open_native_edit' : 'open_native_add', editingEvent ? { id: editingEvent.id } : {});
                  }}
                  className="px-3 py-1.5 rounded-xl border border-[var(--color-border)] text-xs cursor-pointer"
                >
                  تنظیم پیشرفته زمان‌بندی
                </button>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-3 py-1.5 rounded-xl border border-[var(--color-border)] text-xs cursor-pointer"
                >
                  انصراف
                </button>
                <button
                  type="submit"
                  disabled={busy}
                  className="px-4 py-1.5 rounded-xl bg-[var(--color-primary)] text-[var(--color-primary-foreground)] text-xs font-bold hover:opacity-90 disabled:opacity-50 cursor-pointer"
                >
                  {editingEvent ? 'ذخیره تغییرات' : 'ثبت رویداد'}
                </button>
              </div>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
