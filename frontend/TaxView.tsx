import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  ClipboardCheck,
  ExternalLink,
  FileSpreadsheet,
  FileText,
  FolderOpen,
  MoreHorizontal,
  Pencil,
  Plus,
  RefreshCw,
  ShieldAlert,
  Users,
  X,
} from "lucide-react";
import { connectAppearance } from "./appearance";
import HowItWorks from "./components/ui/how-it-works";
import { InsurancePreview } from "./InsurancePreview";

type TaxCaseSummary = { id: string; label: string };
type TaxCaseDetail = {
  id: string;
  title: string;
  period: string;
  due_date: string;
  status: string;
  reference: string;
  responsible: string;
  findings: string[];
};
type TaxStepItem = {
  title: string;
  description: string;
  done: boolean;
};
type TaxState = {
  allowed: boolean;
  can_edit: boolean;
  can_create: boolean;
  company: string;
  company_id: string | null;
  companies: { id: string; label: string }[];
  category: string;
  categories: string[];
  cases: TaxCaseSummary[];
  selected_case: string | null;
  selected_case_detail: TaxCaseDetail | null;
  steps: TaxStepItem[];
  status: string;
};

type InvoiceSummaryRow = {
  label: string;
  count: string;
  base: string;
  tax: string;
  total: string;
};
type CompareInvoicesResult = {
  start: string;
  end: string;
  rows: InvoiceSummaryRow[];
  sales_tax: string;
  purchase_tax: string;
  skipped: string;
  diff_sales: string;
  diff_purchase: string;
};

type Signal<T extends (...args: any[]) => void> = { connect: (fn: T) => void };
type TaxBridge = {
  changed: Signal<(raw: string) => void>;
  completed: Signal<(id: string, raw: string) => void>;
  request: (id: string, action: string, raw: string) => void;
};

const INITIAL_STATE: TaxState = {
  allowed: false,
  can_edit: false,
  can_create: false,
  company: "",
  company_id: null,
  companies: [],
  category: "",
  categories: [],
  cases: [],
  selected_case: null,
  selected_case_detail: null,
  steps: [],
  status: "",
};

const formatFaNumber = (n: number) => {
  const fa = n.toLocaleString("fa-IR");
  return n < 10 ? `۰${fa}` : fa;
};

