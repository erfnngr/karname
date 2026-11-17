import { HomeMiniCalendar } from './HomeMiniCalendar';
import React, { useState } from 'react';
import {
  Bot,
  Briefcase,
  Building2,
  Cake,
  Calendar,
  CheckCircle2,
  Clock,
  Droplets,
  FileSpreadsheet,
  FolderKanban,
  Globe,
  Landmark,
  MessageSquare,
  Quote,
  RefreshCw,
  Sparkles,
  Wind,
} from 'lucide-react';
import { HomeState } from './home-bridge';

export type SkinId = 'classic' | 'command_bento';

export const SKIN_OPTIONS: { id: SkinId; label: string }[] = [
  { id: 'classic', label: 'استاندارد' },
  { id: 'command_bento', label: 'بنتو گرید' },
];

export type SkinProps = {
  state: HomeState;
  dark: boolean;
  skin: SkinId;
  onSelectSkin: (skin: SkinId) => void;
  onToggleDark: () => void;
  act: (action: string, args?: Record<string, unknown>) => void;
  onOpenWeatherDetails: () => void;
};

/** Harmonized ocean backdrop wash per theme preset so ocean.png + karname logo shine through cleanly. */
export function themeWashStyle(themePreset: string | undefined, dark: boolean): string {
  const key = themePreset || 'default';
  if (dark) {
    if (key === 'emerald_ivory') return 'linear-gradient(155deg, rgba(8, 28, 22, 0.42), rgba(14, 42, 33, 0.34))';
    if (key === 'glass_mist') return 'linear-gradient(155deg, rgba(10, 22, 36, 0.34), rgba(19, 38, 59, 0.28))';
    if (key === 'violet_modular') return 'linear-gradient(155deg, rgba(17, 22, 38, 0.42), rgba(26, 33, 56, 0.34))';
    if (key === 'bento_grid') return 'linear-gradient(155deg, rgba(10, 28, 40, 0.34), rgba(14, 40, 48, 0.28))';
    return 'linear-gradient(155deg, rgba(14, 24, 38, 0.36), rgba(20, 34, 52, 0.28))';
  }
  if (key === 'emerald_ivory') return 'linear-gradient(155deg, rgba(246, 244, 236, 0.26), rgba(226, 239, 232, 0.16))';
  if (key === 'glass_mist') return 'linear-gradient(155deg, rgba(233, 241, 250, 0.16), rgba(223, 239, 252, 0.10))';
  if (key === 'violet_modular') return 'linear-gradient(155deg, rgba(238, 241, 247, 0.22), rgba(224, 230, 246, 0.14))';
  if (key === 'bento_grid') return 'linear-gradient(155deg, rgba(234, 246, 250, 0.16), rgba(223, 245, 240, 0.12))';
  return 'linear-gradient(155deg, rgba(243, 247, 251, 0.20), rgba(232, 243, 250, 0.12))';
}

