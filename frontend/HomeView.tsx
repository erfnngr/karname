import React, { useEffect, useState } from 'react';
import {
  ArrowUpRight,
  CheckCircle2,
  Quote,
  Sparkles,
  X,
} from 'lucide-react';
import {
  AiDailyBriefingCard,
  CommandBentoLayout,
  SKIN_OPTIONS,
  SeaWelcomeHero,
  SkinId,
  WeatherForecastCompact,
  WeatherGlyph,
  themeWashStyle,
} from './HomeSkins';
import { instantToggleAppearance } from './appearance';
import { HomeState, homeRequest, onHomeState } from './home-bridge';

function faNumber(num: number): string {
  const map = '۰۱۲۳۴۵۶۷۸۹';
  return num.toFixed(1).replace(/\d/g, (d) => map[Number(d)]);
}

export function HomeView() {
  const [state, setState] = useState<HomeState | null>(null);
  const [optimisticDark, setOptimisticDark] = useState<boolean | null>(null);
  const [weatherDetailsOpen, setWeatherDetailsOpen] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    return onHomeState((nextState) => {
      setState(nextState);
      setOptimisticDark(null);
    });
  }, []);

  const act = (action: string, args: Record<string, unknown> = {}) => {
    setError('');
    return homeRequest(action, args).catch((e: Error) => {
      setError(e.message);
    });
  };

  if (!state) {
    return (
      <div
        dir="rtl"
        className="h-full flex items-center justify-center bg-[var(--color-background)] text-[var(--color-muted-foreground)] text-sm"
      >
        در حال بارگذاری صفحه خانه…
      </div>
    );
  }

  const w = state.weather;
  const dark = optimisticDark ?? state.theme === 'dark';
  const presetKey = state.theme_preset || 'default';
  const rawSkin = presetKey === 'bento_grid' ? 'command_bento' : state.home_skin || 'classic';
  const activeSkin: SkinId = SKIN_OPTIONS.some((o) => o.id === rawSkin) ? (rawSkin as SkinId) : 'classic';

  const handleSelectSkin = (nextSkin: SkinId) => {
    setState((prev) => (prev ? { ...prev, home_skin: nextSkin } : prev));
    void act('set_home_skin', { skin: nextSkin });
  };

  const handleToggleDark = () => {
    const nextDark = !dark;
    setOptimisticDark(nextDark);
    instantToggleAppearance(nextDark);
    setState((prev) => (prev ? { ...prev, theme: nextDark ? 'dark' : 'light' } : prev));
    void act('toggle_theme').finally(() => setOptimisticDark(null));
  };

  const presetCardRadius =
    presetKey === 'glass_mist'
      ? '24px'
      : presetKey === 'violet_modular'
      ? '10px'
      : presetKey === 'emerald_ivory'
      ? '16px'
      : 'var(--card-radius, 16px)';

  const presetCardFrame =
    presetKey === 'glass_mist'
      ? 'border-sky-300/60 dark:border-sky-400/25 shadow-[0_18px_42px_-16px_rgba(2,119,189,0.22)]'
      : presetKey === 'violet_modular'
      ? 'border-indigo-300/65 dark:border-indigo-400/25 border-t-[3px] border-t-[var(--color-primary)]'
      : presetKey === 'emerald_ivory'
      ? 'border-emerald-700/20 dark:border-emerald-400/25 border-r-[3px] border-r-[var(--color-primary)]'
      : 'border-[var(--color-border)]';

  return (
    <div
      dir="rtl"
      data-theme-preset={presetKey}
      className="sea-home-shell home-no-scroll text-[var(--color-foreground)] p-3 md:p-4 flex flex-col"
    >
      <div className="sea-home-wash" style={{ background: themeWashStyle(presetKey, dark) }} />
      <div className="sea-karname-watermark" aria-hidden="true">
        <img src={dark ? './karname-logo-dark.png' : './karname-logo.png'} alt="" />
      </div>
      <div className="relative z-10 w-full flex-1 min-h-0 flex flex-col">
      {error && (
        <div className="w-full max-w-[1840px] mx-auto mb-2 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-1.5 text-xs text-rose-600 dark:text-rose-300 shrink-0">
          {error}
        </div>
      )}

      {activeSkin === 'command_bento' ? (
        <CommandBentoLayout
          state={state}
          dark={dark}
          skin={activeSkin}
          onSelectSkin={handleSelectSkin}
          onToggleDark={handleToggleDark}
          act={act}
          onOpenWeatherDetails={() => setWeatherDetailsOpen(true)}
        />
      ) : (
        (() => {
          const cards = new Set(state.home_prefs?.cards ?? ['briefing', 'weather', 'today_reminders', 'activity_stats', 'quote']);
          const colsPref = state.home_prefs?.columns ?? 'auto';
          const densityPref = state.home_prefs?.density ?? 'comfortable';
          const gapCls = densityPref === 'compact' ? 'gap-2.5' : densityPref === 'spacious' ? 'gap-4' : 'gap-3';
          const padCls = densityPref === 'compact' ? 'p-3' : densityPref === 'spacious' ? 'p-4' : 'p-3.5';
          const showWeather = cards.has('weather') && w.enabled;
          const showBriefing = cards.has('briefing');
          const showToday = cards.has('today_reminders') || cards.has('activity_stats');
          const spanCls =
            colsPref === 2
              ? 'lg:col-span-6'
              : showWeather && showBriefing && showToday
              ? 'lg:col-span-4'
              : 'lg:col-span-6';
          return (
        <div className={`w-full max-w-[1840px] mx-auto flex-1 min-h-0 flex flex-col justify-between ${gapCls}`}>
        <SeaWelcomeHero state={state} dark={dark} />
        {/* Main Frosted-Glass Home Grid (Zero Vertical Scroll) */}
        <div className={`grid grid-cols-1 lg:grid-cols-12 ${gapCls} items-stretch flex-1 min-h-0`}>
          {/* Weather Card (Compact Interactive Hourly/Weekly + Details Modal) */}
          {showWeather && (
            <section
              aria-label="آب‌وهوای تهران"
              className={`${spanCls} rounded-2xl border ${presetCardFrame} bg-[var(--glass-bg)] ${padCls} flex flex-col justify-between gap-2.5 backdrop-blur-lg transition-colors duration-200 min-h-0`}
              style={{ boxShadow: 'var(--glass-shadow)', borderRadius: presetCardRadius }}
            >
              <WeatherForecastCompact
                state={state}
                act={act}
                onOpenWeatherDetails={() => setWeatherDetailsOpen(true)}
                interactiveToggle
              />
            </section>
          )}

          {/* Center AI Daily Briefing (Written Summary Only, No Shortcuts) */}
          {showBriefing && (
            <AiDailyBriefingCard
              state={state}
              cardClass={`${spanCls} ${presetCardFrame}`}
              cardStyle={{ boxShadow: 'var(--glass-shadow)', borderRadius: presetCardRadius }}
            />
          )}

          {/* Today, Reminders, Occasions & Workspace Card */}
          {showToday && (
          <section
            aria-label="امروز"
            className={`${spanCls} rounded-2xl border ${presetCardFrame} bg-[var(--glass-bg)] ${padCls} flex flex-col justify-between gap-2.5 backdrop-blur-lg transition-colors duration-200 min-h-0`}
            style={{ boxShadow: 'var(--glass-shadow)', borderRadius: presetCardRadius }}
          >
            <div className="flex items-start justify-between gap-2 pb-2 border-b border-[var(--color-border)]">
              <div>
                <div className="text-xs text-[var(--color-muted-foreground)]">امروز · {state.today.weekday}</div>
                <div className="text-xl font-extrabold mt-0.5">{state.today.jalali}</div>
                <div className="text-xs text-[var(--color-muted-foreground)]">{state.today.gregorian}</div>
              </div>
              {state.permissions.workspace && (
                <button
                  type="button"
                  onClick={() => act('open_my_day')}
                  className="px-3.5 py-2 rounded-xl bg-[var(--color-primary)] text-[var(--color-primary-foreground)] text-xs font-bold hover:opacity-90 cursor-pointer transition inline-flex items-center gap-1.5"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>امروز من</span>
                </button>
              )}
            </div>

            {cards.has('activity_stats') && state.activity.allowed && (
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-xl bg-[var(--color-card)] border border-[var(--color-border)] p-2">
                  <div className="text-base font-extrabold">{state.activity.overdue_fa ?? '۰'}</div>
                  <div className="text-[11px] text-[var(--color-muted-foreground)]">معوق من</div>
                </div>
                <div className="rounded-xl bg-[var(--color-card)] border border-[var(--color-border)] p-2">
                  <div className="text-base font-extrabold">{state.activity.review_fa ?? '۰'}</div>
                  <div className="text-[11px] text-[var(--color-muted-foreground)]">تأیید کار</div>
                </div>
                <div className="rounded-xl bg-[var(--color-card)] border border-[var(--color-border)] p-2">
                  <div className="text-base font-extrabold">{state.activity.requests_fa ?? '۰'}</div>
                  <div className="text-[11px] text-[var(--color-muted-foreground)]">منتظر من</div>
                </div>
              </div>
            )}

            {state.activity.next_meeting && (
              <div className="rounded-xl bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/25 px-3 py-2 text-xs">
                <span className="font-semibold">جلسه بعدی: </span>
                <span>{state.activity.next_meeting}</span>
              </div>
            )}

            {cards.has('today_reminders') && state.permissions.calendar && (
              <div>
                <div className="flex items-center justify-between text-xs font-bold mb-1.5">
                  <span>یادآورهای امروز ({state.reminders_total_fa})</span>
                  <button
                    type="button"
                    onClick={() => act('open_module', { key: 'calendar' })}
                    className="text-[var(--color-primary)] hover:underline text-[11px] font-medium cursor-pointer"
                  >
                    تقویم
                  </button>
                </div>
                {state.reminders.length === 0 ? (
                  <p className="text-xs text-[var(--color-muted-foreground)]">
                    یادآوری برای امروز ثبت نشده است.
                  </p>
                ) : (
                  <ul className="flex flex-col gap-1.5">
                    {state.reminders.slice(0, 4).map((r, idx) => (
                      <li
                        key={`${r.title}-${idx}`}
                        className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-1.5 text-xs flex items-center justify-between gap-2"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <CheckCircle2
                            className={`w-3.5 h-3.5 shrink-0 ${
                              r.done ? 'text-emerald-500' : 'text-[var(--color-muted-foreground)]'
                            }`}
                          />
                          <span className={`truncate ${r.done ? 'line-through opacity-60' : ''}`}>{r.title}</span>
                        </div>
                        <span className="text-[10px] text-[var(--color-muted-foreground)] shrink-0">
                          {r.company}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <div>
              <div className="text-xs font-bold mb-1.5">مناسبت امروز</div>
              {state.occasions.length === 0 ? (
                <p className="text-xs text-[var(--color-muted-foreground)]">مناسبتی در فهرست ثبت نشده است.</p>
              ) : (
                <div className="flex flex-col gap-1">
                  {state.occasions.map((o, idx) => (
                    <div
                      key={`${o.title}-${idx}`}
                      className={`rounded-lg px-2.5 py-1.5 text-xs flex items-center justify-between gap-2 border ${
                        o.holiday
                          ? 'bg-rose-500/10 border-rose-500/30 text-rose-700 dark:text-rose-200'
                          : 'bg-[var(--color-card)] border-[var(--color-border)]'
                      }`}
                    >
                      <span className="truncate">• {o.title}</span>
                      {o.source && (
                        <button
                          type="button"
                          onClick={() => act('open_occasion_source', { url: o.source })}
                          title="منبع مناسبت"
                          className="shrink-0 opacity-75 hover:opacity-100 cursor-pointer"
                        >
                          <ArrowUpRight className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>
          )}
        </div>

        {/* Daily Quote Footer */}
        {cards.has('quote') && state.quote.enabled && state.quote.text && (
          <footer
            className={`rounded-2xl border ${presetCardFrame} bg-[var(--glass-bg)] px-4 py-2.5 flex flex-col sm:flex-row items-center justify-between gap-2 text-center sm:text-right backdrop-blur-lg shrink-0`}
            style={{ boxShadow: 'var(--glass-shadow)', borderRadius: presetCardRadius }}
          >
            <div className="flex items-center gap-3">
              <Quote className="w-4 h-4 text-[var(--color-primary)] shrink-0 hidden sm:block" />
              <p className="text-xs md:text-sm leading-relaxed select-text">{state.quote.text}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0 text-xs text-[var(--color-muted-foreground)]">
              <span>
                {state.quote.author}
                {state.quote.work ? ` · ${state.quote.work}` : ''}
              </span>
              {state.quote.has_source && (
                <button
                  type="button"
                  onClick={() => act('open_quote_source')}
                  title={`منبع: ${state.quote.author || ''} ${state.quote.work || ''}`}
                  className="p-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] hover:bg-[var(--color-accent)] cursor-pointer"
                >
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </footer>
        )}
      </div>
          );
        })()
      )}
      </div>

      {/* Weather Details & Station Comparison Modal */}
      {weatherDetailsOpen && w.has_data && (
        <div
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setWeatherDetailsOpen(false)}
        >
          <div
            className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 flex flex-col gap-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-3">
              <div>
                <h3 className="font-bold text-base">جزئیات آب‌وهوای {w.location || 'تهران'}</h3>
                <p className="text-xs text-[var(--color-muted-foreground)]">
                  {w.caption}
                  {w.station ? ` · ایستگاه: ${w.station}` : ''}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setWeatherDetailsOpen(false)}
                className="p-1.5 rounded-lg hover:bg-[var(--color-accent)] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex items-center justify-between rounded-xl bg-[var(--color-background)] border border-[var(--color-border)] p-4">
              <div className="flex items-center gap-3">
                <WeatherGlyph kind={w.current?.kind || 'cloud'} className="w-10 h-10" />
                <div>
                  <div className="text-3xl font-extrabold">{w.current?.temp}°</div>
                  <div className="text-xs text-[var(--color-muted-foreground)]">{w.current?.label}</div>
                </div>
              </div>
              <div className="text-xs text-[var(--color-muted-foreground)] flex flex-col gap-1">
                {w.current?.humidity != null && <span>رطوبت: {w.current.humidity}٪</span>}
                {w.current?.wind != null && <span>باد: {w.current.wind} کیلومتر/ساعت</span>}
              </div>
            </div>

            {(w.hours?.length ?? 0) > 0 && (
              <div>
                <div className="text-xs font-bold mb-2">پیش‌بینی ساعتی</div>
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {w.hours!.map((h, idx) => (
                    <div
                      key={`${h.time}-${idx}`}
                      className="shrink-0 w-16 rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] p-2 flex flex-col items-center gap-1 text-xs"
                    >
                      <span className="text-[11px] text-[var(--color-muted-foreground)]">{h.time}</span>
                      <WeatherGlyph kind={h.kind} className="w-5 h-5" />
                      <span className="font-bold">{h.temp}°</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(w.days?.length ?? 0) > 0 && (
              <div>
                <div className="text-xs font-bold mb-2">پیش‌بینی هفتگی</div>
                <div className="flex flex-col gap-1.5">
                  {w.days!.map((d, idx) => (
                    <div
                      key={`${d.name}-${idx}`}
                      className="flex items-center justify-between rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-xs"
                    >
                      <span className="font-semibold w-28">
                        {d.name} · {d.date_fa}
                      </span>
                      <div className="flex items-center gap-2">
                        <WeatherGlyph kind={d.kind} className="w-4 h-4" />
                        <span className="text-[var(--color-muted-foreground)]">{d.label}</span>
                      </div>
                      <span className="font-bold">
                        {d.max}° / {d.min}°
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[var(--color-border)]">
              <div className="text-xs text-[var(--color-muted-foreground)]">
                {w.comparison?.busy && 'در حال دریافت مقایسه…'}
                {!w.comparison?.busy && w.comparison?.data && (
                  <span>
                    مدل: {faNumber(w.comparison.data.model)}° · ایستگاه: {faNumber(w.comparison.data.observation)}° · اختلاف:{' '}
                    {faNumber(w.comparison.data.difference)}°
                  </span>
                )}
                {!w.comparison?.busy && !w.comparison?.data && w.comparison?.error && (
                  <span>{w.comparison.error}</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={!!w.comparison?.busy}
                  onClick={() => act('compare_weather')}
                  className="px-3 py-1.5 rounded-xl bg-[var(--color-primary)] text-[var(--color-primary-foreground)] text-xs font-semibold hover:opacity-90 disabled:opacity-50 cursor-pointer"
                >
                  مقایسه با مدل
                </button>
                <button
                  type="button"
                  onClick={() => setWeatherDetailsOpen(false)}
                  className="px-3 py-1.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] text-xs cursor-pointer"
                >
                  بستن
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
