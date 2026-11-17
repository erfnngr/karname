import { connectAppearance } from './appearance';
import React, { useEffect, useRef, useState } from 'react';
import { PromptInput } from '@/components/ui/ai-chat-input';
import { Button } from '@/components/ui/button';
import {
  AlertCircle,
  Brain,
  CheckCircle2,
  Clock,
  Cpu,
  History,
  Plus,
  RotateCcw,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';

type Suggestion = { title: string; text: string; mode: string };
type TemplateItem = { key: string; title: string; text: string; mode: string; primary?: boolean };
type RequestHistoryItem = { id: string; request: string; status: string; status_label: string; detail: string };
type ScheduledPromptItem = {
  id: string;
  due_at: string;
  due_jalali: string;
  status: string;
  status_label: string;
  prompt: string;
  mode: string;
};
type NativeValue =
  | { scheduled?: boolean }
  | Suggestion[]
  | RequestHistoryItem[]
  | ScheduledPromptItem[]
  | null;

type State = {
  items: { role: string; content: string }[];
  busy: boolean;
  status: string;
  can_send: boolean;
  can_stop: boolean;
  can_review: boolean;
  mode: string;
  context: boolean;
  context_enabled: boolean;
  model_name?: string;
  provider?: string;
  memory_available?: boolean;
  memory_enabled?: boolean;
  templates?: TemplateItem[];
};

type Signal<T extends (...args: any[]) => void> = { connect: (callback: T) => void };
type Bridge = {
  changed: Signal<(raw: string) => void>;
  completed: Signal<(id: string, raw: string) => void>;
  request: (id: string, action: string, raw: string) => void;
};

const MODE_LABELS: Record<string, string> = {
  app: 'دستیار برنامه',
  plan: 'برنامه‌ریزی شخصی',
  chat: 'گفتگوی آزاد',
};

export function AssistantView() {
  const [state, setState] = useState<State>({
    items: [],
    busy: false,
    status: 'در حال اتصال…',
    can_send: false,
    can_stop: false,
    can_review: false,
    mode: 'app',
    context: false,
    context_enabled: false,
    model_name: '',
    memory_available: false,
    memory_enabled: false,
    templates: [],
  });
  const transcript = useRef<HTMLElement | null>(null);
  const follow = useRef(true);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const sendingRef = useRef(false);
  const [error, setError] = useState('');

  const [historyModal, setHistoryModal] = useState<RequestHistoryItem[] | null>(null);
  const [scheduledModal, setScheduledModal] = useState<ScheduledPromptItem[] | null>(null);
  const [templatesOpen, setTemplatesOpen] = useState(false);
  const [confirmClearMem, setConfirmClearMem] = useState(false);

  const bridge = useRef<Bridge | null>(null);
  const pending = useRef(new Map<string, { resolve: (value: NativeValue) => void; reject: (error: Error) => void; timer: number }>());

  const call = (action: string, args: Record<string, unknown> = {}) =>
    new Promise<NativeValue>((resolve, reject) => {
      const native = bridge.current;
      if (!native) {
        reject(Error('اتصال دستیار برقرار نیست.'));
        return;
      }
      const id = crypto.randomUUID();
      const timer = window.setTimeout(
        () => {
          pending.current.delete(id);
          reject(Error('پاسخ برنامه دریافت نشد.'));
        },
        ['settings', 'review', 'scheduled', 'history', 'schedule'].includes(action) ? 1800000 : 60000
      );
      pending.current.set(id, { resolve, reject, timer });
      native.request(id, action, JSON.stringify(args));
    });

  useEffect(() => {
    let active = true;
    const Channel = window.QWebChannel as any;
    if (!Channel || !window.qt) {
      setError('اتصال دستیار برقرار نیست.');
      return;
    }
    new Channel(window.qt.webChannelTransport, (channel: any) => {
      if (!active) return;
      connectAppearance(channel.objects.appearance);
      const native: Bridge = channel.objects.assistant;
      if (!native) {
        setError('دستیار در دسترس نیست.');
        return;
      }
      bridge.current = native;
      native.changed.connect((raw) => {
        if (active) {
          try {
            setState(JSON.parse(raw));
          } catch {
            setError('پاسخ دستیار معتبر نیست.');
          }
        }
      });
      native.completed.connect((id, raw) => {
        const entry = pending.current.get(id);
        if (!entry) return;
        pending.current.delete(id);
        window.clearTimeout(entry.timer);
        try {
          const result = JSON.parse(raw);
          result.ok ? entry.resolve(result.value) : entry.reject(Error(result.error || 'عملیات انجام نشد.'));
        } catch {
          entry.reject(Error('پاسخ برنامه معتبر نیست.'));
        }
      });
      void call('refresh').catch((e) => setError(String(e)));
    });
    return () => {
      active = false;
      bridge.current = null;
      for (const entry of pending.current.values()) {
        window.clearTimeout(entry.timer);
        entry.reject(Error('صفحه بسته شد.'));
      }
      pending.current.clear();
    };
  }, []);

  const run = (action: string, args: Record<string, unknown> = {}) => {
    setError('');
    void call(action, args).catch((e) => setError(String(e)));
  };

  React.useLayoutEffect(() => {
    const el = transcript.current;
    if (el && follow.current) el.scrollTop = el.scrollHeight;
  }, [state.items]);

  const send = (text: string) => {
    if (sendingRef.current || !text.trim()) return;
    sendingRef.current = true;
    setSending(true);
    follow.current = true;
    setError('');
    void call('send', { text })
      .catch((e) => {
        setDraft(text);
        setError(String(e));
      })
      .finally(() => {
        sendingRef.current = false;
        setSending(false);
      });
  };

  useEffect(() => {
    let active = true;
    if (draft.trim().split(/\s+/).filter(Boolean).length < 2) {
      setSuggestions([]);
      return;
    }
    const timer = window.setTimeout(() => {
      void call('suggest', { text: draft })
        .then((value) => {
          if (active) setSuggestions(Array.isArray(value) ? (value as Suggestion[]) : []);
        })
        .catch(() => {
          if (active) setSuggestions([]);
        });
    }, 300);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [draft]);

  const schedule = () => {
    const text = draft;
    if (!text.trim()) return;
    setError('');
    void call('schedule', { text })
      .then((result) => {
        if (result && !Array.isArray(result) && (result as { scheduled?: boolean }).scheduled) {
          setDraft((current) => (current === text ? '' : current));
        }
      })
      .catch((e) => setError(String(e)));
  };

  const openHistoryModal = async () => {
    setError('');
    try {
      const list = await call('request_history_list');
      setHistoryModal(Array.isArray(list) ? (list as RequestHistoryItem[]) : []);
    } catch (e) {
      setError(String(e));
    }
  };

  const openScheduledModal = async () => {
    setError('');
    try {
      const list = await call('scheduled_list');
      setScheduledModal(Array.isArray(list) ? (list as ScheduledPromptItem[]) : []);
    } catch (e) {
      setError(String(e));
    }
  };

  const cancelScheduledItem = async (id: string) => {
    try {
      await call('scheduled_cancel', { id });
      const list = await call('scheduled_list');
      setScheduledModal(Array.isArray(list) ? (list as ScheduledPromptItem[]) : []);
    } catch (e) {
      setError(String(e));
    }
  };

  const applyTemplate = (item: { text: string; mode?: string }) => {
    setDraft(item.text);
    setSuggestions([]);
    setTemplatesOpen(false);
    if (item.mode && ['app', 'plan', 'chat'].includes(item.mode)) {
      run('mode', { value: item.mode });
    }
  };

  const lastMessage = state.items[state.items.length - 1];
  const awaitingClarification =
    !state.busy &&
    lastMessage?.role === 'assistant' &&
    (lastMessage.content.includes('؟') || lastMessage.content.includes('?'));

  const featuredTemplates = (state.templates || []).slice(0, 6);

  return (
    <main dir="rtl" className="glass-backdrop flex h-screen w-full flex-col overflow-hidden text-foreground select-text">
      {/* Minimal Modern Glass Header */}
      <header className="glass-surface z-10 flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border/60 px-5 py-3">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 items-center justify-center rounded-xl bg-primary/15 text-primary">
            <Sparkles className="size-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <strong className="text-sm font-bold">دستیار هوشمند کارنامه</strong>
              {state.model_name && (
                <button
                  type="button"
                  disabled={state.busy}
                  onClick={() => run('settings')}
                  title="تنظیم مدل و اتصال سرویس هوش مصنوعی"
                  className="glass-pill inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground transition hover:text-foreground"
                >
                  <Cpu className="size-3" />
                  <span>{state.model_name}</span>
                </button>
              )}
            </div>
            <p role="status" className="truncate text-[11px] text-muted-foreground">
              {state.status}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {/* App Context Permission Toggle (only for existing authorized access) */}
          <button
            type="button"
            disabled={!state.context_enabled || state.busy}
            onClick={() => run('context', { enabled: !state.context })}
            title="دسترسی دستیار به تقویم، کارها و خلاصه مجاز پرونده‌ها و پیام‌ها"
            className={`glass-pill inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition disabled:opacity-75 ${
              state.context ? 'border-emerald-500/45 bg-emerald-500/12 text-emerald-700 dark:border-emerald-400/40 dark:bg-emerald-500/20 dark:text-emerald-200' : 'text-muted-foreground'
            }`}
          >
            <ShieldCheck className="size-3.5" />
            <span>{state.context ? 'دسترسی برنامه فعال' : 'فقط گفتگو'}</span>
          </button>

          {/* Memory Toggle + Erase */}
          {state.memory_available && (
            <div className="glass-pill inline-flex items-center rounded-full p-0.5">
              <button
                type="button"
                disabled={state.busy}
                onClick={() => run('memory', { enabled: !state.memory_enabled })}
                title="حافظه رمزگذاری‌شده دستیار روی همین رایانه"
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs transition ${
                  state.memory_enabled ? 'bg-indigo-500/15 font-medium text-indigo-700 dark:text-indigo-300' : 'text-muted-foreground'
                }`}
              >
                <Brain className="size-3.5" />
                <span>حافظه</span>
              </button>
              <button
                type="button"
                disabled={state.busy}
                onClick={() => setConfirmClearMem(true)}
                title="پاک کردن حافظه شخصی"
                aria-label="پاک کردن حافظه شخصی"
                className="rounded-full p-1 text-muted-foreground transition hover:bg-red-500/15 hover:text-red-600"
              >
                <Trash2 className="size-3" />
              </button>
            </div>
          )}

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => void openHistoryModal()}
            className="h-8 gap-1.5 rounded-full px-3 text-xs"
          >
            <History className="size-3.5" />
            <span>درخواست‌ها</span>
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => void openScheduledModal()}
            className="h-8 gap-1.5 rounded-full px-3 text-xs"
          >
            <Clock className="size-3.5" />
            <span>زمان‌بندی‌ها</span>
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={state.busy}
            onClick={() => run('settings')}
            className="h-8 gap-1.5 rounded-full px-3 text-xs"
          >
            <Settings2 className="size-3.5" />
            <span>تنظیمات مدل</span>
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={state.busy}
            onClick={() => run('new')}
            className="glass-pill h-8 gap-1.5 rounded-full px-3 text-xs"
          >
            <RotateCcw className="size-3.5" />
            <span>گفتگوی تازه</span>
          </Button>
        </div>
      </header>

      {error && (
        <div role="alert" className="mx-auto mt-2 flex w-[min(48rem,92%)] items-center justify-between gap-2 rounded-2xl border border-red-500/35 bg-red-500/10 px-4 py-2 text-xs text-red-700 dark:text-red-300">
          <span>{error}</span>
          <button onClick={() => setError('')} className="rounded p-0.5 hover:bg-red-500/15">
            <X className="size-3.5" />
          </button>
        </div>
      )}

      {/* Minimal Centered Transcript */}
      <section
        ref={transcript}
        onScroll={(e) => {
          const el = e.currentTarget;
          follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
        className="flex-1 overflow-y-auto px-4 py-6"
      >
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-3.5">
          {state.items.length === 0 ? (
            <div className="my-auto flex flex-col items-center justify-center py-10 text-center">
              <div className="glass-card mb-4 flex size-14 items-center justify-center rounded-3xl text-primary">
                <Sparkles className="size-7" />
              </div>
              <h2 className="mb-2 text-lg font-bold">چطور می‌توانم کمکتان کنم؟</h2>
              <p className="mb-6 max-w-md text-xs leading-6 text-muted-foreground">
                درخواست خود را به زبان ساده بنویسید؛ دستیار بر اساس دسترسی حساب شما در چت، تقویم، کارها و بخش‌های مجاز اقدام کرده و نتیجه واقعی را گزارش می‌دهد.
              </p>
              {featuredTemplates.length > 0 && (
                <div className="grid w-full max-w-2xl grid-cols-1 gap-2 sm:grid-cols-2">
                  {featuredTemplates.map((t) => (
                    <button
                      key={t.key}
                      type="button"
                      onClick={() => applyTemplate(t)}
                      className="glass-card rounded-2xl px-4 py-3 text-right transition hover:-translate-y-0.5 hover:border-primary/40"
                    >
                      <div className="text-xs font-bold text-foreground">{t.title}</div>
                      <div className="mt-1 line-clamp-1 text-[11px] text-muted-foreground">{t.text}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            state.items.map((item, index) => {
              if (item.role === 'app') {
                const hasIssue = item.content.includes('نیازمند بررسی');
                return (
                  <article
                    key={index}
                    className={`w-full max-w-2xl self-end rounded-2xl border px-4 py-3 text-xs leading-6 whitespace-pre-wrap shadow-sm ${
                      hasIssue
                        ? 'border-amber-500/45 bg-amber-500/12 text-amber-950 dark:text-amber-100'
                        : 'border-emerald-500/45 bg-emerald-500/12 text-emerald-950 dark:text-emerald-100'
                    }`}
                  >
                    <div className="mb-1 flex items-center gap-1.5 font-bold">
                      {hasIssue ? (
                        <AlertCircle className="size-4 text-amber-600 dark:text-amber-300" />
                      ) : (
                        <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-300" />
                      )}
                      <span>نتیجه واقعی انجام کار در برنامه</span>
                    </div>
                    {item.content.replace(/^نتیجه واقعی برنامه:\n?/, '')}
                  </article>
                );
              }

              const isUser = item.role === 'user';
              return (
                <article
                  key={index}
                  className={`max-w-[min(42rem,88%)] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-7 ${
                    isUser
                      ? 'self-start rounded-tr-sm border border-sky-400/40 bg-sky-500/14 text-foreground dark:border-sky-400/30 dark:bg-sky-500/20'
                      : 'glass-card self-end rounded-tl-sm text-foreground'
                  }`}
                >
                  <strong className="mb-1 block text-[11px] font-bold text-muted-foreground">
                    {isUser ? 'شما' : 'کارنامه'}
                  </strong>
                  {item.content || (state.busy && index === state.items.length - 1 ? 'در حال نگارش پاسخ…' : '')}
                </article>
              );
            })
          )}

          {awaitingClarification && (
            <div className="self-end rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-[11px] font-medium text-primary">
              پاسخ شما به این پرسش به عنوان تکمیل همین درخواست پردازش می‌شود
            </div>
          )}
        </div>
      </section>

      {/* Bottom Floating Minimal Composer Area (ai-chat-input.tsx centerpiece) */}
      <footer className="z-10 mx-auto w-full max-w-3xl px-4 pb-4 pt-1">
        {/* Contextual Plan Review / Schedule / Suggestions Row */}
        {(state.can_review || suggestions.length > 0 || (draft.trim() && !state.busy)) && (
          <div className="mb-2 flex flex-wrap items-center justify-center gap-2">
            {state.can_review && (
              <Button
                type="button"
                onClick={() => run('review')}
                className="h-8 gap-1.5 rounded-full bg-emerald-600 px-4 text-xs text-white shadow-sm hover:bg-emerald-700"
              >
                <CheckCircle2 className="size-3.5" />
                <span>بازبینی و اعمال تغییرات در برنامه</span>
              </Button>
            )}
            {draft.trim() && !state.busy && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={sending}
                onClick={schedule}
                className="glass-pill h-7 gap-1 rounded-full px-3 text-[11px]"
              >
                <Clock className="size-3" />
                <span>زمان‌بندی ارسال این درخواست</span>
              </Button>
            )}
            {suggestions.map((item) => (
              <button
                key={item.title}
                type="button"
                onClick={() => applyTemplate(item)}
                className="glass-pill rounded-full px-3 py-1 text-[11px] font-medium text-foreground transition hover:border-primary/45 hover:text-primary"
              >
                پیشنهاد: {item.title}
              </button>
            ))}
          </div>
        )}

        <PromptInput
          nativeMode
          disabled={!state.can_send || sending}
          isBusy={state.busy || state.can_stop}
          onStop={() => run('stop')}
          value={draft}
          onChange={setDraft}
          onSubmit={send}
          placeholder="از کارنامه بپرسید یا درخواست خود را بنویسید…"
          toolbar={
            <>
              <select
                aria-label="حالت دستیار"
                value={state.mode}
                disabled={state.busy}
                onChange={(e) => run('mode', { value: e.target.value })}
                className="h-7 rounded-full border border-border/60 bg-background/60 px-2.5 text-[11px] font-medium text-foreground outline-none"
              >
                {Object.entries(MODE_LABELS).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </select>

              {(state.templates || []).length > 0 && (
                <button
                  type="button"
                  onClick={() => setTemplatesOpen(true)}
                  className="inline-flex h-7 items-center gap-1 rounded-full px-2.5 text-[11px] font-medium text-muted-foreground transition hover:bg-accent/70 hover:text-foreground"
                >
                  <Plus className="size-3.5" />
                  <span>الگوهای آماده</span>
                </button>
              )}
            </>
          }
        />
      </footer>

      {/* Templates Modal */}
      {templatesOpen && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="الگوهای آماده دستیار" className="glass-modal max-h-[80vh] w-[min(32rem,92vw)] overflow-auto rounded-3xl p-5 space-y-2">
            <header className="mb-2 flex items-center justify-between">
              <strong className="text-sm font-bold">الگوهای آماده مطابق دسترسی شما</strong>
              <button aria-label="بستن" onClick={() => setTemplatesOpen(false)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            {(state.templates || []).map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => applyTemplate(t)}
                className="block w-full rounded-2xl border border-border/50 bg-background/50 p-3 text-right transition hover:border-primary/40 hover:bg-accent/50"
              >
                <div className="text-xs font-bold">{t.title}</div>
                <div className="mt-1 text-[11px] text-muted-foreground">{t.text}</div>
              </button>
            ))}
          </section>
        </div>
      )}

      {/* Request History Modal */}
      {historyModal && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="درخواست‌های اخیر" className="glass-modal max-h-[80vh] w-[min(34rem,92vw)] overflow-auto rounded-3xl p-5 space-y-3">
            <header className="flex items-center justify-between">
              <strong className="text-sm font-bold">درخواست‌های اخیر و نتیجه اجرا</strong>
              <button aria-label="بستن" onClick={() => setHistoryModal(null)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            {!historyModal.length && (
              <p className="py-6 text-center text-xs text-muted-foreground">هنوز درخواستی در حافظه این نشست ثبت نشده است.</p>
            )}
            {historyModal.map((item, idx) => (
              <div key={item.id || idx} className="rounded-2xl border border-border/60 bg-background/50 p-3 space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="rounded-full bg-primary/12 px-2.5 py-0.5 text-[10px] font-semibold text-primary">
                    {item.status_label}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setDraft(item.request);
                      setHistoryModal(null);
                    }}
                    className="text-[11px] font-semibold text-primary hover:underline"
                  >
                    قرار دادن در کادر
                  </button>
                </div>
                <div className="text-xs font-semibold">{item.request}</div>
                {item.detail && <p className="line-clamp-3 text-[11px] text-muted-foreground">{item.detail}</p>}
              </div>
            ))}
          </section>
        </div>
      )}

      {/* Scheduled Prompts Modal */}
      {scheduledModal && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/35 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" aria-label="درخواست‌های زمان‌بندی‌شده" className="glass-modal max-h-[80vh] w-[min(34rem,92vw)] overflow-auto rounded-3xl p-5 space-y-3">
            <header className="flex items-center justify-between">
              <strong className="text-sm font-bold">درخواست‌های زمان‌بندی‌شده</strong>
              <button aria-label="بستن" onClick={() => setScheduledModal(null)} className="rounded-lg p-1 hover:bg-accent">
                <X className="size-4" />
              </button>
            </header>
            {!scheduledModal.length && (
              <p className="py-6 text-center text-xs text-muted-foreground">درخواست زمان‌بندی‌شده‌ای در صف نیست.</p>
            )}
            {scheduledModal.map((item) => (
              <div key={item.id} className="rounded-2xl border border-border/60 bg-background/50 p-3 space-y-1.5">
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="font-semibold text-primary">{item.status_label}</span>
                  <span className="text-muted-foreground">{item.due_jalali}</span>
                </div>
                <p className="text-xs">{item.prompt}</p>
                {item.status !== 'running' && (
                  <div className="flex justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void cancelScheduledItem(item.id)}
                      className="h-7 rounded-xl text-[11px]"
                    >
                      لغو درخواست
                    </Button>
                  </div>
                )}
              </div>
            ))}
          </section>
        </div>
      )}

      {/* Clear Memory Confirmation */}
      {confirmClearMem && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 backdrop-blur-xs">
          <section role="dialog" aria-modal="true" className="glass-modal w-[min(24rem,90vw)] rounded-3xl p-5 space-y-4">
            <h3 className="text-sm font-bold">پاک کردن حافظه شخصی</h3>
            <p className="text-xs leading-6 text-muted-foreground">
              تمام سوابق گفتگوی رمزگذاری‌شده دستیار روی این رایانه پاک می‌شود. ادامه می‌دهید؟
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setConfirmClearMem(false)}>انصراف</Button>
              <Button
                variant="destructive"
                onClick={() => {
                  setConfirmClearMem(false);
                  run('clear_memory');
                }}
              >
                پاک کردن حافظه
              </Button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