export function TaxView() {
  const [state, setState] = useState<TaxState>(INITIAL_STATE);
  const [error, setError] = useState("");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [selectedStepIndex, setSelectedStepIndex] = useState<number | null>(
    null
  );
  const [toolsOpen, setToolsOpen] = useState(false);
  const [insurancePreviewOpen, setInsurancePreviewOpen] = useState(false);

  // Inline VAT invoice comparison state inside step modal
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareStart, setCompareStart] = useState("");
  const [compareEnd, setCompareEnd] = useState("");
  const [portalSales, setPortalSales] = useState("");
  const [portalPurchase, setPortalPurchase] = useState("");
  const [compareResult, setCompareResult] =
    useState<CompareInvoicesResult | null>(null);

  const bridge = useRef<TaxBridge | null>(null);
  const toolsRef = useRef<HTMLDivElement | null>(null);
  const pending = useRef(
    new Map<
      string,
      {
        resolve: (val: unknown) => void;
        reject: (err: Error) => void;
        timer: number;
      }
    >()
  );

  const call = useCallback(
    <T = unknown,>(action: string, args: Record<string, unknown> = {}) =>
      new Promise<T>((resolve, reject) => {
        if (!bridge.current) {
          reject(new Error("اتصال بخش مالیات برقرار نیست."));
          return;
        }
        const id = crypto.randomUUID();
        const timeoutMs = [
          "step",
          "create",
          "edit_case",
          "case_details",
          "case_review",
          "insured_people",
          "insurance_workshops",
          "insurance_employee_profiles",
          "insurance_lists",
        ].includes(action)
          ? 1800000
          : 60000;
        const timer = window.setTimeout(() => {
          pending.current.delete(id);
          reject(new Error("زمان پاسخ‌گویی برنامه به پایان رسید."));
        }, timeoutMs);
        pending.current.set(id, {
          resolve: resolve as (val: unknown) => void,
          reject,
          timer,
        });
        bridge.current.request(id, action, JSON.stringify(args));
      }),
    []
  );

  useEffect(() => {
    let active = true;
    const Channel = (window as any).QWebChannel;
    if (!Channel || !(window as any).qt) {
      setError("اتصال بخش مالیات برقرار نیست.");
      return;
    }
    new Channel((window as any).qt.webChannelTransport, (channel: any) => {
      if (!active) return;
      connectAppearance(channel.objects.appearance);
      const native: TaxBridge | undefined = channel.objects.tax;
      if (!native) {
        setError("سرویس بخش مالیات در دسترس نیست.");
        return;
      }
      bridge.current = native;
      native.changed.connect((raw: string) => {
        if (!active) return;
        try {
          const parsed = JSON.parse(raw) as TaxState;
          setState(parsed);
        } catch {
          setError("اطلاعات دریافتی بخش مالیات معتبر نیست.");
        }
      });
      native.completed.connect((id: string, raw: string) => {
        const entry = pending.current.get(id);
        if (!entry) return;
        pending.current.delete(id);
        window.clearTimeout(entry.timer);
        try {
          const result = JSON.parse(raw) as {
            ok: boolean;
            value?: unknown;
            error?: string;
          };
          if (result.ok) entry.resolve(result.value);
          else entry.reject(new Error(result.error || "عملیات انجام نشد."));
        } catch {
          entry.reject(new Error("پاسخ برنامه معتبر نیست."));
        }
      });
      void call("refresh").catch((err) =>
        setError(err instanceof Error ? err.message : String(err))
      );
    });

    return () => {
      active = false;
      bridge.current = null;
      for (const entry of pending.current.values()) {
        window.clearTimeout(entry.timer);
        entry.reject(new Error("صفحه بسته شد."));
      }
      pending.current.clear();
    };
  }, [call]);

  // Reset modal step if category changes or steps list shrinks
  useEffect(() => {
    if (
      selectedStepIndex !== null &&
      (selectedStepIndex < 0 || selectedStepIndex >= state.steps.length)
    ) {
      setSelectedStepIndex(null);
    }
  }, [selectedStepIndex, state.steps.length]);

  useEffect(() => {
    setCompareOpen(false);
    setCompareResult(null);
  }, [selectedStepIndex, state.category]);

  // Close tools dropdown on outside click
  useEffect(() => {
    if (!toolsOpen) return;
    const onPointerDown = (ev: MouseEvent) => {
      if (toolsRef.current && !toolsRef.current.contains(ev.target as Node)) {
        setToolsOpen(false);
      }
    };
    window.addEventListener("mousedown", onPointerDown);
    return () => window.removeEventListener("mousedown", onPointerDown);
  }, [toolsOpen]);

  // Close modal on Escape
  useEffect(() => {
    if (selectedStepIndex === null) return;
    const onKeyDown = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") setSelectedStepIndex(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedStepIndex]);

  const run = useCallback(
    async (action: string, args: Record<string, unknown> = {}) => {
      setError("");
      setBusyAction(action);
      try {
        return await call(action, args);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        return undefined;
      } finally {
        setBusyAction(null);
      }
    },
    [call]
  );

  const handleCategorySwitch = (name: string) => {
    if (name === state.category) return;
    setSelectedStepIndex(null);
    setToolsOpen(false);
    void run("category", { name });
  };

  const handleCompleteStep = async (index: number, nextDone: boolean) => {
    setError("");
    setBusyAction("complete_step");
    try {
      await call("complete_step", { index, done: nextDone });
      if (nextDone) {
        setSelectedStepIndex(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyAction(null);
    }
  };

  const handleCompareInvoices = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const res = await run("compare_invoices", {
      start: compareStart.trim(),
      end: compareEnd.trim(),
      portal_sales: portalSales.trim(),
      portal_purchase: portalPurchase.trim(),
    });
    if (res) {
      setCompareResult(res as CompareInvoicesResult);
    }
  };

  const doneCount = useMemo(
    () => state.steps.filter((s) => s.done).length,
    [state.steps]
  );
  const totalCount = state.steps.length;
  const progressPct =
    totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0;

  const activeStep =
    selectedStepIndex !== null ? state.steps[selectedStepIndex] ?? null : null;

  return (
    <main
      dir="rtl"
      className="glass-backdrop relative flex h-screen flex-col overflow-hidden text-foreground"
    >
      {/* Clean, uncluttered glass top bar */}
      <header className="glass-surface z-20 shrink-0 border-b px-4 py-2.5">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2.5">
          {/* Category selector pills */}
          <nav
            aria-label="بخش‌های مالیاتی"
            className="flex flex-wrap items-center gap-1.5"
          >
            {state.categories.map((cat) => {
              const active = cat === state.category;
              return (
                <button
                  key={cat}
                  type="button"
                  data-tax-category={cat}
                  aria-pressed={active}
                  onClick={() => handleCategorySwitch(cat)}
                  className={`rounded-xl px-3 py-1.5 text-xs font-medium transition-all cursor-pointer ${
                    active
                      ? "bg-primary text-primary-foreground shadow-sm shadow-sky-500/25"
                      : "glass-pill text-slate-700 hover:bg-white/80 dark:text-slate-200 dark:hover:bg-white/15"
                  }`}
                >
                  {cat}
                </button>
              );
            })}
          </nav>

          {/* Compact context controls (Company, Case, Add, Tools) */}
          <div className="flex flex-wrap items-center gap-2">
            {state.companies.length > 1 && (
              <select
                aria-label="شرکت"
                value={state.company_id || ""}
                onChange={(e) => void run("company", { id: e.target.value })}
                className="glass-pill max-w-44 rounded-xl px-2.5 py-1.5 text-xs text-foreground outline-none"
              >
                {state.companies.map((c) => (
                  <option
                    key={c.id}
                    value={c.id}
                    className="bg-card text-foreground"
                  >
                    {c.label}
                  </option>
                ))}
              </select>
            )}

            {state.allowed && (
              <select
                aria-label="پرونده مالیاتی"
                value={state.selected_case || ""}
                onChange={(e) =>
                  void run("case", { id: e.target.value || null })
                }
                className="glass-pill max-w-56 rounded-xl px-2.5 py-1.5 text-xs text-foreground outline-none"
              >
                <option value="" className="bg-card text-foreground">
                  {state.cases.length > 0
                    ? "انتخاب پرونده مالیاتی..."
                    : "بدون پرونده"}
                </option>
                {state.cases.map((c) => (
                  <option
                    key={c.id}
                    value={c.id}
                    className="bg-card text-foreground"
                  >
                    {c.label}
                  </option>
                ))}
              </select>
            )}

            {state.can_create && (
              <button
                type="button"
                onClick={() => void run("create")}
                disabled={busyAction !== null}
                className="glass-pill inline-flex items-center gap-1 rounded-xl px-2.5 py-1.5 text-xs font-medium text-sky-700 hover:bg-sky-100/80 dark:text-sky-200 dark:hover:bg-sky-500/20 cursor-pointer disabled:opacity-50"
              >
                <Plus className="size-3.5" />
                <span>پرونده جدید</span>
              </button>
            )}

            {state.allowed && (
              <div ref={toolsRef} className="relative">
                <button
                  type="button"
                  aria-expanded={toolsOpen}
                  aria-label="امکانات بخش مالیات"
                  onClick={() => setToolsOpen((v) => !v)}
                  className="glass-pill inline-flex items-center gap-1 rounded-xl px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  <MoreHorizontal className="size-4" />
                </button>
                {toolsOpen && (
                  <div className="glass-modal absolute left-0 z-40 mt-2 flex min-w-44 flex-col rounded-2xl border p-1.5 shadow-xl">
                    <button
                      type="button"
                      onClick={() => {
                        setToolsOpen(false);
                        void run("all_cases");
                      }}
                      className="flex items-center gap-2 rounded-xl px-3 py-2 text-right text-xs hover:bg-sky-500/15 cursor-pointer"
                    >
                      <FolderOpen className="size-3.5 text-sky-600 dark:text-sky-300" />
                      <span>همه پرونده‌ها</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setToolsOpen(false);
                        void run("compare");
                      }}
                      className="flex items-center gap-2 rounded-xl px-3 py-2 text-right text-xs hover:bg-sky-500/15 cursor-pointer"
                    >
                      <FileSpreadsheet className="size-3.5 text-indigo-600 dark:text-indigo-300" />
                      <span>مقایسه فاکتورها</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setToolsOpen(false);
                        void run("tools");
                      }}
                      className="flex items-center gap-2 rounded-xl px-3 py-2 text-right text-xs hover:bg-sky-500/15 cursor-pointer"
                    >
                      <ExternalLink className="size-3.5 text-violet-600 dark:text-violet-300" />
                      <span>سامانه‌های مرتبط</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setToolsOpen(false);
                        void run("refresh");
                      }}
                      className="flex items-center gap-2 rounded-xl px-3 py-2 text-right text-xs hover:bg-sky-500/15 cursor-pointer"
                    >
                      <RefreshCw className="size-3.5 text-emerald-600 dark:text-emerald-300" />
                      <span>بروزرسانی</span>
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Subtle status / progress strip + error banner */}
      <div className="shrink-0 px-4 pt-2">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 rounded-2xl border border-white/40 bg-white/45 px-4 py-2 text-xs backdrop-blur-md dark:border-white/10 dark:bg-slate-900/45">
          <div className="flex flex-wrap items-center gap-2 text-slate-700 dark:text-slate-200">
            <span className="font-semibold text-slate-900 dark:text-slate-50">
              {state.category || "بخش مالیات"}
            </span>
            {state.company && (
              <>
                <span className="opacity-40">•</span>
                <span>{state.company}</span>
              </>
            )}
            {state.selected_case_detail && (
              <>
                <span className="opacity-40">•</span>
                <span className="font-medium text-sky-700 dark:text-sky-300">
                  {state.selected_case_detail.title}
                </span>
                {state.selected_case_detail.period && (
                  <span className="rounded-lg bg-white/60 px-2 py-0.5 text-[11px] dark:bg-white/10">
                    دوره: {state.selected_case_detail.period}
                  </span>
                )}
                {state.selected_case_detail.due_date && (
                  <span className="rounded-lg bg-white/60 px-2 py-0.5 text-[11px] dark:bg-white/10">
                    موعد: {state.selected_case_detail.due_date}
                  </span>
                )}
              </>
            )}
            {!state.selected_case_detail && state.status && (
              <>
                <span className="opacity-40">•</span>
                <span className="text-muted-foreground">{state.status}</span>
              </>
            )}
          </div>

          {totalCount > 0 && state.allowed && (
            <div className="flex items-center gap-2.5">
              <span className="text-[11px] font-medium tabular-nums text-slate-700 dark:text-slate-200">
                پیشرفت:{" "}
                <strong className="text-emerald-700 dark:text-emerald-300">
                  {doneCount.toLocaleString("fa-IR")} از{" "}
                  {totalCount.toLocaleString("fa-IR")}
                </strong>
              </span>
              <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-200/80 dark:bg-white/10">
                <div
                  className="h-full rounded-full bg-gradient-to-l from-emerald-500 to-teal-400 transition-all duration-300"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {error && (
          <div
            role="alert"
            className="mx-auto mt-2 flex max-w-6xl items-center justify-between gap-2 rounded-2xl border border-rose-300/80 bg-rose-50/90 px-4 py-2 text-xs text-rose-800 backdrop-blur-md dark:border-rose-500/40 dark:bg-rose-950/65 dark:text-rose-200"
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="size-4 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              type="button"
              aria-label="بستن خطا"
              onClick={() => setError("")}
              className="rounded-lg p-1 hover:bg-rose-200/50 dark:hover:bg-rose-800/40 cursor-pointer"
            >
              <X className="size-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Main Viewport: Visual Step Roadmap */}
      <section
        aria-label="نقشه مراحل مالیات"
        className="flex-1 overflow-y-auto overflow-x-hidden px-3 pb-10 pt-2"
      >
        {!state.allowed && state.status ? (
          <div className="mx-auto mt-12 max-w-lg rounded-3xl border border-amber-300/70 bg-white/75 p-8 text-center shadow-lg backdrop-blur-xl dark:border-amber-400/25 dark:bg-slate-900/70">
            <ShieldAlert className="mx-auto mb-3 size-10 text-amber-500" />
            <h2 className="mb-2 text-base font-bold text-slate-900 dark:text-slate-50">
              محدودیت دسترسی بخش مالیات
            </h2>
            <p className="text-sm leading-7 text-slate-600 dark:text-slate-300">
              {state.status}
            </p>
          </div>
        ) : (
          <HowItWorks
            steps={state.steps}
            activeStepIndex={selectedStepIndex}
            onStepClick={(index) => setSelectedStepIndex(index)}
          />
        )}
      </section>

      {/* Step Detail & Tasks Modal */}
      {selectedStepIndex !== null && activeStep && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="tax-step-modal-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelectedStepIndex(null);
          }}
        >
          <div
            dir="rtl"
            className="glass-modal relative flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden rounded-3xl border shadow-2xl"
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between gap-3 border-b border-white/30 px-6 py-4 dark:border-white/10">
              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-sky-500/15 px-3 py-0.5 text-xs font-bold text-sky-700 dark:bg-sky-400/20 dark:text-sky-200">
                    مرحله {formatFaNumber(selectedStepIndex)}
                  </span>
                  {activeStep.done ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/20 px-3 py-0.5 text-xs font-semibold text-emerald-800 dark:bg-emerald-500/25 dark:text-emerald-200">
                      <CheckCircle2 className="size-3.5" />
                      <span>تکمیل‌شده</span>
                    </span>
                  ) : (
                    <span className="rounded-full bg-amber-500/15 px-3 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-400/20 dark:text-amber-200">
                      در انتظار انجام
                    </span>
                  )}
                </div>
                <h2
                  id="tax-step-modal-title"
                  className="text-lg font-bold leading-snug text-slate-900 dark:text-slate-50"
                >
                  {activeStep.title}
                </h2>
              </div>

              <button
                type="button"
                aria-label="بستن"
                onClick={() => setSelectedStepIndex(null)}
                className="rounded-xl p-1.5 text-slate-500 hover:bg-slate-200/60 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-white cursor-pointer"
              >
                <X className="size-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
              {/* Step description / tasks */}
              <div className="rounded-2xl border border-sky-200/70 bg-sky-50/70 p-4 dark:border-sky-400/25 dark:bg-sky-950/35">
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-bold text-sky-800 dark:text-sky-200">
                  <ClipboardCheck className="size-4" />
                  <span>توضیحات و کارهای این مرحله</span>
                </div>
                <p className="whitespace-pre-line text-sm leading-7 text-slate-800 dark:text-slate-100">
                  {activeStep.description}
                </p>
              </div>

              {/* Active case metadata & review findings */}
              {state.selected_case_detail ? (
                <div className="glass-subtle space-y-3 rounded-2xl border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-bold text-slate-800 dark:text-slate-100">
                      پرونده فعال: {state.selected_case_detail.title}
                    </span>
                    {state.selected_case_detail.status && (
                      <span className="glass-pill rounded-full px-2.5 py-0.5 text-[11px]">
                        {state.selected_case_detail.status}
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 dark:text-slate-300 sm:grid-cols-4">
                    <div>
                      <span className="opacity-70">دوره: </span>
                      <strong className="text-foreground">
                        {state.selected_case_detail.period || "—"}
                      </strong>
                    </div>
                    <div>
                      <span className="opacity-70">موعد: </span>
                      <strong className="text-foreground">
                        {state.selected_case_detail.due_date || "—"}
                      </strong>
                    </div>
                    <div>
                      <span className="opacity-70">کد پیگیری: </span>
                      <strong className="text-foreground">
                        {state.selected_case_detail.reference || "—"}
                      </strong>
                    </div>
                    <div>
                      <span className="opacity-70">مسئول: </span>
                      <strong className="text-foreground">
                        {state.selected_case_detail.responsible || "—"}
                      </strong>
                    </div>
                  </div>
                  {state.selected_case_detail.findings.length > 0 && (
                    <div className="rounded-xl border border-amber-300/70 bg-amber-50/80 p-3 dark:border-amber-400/30 dark:bg-amber-500/10">
                      <p className="mb-1 text-xs font-semibold text-amber-800 dark:text-amber-200">
                        نکات و کنترل‌های پرونده:
                      </p>
                      <ul className="list-inside list-disc space-y-1 text-xs leading-6 text-amber-900 dark:text-amber-100">
                        {state.selected_case_detail.findings.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-2xl border border-amber-300/70 bg-amber-50/75 p-4 text-xs text-amber-900 dark:border-amber-400/30 dark:bg-amber-950/45 dark:text-amber-100">
                  <p className="mb-2 font-medium">
                    برای ثبت پیشرفت مراحل، ابتدا یک پرونده مالیاتی انتخاب یا ایجاد
                    کنید.
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    {state.cases.length > 0 && (
                      <select
                        aria-label="انتخاب سریع پرونده"
                        value=""
                        onChange={(e) => {
                          if (e.target.value)
                            void run("case", { id: e.target.value });
                        }}
                        className="glass-pill rounded-xl px-2.5 py-1.5 text-xs text-foreground"
                      >
                        <option value="">انتخاب پرونده موجود...</option>
                        {state.cases.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.label}
                          </option>
                        ))}
                      </select>
                    )}
                    {state.can_create && (
                      <button
                        type="button"
                        onClick={() => void run("create")}
                        className="inline-flex items-center gap-1 rounded-xl bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-700 cursor-pointer"
                      >
                        <Plus className="size-3.5" />
                        <span>ساخت پرونده جدید</span>
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Contextual inline tools */}
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => void run("step", { index: selectedStepIndex })}
                  disabled={busyAction !== null}
                  className="glass-pill inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-medium hover:bg-white/80 dark:hover:bg-white/15 cursor-pointer disabled:opacity-50"
                >
                  <FileText className="size-3.5 text-sky-600 dark:text-sky-300" />
                  <span>راهنما و ابزارهای مرحله</span>
                </button>

                {state.selected_case && state.can_edit && (
                  <button
                    type="button"
                    onClick={() => void run("edit_case")}
                    disabled={busyAction !== null}
                    className="glass-pill inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-medium hover:bg-white/80 dark:hover:bg-white/15 cursor-pointer disabled:opacity-50"
                  >
                    <Pencil className="size-3.5 text-indigo-600 dark:text-indigo-300" />
                    <span>ویرایش پرونده</span>
                  </button>
                )}

                {state.selected_case && (
                  <>
                    <button
                      type="button"
                      onClick={() => void run("case_details")}
                      disabled={busyAction !== null}
                      className="glass-pill inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-medium hover:bg-white/80 dark:hover:bg-white/15 cursor-pointer disabled:opacity-50"
                    >
                      <FolderOpen className="size-3.5 text-violet-600 dark:text-violet-300" />
                      <span>مدارک و تاریخچه</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => void run("case_review")}
                      disabled={busyAction !== null}
                      className="glass-pill inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-medium hover:bg-white/80 dark:hover:bg-white/15 cursor-pointer disabled:opacity-50"
                    >
                      <ClipboardCheck className="size-3.5 text-amber-600 dark:text-amber-300" />
                      <span>کنترل پرونده</span>
                    </button>
                  </>
                )}

                {state.category === "بیمه کارکنان" && state.selected_case && (
                  <button
                    type="button"
                    onClick={() => void run("insured_people")}
                    disabled={busyAction !== null}
                    className="glass-pill inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-medium hover:bg-white/80 dark:hover:bg-white/15 cursor-pointer disabled:opacity-50"
                  >
                    <Users className="size-3.5 text-cyan-600 dark:text-cyan-300" />
                    <span>فهرست بیمه‌شدگان</span>
                  </button>
                )}

                {state.category === "بیمه کارکنان" && (
                  <>
                    <button type="button" onClick={() => void run("insurance_workshops")} disabled={busyAction !== null}
                      className="glass-pill rounded-xl px-3 py-2 text-xs font-medium text-foreground disabled:opacity-50">
                      کارگاه‌های بیمه
                    </button>
                    <button type="button" onClick={() => void run("insurance_employee_profiles")} disabled={busyAction !== null}
                      className="glass-pill rounded-xl px-3 py-2 text-xs font-medium text-foreground disabled:opacity-50">
                      اطلاعات بیمه‌ای کارکنان
                    </button>
                    <button type="button" onClick={() => void run("insurance_lists")} disabled={busyAction !== null}
                      className="glass-pill rounded-xl px-3 py-2 text-xs font-medium text-foreground disabled:opacity-50">
                      لیست‌های ماهانه بیمه
                    </button>
                    <button type="button" onClick={() => setInsurancePreviewOpen(v => !v)}
                      className="glass-pill rounded-xl px-3 py-2 text-xs font-medium text-foreground">
                      محاسبه آزمایشی بیمه
                    </button>
                  </>
                )}

                {state.category === "ارزش افزوده" && (
                  <button
                    type="button"
                    onClick={() => setCompareOpen((v) => !v)}
                    className="glass-pill inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-medium hover:bg-white/80 dark:hover:bg-white/15 cursor-pointer"
                  >
                    <FileSpreadsheet className="size-3.5 text-emerald-600 dark:text-emerald-300" />
                    <span>مقایسه فاکتورها با سامانه</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => void run("open_portal")}
                  disabled={busyAction !== null}
                  className="glass-pill inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-medium hover:bg-white/80 dark:hover:bg-white/15 cursor-pointer disabled:opacity-50"
                >
                  <ExternalLink className="size-3.5 text-rose-600 dark:text-rose-300" />
                  <span>درگاه رسمی</span>
                </button>
              </div>

              {state.category === "بیمه کارکنان" && insurancePreviewOpen && (
                <InsurancePreview calculate={(values) => call<Record<string, number | string>>("insurance_calculate", values)} />
              )}

              {/* Inline VAT Invoice Comparison tool */}
              {compareOpen && state.category === "ارزش افزوده" && (
                <form
                  onSubmit={(e) => void handleCompareInvoices(e)}
                  className="glass-subtle space-y-3 rounded-2xl border p-4"
                >
                  <p className="text-xs font-bold text-foreground">
                    جمع فاکتورهای ثبت‌شده و مقایسه با سامانه
                  </p>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <input
                      type="text"
                      placeholder="از تاریخ (مثلاً 1404/01/01)"
                      value={compareStart}
                      onChange={(e) => setCompareStart(e.target.value)}
                      className="glass-pill rounded-xl px-3 py-1.5 text-xs text-foreground outline-none"
                    />
                    <input
                      type="text"
                      placeholder="تا تاریخ (مثلاً 1404/03/31)"
                      value={compareEnd}
                      onChange={(e) => setCompareEnd(e.target.value)}
                      className="glass-pill rounded-xl px-3 py-1.5 text-xs text-foreground outline-none"
                    />
                    <input
                      type="text"
                      placeholder="مالیات فروش در سامانه (اختیاری)"
                      value={portalSales}
                      onChange={(e) => setPortalSales(e.target.value)}
                      className="glass-pill rounded-xl px-3 py-1.5 text-xs text-foreground outline-none"
                    />
                    <input
                      type="text"
                      placeholder="مالیات خرید در سامانه (اختیاری)"
                      value={portalPurchase}
                      onChange={(e) => setPortalPurchase(e.target.value)}
                      className="glass-pill rounded-xl px-3 py-1.5 text-xs text-foreground outline-none"
                    />
                  </div>
                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={busyAction !== null}
                      className="rounded-xl bg-primary px-3.5 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90 cursor-pointer disabled:opacity-50"
                    >
                      محاسبه و مقایسه
                    </button>
                  </div>

                  {compareResult && (
                    <div className="space-y-2 pt-2">
                      <p className="text-[11px] text-muted-foreground">
                        بازه: {compareResult.start} تا {compareResult.end} •
                        ردشده: {compareResult.skipped}
                      </p>
                      <div className="overflow-x-auto rounded-xl border border-white/30 dark:border-white/10">
                        <table className="w-full text-right text-xs">
                          <thead className="bg-white/50 dark:bg-white/5">
                            <tr>
                              <th className="px-2.5 py-2">نوع</th>
                              <th className="px-2.5 py-2">تعداد</th>
                              <th className="px-2.5 py-2">پایه</th>
                              <th className="px-2.5 py-2">مالیات</th>
                              <th className="px-2.5 py-2">جمع</th>
                            </tr>
                          </thead>
                          <tbody>
                            {compareResult.rows.map((r) => (
                              <tr
                                key={r.label}
                                className="border-t border-white/25 dark:border-white/10"
                              >
                                <td className="px-2.5 py-1.5 font-medium">
                                  {r.label}
                                </td>
                                <td className="px-2.5 py-1.5 tabular-nums">
                                  {r.count}
                                </td>
                                <td className="px-2.5 py-1.5 tabular-nums">
                                  {r.base}
                                </td>
                                <td className="px-2.5 py-1.5 tabular-nums">
                                  {r.tax}
                                </td>
                                <td className="px-2.5 py-1.5 tabular-nums">
                                  {r.total}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div className="flex flex-wrap gap-3 text-xs font-medium">
                        <span>خالص مالیات فروش: {compareResult.sales_tax}</span>
                        <span>
                          خالص مالیات خرید: {compareResult.purchase_tax}
                        </span>
                        {compareResult.diff_sales && (
                          <span>اختلاف فروش: {compareResult.diff_sales}</span>
                        )}
                        {compareResult.diff_purchase && (
                          <span>
                            اختلاف خرید: {compareResult.diff_purchase}
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </form>
              )}
            </div>

            {/* Modal Footer: Primary «تکمیل» Button */}
            <div className="flex items-center justify-between gap-3 border-t border-white/30 bg-white/40 px-6 py-3.5 dark:border-white/10 dark:bg-slate-900/45">
              <button
                type="button"
                onClick={() => setSelectedStepIndex(null)}
                className="glass-pill rounded-xl px-4 py-2 text-xs font-medium text-slate-700 hover:bg-white/80 dark:text-slate-200 dark:hover:bg-white/15 cursor-pointer"
              >
                بستن
              </button>

              {state.selected_case && state.can_edit && (
                <button
                  type="button"
                  data-tax-complete-button="true"
                  disabled={busyAction !== null}
                  onClick={() =>
                    void handleCompleteStep(selectedStepIndex, !activeStep.done)
                  }
                  className={`inline-flex items-center gap-2 rounded-xl px-5 py-2 text-xs font-bold shadow-sm transition-all cursor-pointer disabled:opacity-50 ${
                    activeStep.done
                      ? "border border-emerald-400/70 bg-emerald-100/80 text-emerald-900 hover:bg-emerald-200/80 dark:border-emerald-500/40 dark:bg-emerald-500/20 dark:text-emerald-100"
                      : "bg-emerald-600 text-white hover:bg-emerald-700 shadow-emerald-600/30"
                  }`}
                >
                  <Check className="size-4 stroke-[2.5]" />
                  <span>{activeStep.done ? "لغو تکمیل" : "تکمیل"}</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
