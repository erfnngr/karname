import { connectAppearance } from './appearance';

type Callback = (requestId: string, body: string) => void;
type TargetCallback = (body: string) => void;
type NativeBridge = {
  completed: { connect: (cb: Callback) => void };
  target_opened?: { connect: (cb: TargetCallback) => void };
  request: (id: string, action: string, body: string) => void;
};

declare global {
  interface Window {
    qt?: { webChannelTransport: unknown };
    QWebChannel?: new (
      transport: unknown,
      cb: (channel: { objects: { chat: NativeBridge; appearance?: unknown } }) => void
    ) => void;
  }
}

export type ChatTarget = {
  company: string;
  room: string;
  thread?: string | null;
  message_id?: string | null;
};

let connection: Promise<NativeBridge> | undefined;
const targetListeners = new Set<(target: ChatTarget) => void>();
let targetHooked = false;

export function nativeChat(): Promise<NativeBridge> {
  if (!connection) {
    connection = new Promise((resolve, reject) => {
      if (!window.qt || !window.QWebChannel) {
        reject(new Error('صفحه به برنامه متصل نیست.'));
        return;
      }
      new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
        connectAppearance(channel.objects.appearance as never);
        const chat = channel.objects.chat;
        if (!targetHooked && chat?.target_opened) {
          targetHooked = true;
          chat.target_opened.connect((raw) => {
            try {
              const target = JSON.parse(raw) as ChatTarget;
              targetListeners.forEach((fn) => fn(target));
            } catch {
              /* Ignore malformed target payloads */
            }
          });
        }
        resolve(chat);
      });
    });
  }
  return connection;
}

export function onChatTarget(listener: (target: ChatTarget) => void): () => void {
  targetListeners.add(listener);
  void nativeChat()
    .then(() => request<ChatTarget | null>('last_target'))
    .then((target) => {
      if (target && target.company && target.room) listener(target);
    })
    .catch(() => {});
  return () => {
    targetListeners.delete(listener);
  };
}

const pending = new Map<string, { resolve: (value: unknown) => void; reject: (error: Error) => void; timer: number }>();
let initialized = false;

export async function request<T>(action: string, args: Record<string, unknown> = {}): Promise<T> {
  const bridge = await nativeChat();
  if (!initialized) {
    bridge.completed.connect((id, raw) => {
      const task = pending.get(id);
      if (!task) return;
      pending.delete(id);
      window.clearTimeout(task.timer);
      try {
        const value = JSON.parse(raw);
        value.ok ? task.resolve(value.value) : task.reject(new Error(value.error || 'خطای ارتباط'));
      } catch {
        task.reject(new Error('پاسخ نامعتبر است.'));
      }
    });
    initialized = true;
  }
  const id = crypto.randomUUID();
  return new Promise<T>((resolve, reject) => {
    const interactive = ['choose_schedule', 'choose_poll', 'choose_meeting', 'native_reminder', 'native_task'].includes(action);
    const timer = window.setTimeout(
      () => {
        pending.delete(id);
        reject(new Error('زمان پاسخ پایان یافت؛ پیش از تلاش دوباره وضعیت عملیات را بررسی کنید.'));
      },
      interactive ? 1800000 : 60000
    );
    pending.set(id, { resolve: (value) => resolve(value as T), reject, timer });
    bridge.request(id, action, JSON.stringify(args));
  });
}