export function WeatherGlyph({ kind, className = 'w-5 h-5' }: { kind: string; className?: string }) {
  switch (kind) {
    case 'sun':
      return (
        <svg viewBox="0 0 24 24" className={className} fill="none" aria-hidden="true">
          <g className="wx-sun-spin" stroke="#f59e0b" strokeWidth="2" strokeLinecap="round">
            <line x1="12" y1="2.2" x2="12" y2="4.4" />
            <line x1="12" y1="19.6" x2="12" y2="21.8" />
            <line x1="2.2" y1="12" x2="4.4" y2="12" />
            <line x1="19.6" y1="12" x2="21.8" y2="12" />
            <line x1="5.1" y1="5.1" x2="6.6" y2="6.6" />
            <line x1="17.4" y1="17.4" x2="18.9" y2="18.9" />
            <line x1="18.9" y1="5.1" x2="17.4" y2="6.6" />
            <line x1="6.6" y1="17.4" x2="5.1" y2="18.9" />
          </g>
          <circle cx="12" cy="12" r="4.6" fill="#fbbf24" stroke="#f59e0b" strokeWidth="1.4" />
        </svg>
      );
    case 'cloud-sun':
      return (
        <svg viewBox="0 0 24 24" className={className} fill="none" aria-hidden="true">
          <g className="wx-sun-spin" style={{ transformOrigin: '9px 8px' }} stroke="#f59e0b" strokeWidth="1.6" strokeLinecap="round">
            <line x1="9" y1="2.2" x2="9" y2="3.7" />
            <line x1="3.2" y1="8" x2="4.7" y2="8" />
            <line x1="4.9" y1="3.9" x2="6" y2="5" />
            <line x1="13.1" y1="3.9" x2="12" y2="5" />
          </g>
          <circle cx="9" cy="8.2" r="3.4" fill="#fbbf24" />
          <path
            className="wx-cloud-drift"
            d="M7.5 18.5h9.2a3.3 3.3 0 0 0 .4-6.58A4.6 4.6 0 0 0 8.3 10.6a3.9 3.9 0 0 0-.8 7.9Z"
            fill="#e2e8f0"
            stroke="#94a3b8"
            strokeWidth="1.4"
          />
        </svg>
      );
    case 'moon':
      return (
        <svg viewBox="0 0 24 24" className={className} fill="none" aria-hidden="true">
          <path
            d="M16.8 14.8A6.5 6.5 0 0 1 9.2 7.2a6.6 6.6 0 1 0 7.6 7.6Z"
            fill="#38bdf8"
            stroke="#0ea5e9"
            strokeWidth="1.4"
            strokeLinejoin="round"
          />
          <circle className="wx-star-1" cx="17.5" cy="6.2" r="1.15" fill="#fde047" />
          <circle className="wx-star-2" cx="20" cy="10.2" r="0.85" fill="#7dd3fc" />
        </svg>
      );
    case 'cloud-moon':
      return (
        <svg viewBox="0 0 24 24" className={className} fill="none" aria-hidden="true">
          <path
            d="M12.2 10.8a4.2 4.2 0 0 1-4.8-4.8 4.4 4.4 0 1 0 4.8 4.8Z"
            fill="#38bdf8"
            stroke="#0284c7"
            strokeWidth="1.2"
          />
          <circle className="wx-star-1" cx="15.5" cy="5.5" r="0.95" fill="#fde047" />
          <path
            className="wx-cloud-drift"
            d="M7.5 18.5h9.2a3.3 3.3 0 0 0 .4-6.58A4.6 4.6 0 0 0 8.3 10.6a3.9 3.9 0 0 0-.8 7.9Z"
            fill="#cbd5e1"
            stroke="#64748b"
            strokeWidth="1.4"
          />
        </svg>
      );
    case 'cloud-rain':
      return (
        <svg viewBox="0 0 24 24" className={className} fill="none" aria-hidden="true">
          <path
            className="wx-cloud-drift"
            d="M6.8 15.2h10.1a3.4 3.4 0 0 0 .4-6.77A4.9 4.9 0 0 0 8.1 7.2a4 4 0 0 0-1.3 8Z"
            fill="#cbd5e1"
            stroke="#64748b"
            strokeWidth="1.4"
          />
          <line className="wx-rain-1" x1="8.5" y1="16.4" x2="7.2" y2="20.2" stroke="#0ea5e9" strokeWidth="1.8" strokeLinecap="round" />
          <line className="wx-rain-2" x1="12.5" y1="16.4" x2="11.2" y2="20.4" stroke="#0284c7" strokeWidth="1.8" strokeLinecap="round" />
          <line className="wx-rain-1" x1="16.3" y1="16.4" x2="15" y2="20.2" stroke="#38bdf8" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      );
    case 'cloud-snow':
      return (
        <svg viewBox="0 0 24 24" className={className} fill="none" aria-hidden="true">
          <path
            className="wx-cloud-drift"
            d="M6.8 14.8h10.1a3.4 3.4 0 0 0 .4-6.77A4.9 4.9 0 0 0 8.1 6.8a4 4 0 0 0-1.3 8Z"
            fill="#e2e8f0"
            stroke="#64748b"
            strokeWidth="1.4"
          />
          <circle className="wx-snow-1" cx="8.6" cy="18" r="1.25" fill="#38bdf8" />
          <circle className="wx-snow-2" cx="12.3" cy="19.3" r="1.35" fill="#7dd3fc" />
          <circle className="wx-snow-1" cx="16.1" cy="18" r="1.25" fill="#38bdf8" />
        </svg>
      );
    case 'cloud-lightning':
      return (
        <svg viewBox="0 0 24 24" className={className} fill="none" aria-hidden="true">
          <path
            className="wx-cloud-drift"
            d="M6.8 14.6h10.1a3.4 3.4 0 0 0 .4-6.77A4.9 4.9 0 0 0 8.1 6.6a4 4 0 0 0-1.3 8Z"
            fill="#cbd5e1"
            stroke="#64748b"
            strokeWidth="1.4"
          />
          <polyline
            className="wx-bolt"
            points="12.8 14.4 10.6 18 13.2 18 11.4 21.8"
            stroke="#f59e0b"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case 'cloud-fog':
      return (
        <svg viewBox="0 0 24 24" className={className} fill="none" aria-hidden="true">
          <path
            className="wx-cloud-drift"
            d="M6.8 13.6h10.1a3.3 3.3 0 0 0 .4-6.57A4.8 4.8 0 0 0 8.2 5.9a3.9 3.9 0 0 0-1.4 7.7Z"
            fill="#cbd5e1"
            stroke="#64748b"
            strokeWidth="1.4"
          />
          <line className="wx-fog-bar" x1="5" y1="16.8" x2="19" y2="16.8" stroke="#94a3b8" strokeWidth="1.8" strokeLinecap="round" />
          <line className="wx-fog-bar" x1="7" y1="19.8" x2="17" y2="19.8" stroke="#94a3b8" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      );
    default:
      return (
        <svg viewBox="0 0 24 24" className={className} fill="none" aria-hidden="true">
          <path
            className="wx-cloud-drift"
            d="M6.5 17.5h10.8a3.6 3.6 0 0 0 .4-7.17A5.2 5.2 0 0 0 8 9a4.2 4.2 0 0 0-1.5 8.5Z"
            fill="#cbd5e1"
            stroke="#64748b"
            strokeWidth="1.5"
          />
        </svg>
      );
  }
}

export function ModuleIcon({ moduleKey, className = 'w-4 h-4' }: { moduleKey: string; className?: string }) {
  switch (moduleKey) {
    case 'chat':
      return <MessageSquare className={className} />;
    case 'assistant':
      return <Bot className={className} />;
    case 'tax':
      return <Landmark className={className} />;
    case 'workspace':
      return <FolderKanban className={className} />;
    case 'calendar':
      return <Calendar className={className} />;
    case 'clients':
      return <FileSpreadsheet className={className} />;
    case 'desk':
      return <Briefcase className={className} />;
    case 'company':
      return <Building2 className={className} />;
    case 'attendance':
      return <Clock className={className} />;
    default:
      return <Globe className={className} />;
  }
}

/** Soft calming sky-blue and mint-green module tints (no harsh purple). */
function bentoModuleTint(idx: number): { chip: string; badge: string } {
  const alternatingBlue = idx % 2 === 0;
  return alternatingBlue
    ? {
        chip: 'bg-sky-500/12 text-sky-600 dark:text-sky-300 border-sky-400/30',
        badge: 'text-sky-600/80 dark:text-sky-300/80',
      }
    : {
        chip: 'bg-emerald-500/12 text-emerald-600 dark:text-emerald-300 border-emerald-400/30',
        badge: 'text-emerald-600/80 dark:text-emerald-300/80',
      };
}

/**
 * Bento Grid Home Layout:
 * Soft Sky-Blue & Mint-Green palette over ocean + Karname backdrop, 6 customizable Quick Access tiles.
 */

export function WeatherForecastCompact({
  state,
  act,
  onOpenWeatherDetails,
  interactiveToggle = false,
}: {
  state: HomeState;
  act: SkinProps['act'];
  onOpenWeatherDetails: () => void;
  interactiveToggle?: boolean;
}) {
  const [tab, setTab] = useState<'hourly' | 'weekly'>('hourly');
  const w = state.weather;
  const hourlyAvailable = !!w.show_hourly && !!w.hours?.length;
  const weeklyAvailable = !!w.show_weekly && !!w.days?.length;
  const activeTab = tab === 'hourly' && !hourlyAvailable && weeklyAvailable ? 'weekly' : tab === 'weekly' && !weeklyAvailable && hourlyAvailable ? 'hourly' : tab;
  if (!w.enabled) return null;

  return (
    <div className="flex flex-col gap-3 min-w-0">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="font-bold text-sm leading-6 truncate">آب‌وهوای {w.location || 'تهران'}</h2>
          <p className="text-[11px] leading-5 text-[var(--color-muted-foreground)] mt-0.5 truncate">
            {w.caption || (w.busy ? 'در حال دریافت…' : w.error || 'به‌روزرسانی خودکار')}
          </p>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            type="button"
            onClick={() => act('refresh_weather')}
            title="به‌روزرسانی آب‌وهوا"
            className="p-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-card)] hover:bg-[var(--color-accent)] cursor-pointer transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${w.busy ? 'animate-spin' : ''}`} />
          </button>
          {w.has_data && (
            <button
              type="button"
              onClick={onOpenWeatherDetails}
              className="px-2.5 py-1 rounded-full bg-sky-500/14 text-sky-700 dark:text-sky-300 hover:bg-sky-500/22 text-xs font-semibold cursor-pointer transition"
            >
              جزئیات
            </button>
          )}
        </div>
      </div>

      {!w.has_data ? (
        <div className="py-6 text-center text-xs text-[var(--color-muted-foreground)]">
          {w.busy ? 'در حال دریافت اطلاعات آب‌وهوا…' : w.error || 'اطلاعات آب‌وهوا هنوز دریافت نشده است.'}
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-12 h-12 rounded-2xl bg-[var(--color-background)] border border-[var(--color-border)] flex items-center justify-center shrink-0">
                <WeatherGlyph kind={w.current?.kind || 'cloud'} className="w-7 h-7" />
              </div>
              <div className="min-w-0">
                <div className="text-3xl font-extrabold leading-none">{w.current?.temp}°</div>
                <div className="text-xs leading-5 text-[var(--color-muted-foreground)] mt-1 truncate">
                  {w.current?.label}
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-1 text-[11px] leading-5 text-[var(--color-muted-foreground)] shrink-0">
              {w.current?.humidity != null && (
                <span className="inline-flex items-center gap-1">
                  <Droplets className="w-3 h-3 text-sky-500" />
                  رطوبت {w.current.humidity}٪
                </span>
              )}
              {w.current?.wind != null && (
                <span className="inline-flex items-center gap-1">
                  <Wind className="w-3 h-3 text-emerald-500" />
                  باد {w.current.wind} کیلومتر
                </span>
              )}
            </div>
          </div>

          {interactiveToggle && (hourlyAvailable || weeklyAvailable) ? (
            <div className="flex flex-col gap-2">
              <div className="inline-flex self-start rounded-full bg-[var(--color-background)] border border-[var(--color-border)] p-0.5 text-[11px]">
                <button
                  type="button"
                  onClick={() => setTab('hourly')}
                  disabled={!hourlyAvailable}
                  className={`px-3 py-1 rounded-full cursor-pointer transition font-semibold disabled:opacity-40 disabled:cursor-not-allowed ${
                    activeTab === 'hourly'
                      ? 'bg-sky-500 text-white'
                      : 'text-[var(--color-muted-foreground)]'
                  }`}
                >
                  ساعتی
                </button>
                <button
                  type="button"
                  onClick={() => setTab('weekly')}
                  disabled={!weeklyAvailable}
                  className={`px-3 py-1 rounded-full cursor-pointer transition font-semibold disabled:opacity-40 disabled:cursor-not-allowed ${
                    activeTab === 'weekly'
                      ? 'bg-emerald-500 text-white'
                      : 'text-[var(--color-muted-foreground)]'
                  }`}
                >
                  هفتگی
                </button>
              </div>
              {activeTab === 'hourly' && w.show_hourly && (w.hours?.length ?? 0) > 0 && (
                <div className="flex gap-1.5 overflow-x-auto pb-1">
                  {w.hours!.slice(0, 10).map((h, idx) => (
                    <div
                      key={`${h.time}-${idx}`}
                      className="shrink-0 w-14 rounded-2xl border border-[var(--color-border)] bg-[var(--color-background)] px-1.5 py-2 flex flex-col items-center gap-1 text-[11px]"
                    >
                      <span className="text-[10px] text-[var(--color-muted-foreground)]">{h.time}</span>
                      <WeatherGlyph kind={h.kind} className="w-4 h-4" />
                      <span className="font-bold">{h.temp}°</span>
                    </div>
                  ))}
                </div>
              )}
              {activeTab === 'weekly' && w.show_weekly && (w.days?.length ?? 0) > 0 && (
                <div className="flex flex-col gap-1">
                  {w.days!.slice(0, 4).map((d, idx) => (
                    <div
                      key={`${d.name}-${idx}`}
                      className="flex items-center justify-between rounded-xl bg-[var(--color-background)] border border-[var(--color-border)] px-3 py-1.5 text-xs"
                    >
                      <span className="font-medium w-20 truncate">{d.name}</span>
                      <WeatherGlyph kind={d.kind} className="w-4 h-4" />
                      <span className="text-[11px] font-semibold">
                        {d.max}° / {d.min}°
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <>
              {w.show_hourly && (w.hours?.length ?? 0) > 0 && (
                <div>
                  <div className="text-[11px] leading-5 text-[var(--color-muted-foreground)] mb-1.5">
                    {w.estimated ? 'ساعت‌های آینده · تخمینی' : 'ساعت‌های آینده'}
                  </div>
                  <div className="flex gap-1.5 overflow-x-auto pb-1">
                    {w.hours!.slice(0, 10).map((h, idx) => (
                      <div
                        key={`${h.time}-${idx}`}
                        className="shrink-0 w-14 rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-1.5 py-1.5 flex flex-col items-center gap-1 text-[11px]"
                      >
                        <span className="text-[10px] text-[var(--color-muted-foreground)]">{h.time}</span>
                        <WeatherGlyph kind={h.kind} className="w-4 h-4" />
                        <span className="font-bold">{h.temp}°</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {w.show_weekly && (w.days?.length ?? 0) > 0 && (
                <div className="flex flex-col gap-1.5">
                  {w.days!.slice(0, 5).map((d, idx) => (
                    <div
                      key={`${d.name}-${idx}`}
                      className="flex items-center justify-between rounded-lg bg-[var(--color-background)] border border-[var(--color-border)] px-2.5 py-1.5 text-xs"
                    >
                      <span className="font-medium w-20 truncate">{d.name}</span>
                      <WeatherGlyph kind={d.kind} className="w-4 h-4" />
                      <span className="text-[11px] text-[var(--color-muted-foreground)]">
                        {d.max}° / {d.min}°
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

/** Compact, simple top-right user welcome line without extra text boxes or time-of-day clutter. */
export function SeaWelcomeHero({ state }: { state: HomeState; dark?: boolean }) {
  const firstName = state.user.first_name || state.user.fullname || 'کاربر';

  return (
    <div className="sea-welcome-hero w-full max-w-[1840px] mx-auto flex items-center justify-between gap-2 pb-1 shrink-0">
      <div className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--glass-bg)] backdrop-blur-md px-3.5 py-1 shadow-sm">
        <span className="text-[13px] font-bold text-[var(--color-foreground)]">
          خوش آمدید، {firstName} عزیز
        </span>
      </div>

      <div className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--glass-bg)] backdrop-blur-md px-3 py-1 text-[11px] font-bold text-[var(--color-foreground)] shadow-sm shrink-0">
        <Calendar className="w-3.5 h-3.5 text-[var(--color-primary)]" />
        <span>
          {state.today.weekday} · {state.today.jalali}
        </span>
      </div>
    </div>
  );
}

/** Concise automatic written AI Daily Briefing card without shortcuts or interactive distraction. */
export function AiDailyBriefingCard({
  state,
  cardClass = '',
  cardStyle,
}: {
  state: HomeState;
  act?: SkinProps['act'];
  cardClass?: string;
  cardStyle?: React.CSSProperties;
}) {
  const briefing = state.briefing;
  const bullets = briefing?.bullets || [];

  const bulletIcon = (type: string) => {
    switch (type) {
      case 'weather':
        return <WeatherGlyph kind={state.weather.current?.kind || 'cloud'} className="w-4 h-4 shrink-0" />;
      case 'birthday':
        return <Cake className="w-4 h-4 text-rose-500 shrink-0" />;
      case 'work':
        return <FolderKanban className="w-4 h-4 text-sky-600 dark:text-sky-300 shrink-0" />;
      case 'occasion':
        return <Calendar className="w-4 h-4 text-teal-600 dark:text-teal-300 shrink-0" />;
      default:
        return <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-300 shrink-0" />;
    }
  };

  return (
    <section
      data-ai-briefing="true"
      aria-label="خلاصه هوشمند امروز"
      className={`rounded-2xl border bg-[var(--glass-bg)] text-[var(--color-foreground)] p-3.5 flex flex-col gap-2.5 overflow-y-auto backdrop-blur-lg transition-colors duration-150 min-w-0 min-h-0 ${cardClass}`}
      style={cardStyle}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-xl bg-[var(--color-primary)]/14 text-[var(--color-primary)] flex items-center justify-center shrink-0">
            <Bot className="w-4 h-4" />
          </div>
          <h2 className="text-xs sm:text-sm font-extrabold leading-5 truncate">خلاصه هوشمند وضعیت امروز</h2>
        </div>
        <span className="px-2 py-0.5 rounded-full bg-[var(--color-primary)]/10 text-[var(--color-primary)] border border-[var(--color-primary)]/20 text-[10px] font-bold inline-flex items-center gap-1 shrink-0">
          <Sparkles className="w-3 h-3" />
          <span>{briefing?.ai_powered ? 'نگارش با هوش مصنوعی' : 'تحلیل خودکار کارنامه'}</span>
        </span>
      </div>

      <p className="text-xs leading-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-background)]/80 px-3 py-2 text-[var(--color-foreground)]">
        {briefing?.summary || `امروز ${state.today.weekday} ${state.today.jalali} است و برنامه کاری شما آماده است.`}
      </p>

      {bullets.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {bullets.map((b, idx) => (
            <div
              key={`${b.type}-${idx}`}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)]/85 px-2.5 py-1.5 text-right flex items-start gap-2 min-w-0"
            >
              <span className="mt-0.5">{bulletIcon(b.type)}</span>
              <div className="min-w-0 flex-1">
                <div className="text-[11px] font-bold truncate">{b.title}</div>
                <div className="text-[10px] text-[var(--color-muted-foreground)] leading-4 break-words">
                  {b.detail}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/**
 * Bento Grid Home Layout:
 * Soft Sky-Blue & Mint-Green frosted-glass palette over ocean + Karname backdrop, zero vertical scroll.
 */
export function CommandBentoLayout({
  state,
  dark,
  act,
  onOpenWeatherDetails,
}: SkinProps) {
  const cards = new Set(state.home_prefs?.cards ?? ['briefing', 'weather', 'today_reminders', 'activity_stats', 'quote']);
  const density = state.home_prefs?.density ?? 'comfortable';
  const pad = density === 'compact' ? 'p-2.5' : density === 'spacious' ? 'p-3.5' : 'p-3';
  const bentoModules = (state.bento_modules || state.modules || []).slice(0, 6);

  return (
    <div
      data-bento-grid="true"
      className="w-full max-w-[1840px] mx-auto flex-1 min-h-0 flex flex-col gap-2.5 bento-stage text-[var(--color-foreground)] rounded-3xl"
    >
      <SeaWelcomeHero state={state} dark={dark} />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-stretch flex-1 min-h-0">
        {/* Right/Main 8 Cols in RTL: Activity Stats + 6 Customizable Bento Tiles + AI Briefing + Reminders */}
        <div className="lg:col-span-8 flex flex-col justify-between gap-2.5 min-w-0 min-h-0">
          {cards.has('activity_stats') && (
            <div className={`rounded-2xl bento-card border border-sky-200/75 dark:border-sky-500/25 bg-[var(--glass-bg)] text-[var(--color-foreground)] ${pad} flex flex-wrap items-center justify-between gap-3 shrink-0`}>
              <div className="min-w-0">
                <div className="text-[11px] font-bold text-sky-700 dark:text-sky-300">شاخص‌ها و نبض میز کار</div>
                <div className="text-base font-extrabold leading-tight mt-0.5">{state.today.jalali}</div>
                <div className="text-[10px] leading-4 text-[var(--color-muted-foreground)]">
                  {state.today.weekday} · {state.today.gregorian}
                </div>
              </div>

              {state.activity.allowed && (
                <div className="grid grid-cols-3 gap-2 shrink-0">
                  <div className="px-3 py-1.5 rounded-xl border border-sky-200/80 dark:border-sky-500/25 bg-[var(--color-background)]/85 text-center min-w-[74px]">
                    <div className="text-base font-extrabold leading-5 text-sky-700 dark:text-sky-300">
                      {state.activity.overdue_fa ?? '۰'}
                    </div>
                    <div className="text-[10px] leading-4 text-[var(--color-muted-foreground)]">معوق من</div>
                  </div>
                  <div className="px-3 py-1.5 rounded-xl border border-emerald-200/80 dark:border-emerald-500/25 bg-[var(--color-background)]/85 text-center min-w-[74px]">
                    <div className="text-base font-extrabold leading-5 text-emerald-700 dark:text-emerald-300">
                      {state.activity.review_fa ?? '۰'}
                    </div>
                    <div className="text-[10px] leading-4 text-[var(--color-muted-foreground)]">تأیید کار</div>
                  </div>
                  <div className="px-3 py-1.5 rounded-xl border border-cyan-200/80 dark:border-cyan-500/25 bg-[var(--color-background)]/85 text-center min-w-[74px]">
                    <div className="text-base font-extrabold leading-5 text-cyan-700 dark:text-cyan-300">
                      {state.activity.requests_fa ?? '۰'}
                    </div>
                    <div className="text-[10px] leading-4 text-[var(--color-muted-foreground)]">منتظر من</div>
                  </div>
                </div>
              )}

              {state.permissions.workspace && (
                <button
                  type="button"
                  onClick={() => act('open_my_day')}
                  className="px-3.5 py-1.5 rounded-xl bg-[var(--color-primary)] text-[var(--color-primary-foreground)] text-xs font-bold hover:opacity-90 cursor-pointer transition inline-flex items-center gap-1.5 shrink-0"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>امروز من</span>
                </button>
              )}
            </div>
          )}

          {bentoModules.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 shrink-0">
              {bentoModules.map((mod, idx) => {
                const tint = bentoModuleTint(idx);
                return (
                  <button
                    key={mod.key}
                    type="button"
                    onClick={() => act('open_module', { key: mod.key })}
                    className={`rounded-2xl bento-card border border-[var(--color-border)] bg-[var(--glass-bg)] text-[var(--color-foreground)] ${pad} text-right flex items-center gap-2.5 cursor-pointer min-w-0`}
                  >
                    <span className={`w-8 h-8 rounded-xl border flex items-center justify-center shrink-0 ${tint.chip}`}>
                      <ModuleIcon moduleKey={mod.key} className="w-4 h-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-extrabold truncate">{mod.title}</div>
                      <div className="text-[10px] text-[var(--color-muted-foreground)] truncate">
                        {mod.desc}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {cards.has('briefing') && (
            <AiDailyBriefingCard
              state={state}
              cardClass="bento-card border-sky-200/75 dark:border-sky-500/25 flex-1 min-h-0"
            />
          )}

          {cards.has('today_reminders') && state.permissions.calendar && (
            <div className={`rounded-2xl bento-card border border-[var(--color-border)] bg-[var(--glass-bg)] ${pad} flex flex-col gap-1.5 min-w-0 shrink-0`}>
              <div className="text-xs font-bold leading-5 flex flex-wrap items-center justify-between gap-2">
                <span>یادآورهای امروز ({state.reminders_total_fa})</span>
                {state.occasions[0] && (
                  <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/12 text-emerald-700 dark:text-emerald-300 truncate max-w-full">
                    مناسبت: {state.occasions[0].title}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
                {state.reminders.length === 0 ? (
                  <div className="text-[11px] leading-5 text-[var(--color-muted-foreground)]">
                    برای امروز یادآور باز وجود ندارد.
                  </div>
                ) : (
                  state.reminders.slice(0, 2).map((r, i) => (
                    <div
                      key={`${r.title}-${i}`}
                      className="rounded-xl border border-[var(--color-border)] bg-[var(--color-background)]/85 px-2.5 py-1.5 text-[11px] leading-4 flex items-center justify-between gap-2 min-w-0"
                    >
                      <span className="truncate">{r.title}</span>
                      <span className="text-[10px] text-[var(--color-muted-foreground)] shrink-0">
                        {r.company}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Left 4 Cols in RTL: Weather Cockpit + Quick Status + Daily Quote Bento */}
        <div className="lg:col-span-4 flex flex-col gap-2.5 min-w-0 min-h-0 overflow-y-auto">
          {cards.has('weather') && state.weather.enabled && (
            <section
              aria-label="آب‌وهوای تهران"
              className={`rounded-2xl bento-card border border-sky-200/75 dark:border-sky-500/25 bg-[var(--glass-bg)] ${pad} shrink-0`}
            >
              <WeatherForecastCompact
                state={state}
                act={act}
                onOpenWeatherDetails={onOpenWeatherDetails}
                interactiveToggle
              />
            </section>
          )}

          <HomeMiniCalendar state={state} act={act} />

          {cards.has('today_reminders') && (
            <section
              aria-label="دسترسی سریع امروز"
              className={`rounded-2xl bento-card border border-teal-200/75 dark:border-teal-500/25 bg-[var(--glass-bg)] ${pad} flex flex-col gap-2 min-w-0 shrink-0`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold leading-5 text-teal-800 dark:text-teal-200">
                  رویدادها و پیگیری سریع
                </span>
                <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-sky-500/12 text-sky-700 dark:text-sky-300 shrink-0">
                  {state.occasions.length > 0 ? `${state.occasions.length} مناسبت` : state.today.weekday}
                </span>
              </div>
              {state.occasions.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {state.occasions.slice(0, 2).map((occ, idx) => (
                    <span
                      key={`${occ.title}-${idx}`}
                      className="text-[10px] leading-4 px-2 py-0.5 rounded-lg border border-emerald-200/80 dark:border-emerald-500/25 bg-[var(--color-background)]/85 truncate max-w-full"
                    >
                      {occ.title}
                    </span>
                  ))}
                </div>
              ) : (
                <div className="text-[11px] leading-4 text-[var(--color-muted-foreground)]">
                  مناسبت خاصی برای امروز ثبت نشده است.
                </div>
              )}
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => act('open_module', { key: 'desk' })}
                  className="rounded-xl border border-sky-300/60 dark:border-sky-500/35 bg-[var(--color-card)]/90 hover:border-sky-400 px-2.5 py-1.5 text-[11px] font-semibold text-sky-800 dark:text-sky-200 text-center cursor-pointer transition truncate"
                >
                  امروز من
                </button>
                <button
                  type="button"
                  onClick={() => act('new_reminder')}
                  className="rounded-xl border border-emerald-300/60 dark:border-emerald-500/35 bg-[var(--color-card)]/90 hover:border-emerald-400 px-2.5 py-1.5 text-[11px] font-semibold text-emerald-800 dark:text-emerald-200 text-center cursor-pointer transition truncate"
                >
                  ثبت یادآور
                </button>
              </div>
            </section>
          )}

          {cards.has('quote') && state.quote.enabled && state.quote.text && (
            <footer className={`rounded-2xl bento-card border border-emerald-200/75 dark:border-emerald-500/25 bg-[var(--glass-bg)] ${pad} text-xs flex flex-col justify-between gap-1.5 flex-1 min-h-0 min-w-0`}>
              <div className="flex flex-col gap-1 min-h-0 overflow-hidden">
                <div className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-300 font-bold leading-5">
                  <Quote className="w-3.5 h-3.5 shrink-0" />
                  <span>نکته روز</span>
                </div>
                <p className="text-[11px] leading-5 line-clamp-3 break-words">{state.quote.text}</p>
              </div>
              <div className="text-[10px] leading-4 text-[var(--color-muted-foreground)] truncate shrink-0">
                {state.quote.author}
              </div>
            </footer>
          )}
        </div>
      </div>
    </div>
  );
}
