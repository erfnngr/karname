import { connectAppearance } from './appearance';

type Callback = (id: string, raw: string) => void;
type ChangedCallback = (raw: string) => void;

type NativeCalendar = {
  changed: { connect: (cb: ChangedCallback) => void };
  completed: { connect: (cb: Callback) => void };
  request: (id: string, action: string, raw: string) => void;
};

type CalendarQWebChannel = new (
  transport: unknown,
  cb: (channel: { objects: { calendar?: NativeCalendar; appearance?: unknown } }) => void
) => void;

export type CalendarOccasion = {
  title: string;
  holiday: boolean;
  source: string;
};

export type CalendarDayCell = {
  day: number;
  day_fa: string;
  date_jalali: string;
  date_gregorian: string;
  greg_label: string;
  in_month: boolean;
  is_today: boolean;
  is_selected: boolean;
  is_holiday: boolean;
  weekday_idx: number;
  occasions: CalendarOccasion[];
};

export type CalendarEventItem = {
  id: string;
  title: string;
  notes: string;
  company: string;
  category: string;
  color: 'sky' | 'emerald' | 'amber' | 'rose' | 'indigo' | 'teal';
  priority: string;
  recurrence: string;
  date_jalali: string;
  date_gregorian: string;
  done: boolean;
  needs_review: boolean;
  source_kind: 'personal' | 'shared' | 'desk_note' | 'birthday';
  editable: boolean;
  tags: string[];
  start_hour?: string;
  end_hour?: string;
};

export type CalendarState = {
  title: string;
  today: { year: number; month: number; day: number; jalali: string; gregorian: string };
  view: {
    year: number;
    month: number;
    year_fa: string;
    month_name: string;
    greg_range: string;
    selected_jalali: string;
    selected_fa: string;
    selected_gregorian: string;
    selected_occasions: CalendarOccasion[];
  };
  weekdays: string[];
  months: string[];
  days: CalendarDayCell[];
  events: CalendarEventItem[];
  companies: string[];
  preferences: { show_gregorian: boolean; show_occasions: boolean; show_tasks: boolean };
  permissions: { create: boolean; edit: boolean; delete: boolean; export: boolean };
  theme: string;
  theme_preset: string;
};

let connection: Promise<NativeCalendar> | undefined;
const listeners = new Set<(state: CalendarState) => void>();
const pending = new Map<string, { resolve: (v: unknown) => void; reject: (e: Error) => void; timer: number }>();
let hooked = false;
let lastState: CalendarState | null = null;

function nativeCalendar(): Promise<NativeCalendar> {
  if (!connection) {
    connection = new Promise((resolve, reject) => {
      if (!window.qt || !window.QWebChannel) {
        reject(new Error('تقویم به برنامه متصل نیست.'));
        return;
      }
      const QWC = window.QWebChannel as unknown as CalendarQWebChannel;
      new QWC(window.qt.webChannelTransport, (channel) => {
        connectAppearance(channel.objects.appearance as never);
        const cal = channel.objects.calendar;
        if (!cal) {
          reject(new Error('رابط تقویم در دسترس نیست.'));
          return;
        }
        if (!hooked) {
          hooked = true;
          cal.changed.connect((raw) => {
            try {
              const state = JSON.parse(raw) as CalendarState;
              lastState = state;
              listeners.forEach((fn) => fn(state));
            } catch {
              /* ignore malformed snapshots */
            }
          });
          cal.completed.connect((id, raw) => {
            const task = pending.get(id);
            if (!task) return;
            pending.delete(id);
            window.clearTimeout(task.timer);
            try {
              const res = JSON.parse(raw);
              res.ok ? task.resolve(res.value) : task.reject(new Error(res.error || 'خطای تقویم'));
            } catch {
              task.reject(new Error('پاسخ تقویم نامعتبر است.'));
            }
          });
        }
        resolve(cal);
      });
    });
  }
  return connection;
}

export async function calendarRequest<T = void>(
  action: string,
  args: Record<string, unknown> = {}
): Promise<T> {
  const bridge = await nativeCalendar();
  const id = crypto.randomUUID();
  return new Promise<T>((resolve, reject) => {
    const timer = window.setTimeout(() => {
      pending.delete(id);
      reject(new Error('زمان پاسخ تقویم به پایان رسید.'));
    }, 15000);
    pending.set(id, { resolve: (v) => resolve(v as T), reject, timer });
    bridge.request(id, action, JSON.stringify(args));
  });
}

export function onCalendarState(listener: (state: CalendarState) => void): () => void {
  listeners.add(listener);
  if (lastState) listener(lastState);
  void nativeCalendar()
    .then(() => calendarRequest('refresh'))
    .catch(() => {});
  return () => {
    listeners.delete(listener);
  };
}
