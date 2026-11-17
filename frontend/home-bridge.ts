import { connectAppearance } from './appearance';

type Callback = (id: string, raw: string) => void;
type ChangedCallback = (raw: string) => void;

type NativeHome = {
  changed: { connect: (cb: ChangedCallback) => void };
  completed: { connect: (cb: Callback) => void };
  request: (id: string, action: string, raw: string) => void;
};

type HomeQWebChannel = new (
  transport: unknown,
  cb: (channel: { objects: { home?: NativeHome; appearance?: unknown } }) => void
) => void;

export type HomeWeatherHour = {
  time: string;
  temp: string;
  kind: string;
  label: string;
};

export type HomeWeatherDay = {
  name: string;
  date_fa: string;
  min: string;
  max: string;
  kind: string;
  label: string;
};

export type HomeWeather = {
  enabled: boolean;
  busy?: boolean;
  error?: string;
  cached?: boolean;
  has_data?: boolean;
  estimated?: boolean;
  show_hourly?: boolean;
  show_weekly?: boolean;
  location?: string;
  caption?: string;
  station?: string;
  last_checked?: string;
  current?: {
    temp: string;
    kind: string;
    label: string;
    humidity: string | null;
    wind: string | null;
  };
  hours?: HomeWeatherHour[];
  days?: HomeWeatherDay[];
  comparison?: {
    busy: boolean;
    error: string;
    data: { model: number; observation: number; difference: number } | null;
  };
};

export type HomeState = {
  user: { fullname: string; first_name?: string; username: string };
  greeting?: {
    period: 'morning' | 'noon' | 'evening' | 'night';
    first_name: string;
    salutation: string;
    subtitle: string;
    badge: string;
  };
  home_prefs?: {
    cards: string[];
    columns: 'auto' | 2 | 3;
    density: 'compact' | 'comfortable' | 'spacious';
  };
  today: { jalali: string; gregorian: string; weekday: string };
  mini_calendar?: {title:string;offset:number;days:{day:number;label:string;date:string;today:boolean;holiday:boolean;has_events:boolean}[]} | null;
  permissions: {
    calendar: boolean;
    calendar_create: boolean;
    workspace: boolean;
    assistant?: boolean;
    settings: boolean;
    settings_edit: boolean;
  };
  briefing?: {
    summary: string;
    ai_powered?: boolean;
    bullets: { type: string; title: string; detail: string; module?: string }[];
  };
  reminders: { title: string; company: string; priority: string; done: boolean }[];
  reminders_total: number;
  reminders_total_fa: string;
  occasions: { title: string; holiday: boolean; source: string }[];
  activity: {
    allowed: boolean;
    overdue: number;
    overdue_fa?: string;
    review: number;
    review_fa?: string;
    requests: number;
    requests_fa?: string;
    total: number;
    total_fa?: string;
    next_meeting: string;
  };
  weather: HomeWeather;
  quote: {
    enabled: boolean;
    text?: string;
    author?: string;
    work?: string;
    section?: string;
    has_source?: boolean;
  };
  modules: { key: string; title: string; desc: string }[];
  bento_modules?: { key: string; title: string; desc: string }[];
  theme: string;
  theme_preset?: string;
  home_skin?: string;
};

let connection: Promise<NativeHome> | undefined;
const listeners = new Set<(state: HomeState) => void>();
const pending = new Map<string, { resolve: (v: unknown) => void; reject: (e: Error) => void; timer: number }>();
let hooked = false;
let lastState: HomeState | null = null;

function nativeHome(): Promise<NativeHome> {
  if (!connection) {
    connection = new Promise((resolve, reject) => {
      if (!window.qt || !window.QWebChannel) {
        reject(new Error('صفحه خانه به برنامه متصل نیست.'));
        return;
      }
      const QWC = window.QWebChannel as unknown as HomeQWebChannel;
      new QWC(window.qt.webChannelTransport, (channel) => {
        connectAppearance(channel.objects.appearance as never);
        const home = channel.objects.home;
        if (!home) {
          reject(new Error('رابط خانه در دسترس نیست.'));
          return;
        }
        if (!hooked) {
          hooked = true;
          home.changed.connect((raw) => {
            try {
              const state = JSON.parse(raw) as HomeState;
              lastState = state;
              listeners.forEach((fn) => fn(state));
            } catch {
              /* ignore malformed snapshots */
            }
          });
          home.completed.connect((id, raw) => {
            const task = pending.get(id);
            if (!task) return;
            pending.delete(id);
            window.clearTimeout(task.timer);
            try {
              const res = JSON.parse(raw);
              res.ok ? task.resolve(res.value) : task.reject(new Error(res.error || 'خطای ارتباط'));
            } catch {
              task.reject(new Error('پاسخ نامعتبر است.'));
            }
          });
        }
        resolve(home);
      });
    });
  }
  return connection;
}

export async function homeRequest<T = void>(action: string, args: Record<string, unknown> = {}): Promise<T> {
  const bridge = await nativeHome();
  const id = crypto.randomUUID();
  return new Promise<T>((resolve, reject) => {
    const timer = window.setTimeout(() => {
      pending.delete(id);
      reject(new Error('زمان پاسخ به پایان رسید.'));
    }, 15000);
    pending.set(id, { resolve: (v) => resolve(v as T), reject, timer });
    bridge.request(id, action, JSON.stringify(args));
  });
}

export function onHomeState(listener: (state: HomeState) => void): () => void {
  listeners.add(listener);
  if (lastState) listener(lastState);
  void nativeHome()
    .then(() => homeRequest('refresh'))
    .catch(() => {});
  return () => {
    listeners.delete(listener);
  };
}
