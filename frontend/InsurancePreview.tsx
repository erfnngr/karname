import React, { useState } from "react";

type Result = Record<string, number | string>;
type Props = { calculate: (values: Record<string, unknown>) => Promise<Result> };

const inputs = [
  ["period", "ماه شمسی (۱۴۰۵/۰۸)", "۱۴۰۵/۰۸"], ["days", "روزهای بیمه", ""],
  ["daily_wage", "مزد روزانه (ریال)", ""], ["daily_seniority", "سنوات روزانه (ریال)", ""],
  ["insured_benefits", "جمع مزایای مشمول (ریال)", ""], ["non_insured_benefits", "جمع مزایای غیرمشمول (ریال)", ""],
  ["minimum_daily", "حداقل روزانه مصوب (ریال)", ""], ["maximum_daily", "حداکثر روزانه مصوب (ریال)", ""],
  ["worker_rate", "نرخ سهم کارمند (درصد)", ""], ["employer_rate", "نرخ سهم کارفرما (درصد)", ""],
  ["unemployment_rate", "نرخ بیمه بیکاری (درصد)", ""], ["rules_version", "نسخه قواعد", ""],
  ["source", "منبع رسمی و تاریخ اعتبار", ""],
] as const;
const labels: [string, string][] = [
  ["monthly_wage", "مزد و سنوات"], ["seniority_total", "جمع سنوات"], ["insured_total", "جمع مشمول"],
  ["gross_total", "جمع پرداختی"], ["worker", "سهم کارمند"], ["employer", "سهم کارفرما"],
  ["unemployment", "سهم بیکاری"], ["insurance_total", "جمع حق بیمه"],
];

export function InsurancePreview({ calculate }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [approved, setApproved] = useState(false);
  const [unemployment, setUnemployment] = useState(true);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setError(""); setResult(null); setBusy(true);
    try { setResult(await calculate({ ...values, approved, unemployment_applies: unemployment })); }
    catch (err) { setError(err instanceof Error ? err.message : "محاسبه انجام نشد."); }
    finally { setBusy(false); }
  }
  return <form onSubmit={submit} className="glass-subtle space-y-3 rounded-2xl border p-4" dir="rtl">
    <h3 className="text-sm font-bold">محاسبه آزمایشی حق بیمه یک نفر</h3>
    <p className="text-xs leading-6 text-foreground/75">این محاسبه با داده‌های واردشده انجام می‌شود و هنوز به حقوق و پرونده کارکنان متصل نیست؛ خروجی یا تأیید سازمان محسوب نمی‌شود. مقادیر را برای دوره و شرایط فرد از منبع معتبر بررسی کنید.</p>
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {inputs.map(([key,label,placeholder]) => <label key={key} className="space-y-1 text-xs">
        <span className="block">{label}</span><input required value={values[key] ?? ""} placeholder={placeholder}
          inputMode={key === "source" || key === "rules_version" ? "text" : "decimal"}
          onChange={e => { setValues({...values,[key]:e.target.value}); setResult(null); setApproved(false); }}
          className="glass-pill w-full min-w-0 rounded-xl px-3 py-2 text-foreground outline-none" />
      </label>)}
    </div>
    <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={unemployment} onChange={e => {setUnemployment(e.target.checked); setResult(null);}} /> بیمه بیکاری برای این فرد اعمال شود</label>
    <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={approved} onChange={e => {setApproved(e.target.checked); setResult(null);}} /> اعتبار نرخ‌ها، حدود و منبع را برای این دوره و فرد بررسی کرده‌ام</label>
    <button disabled={!approved || busy} className="rounded-xl bg-sky-700 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50">محاسبه آزمایشی</button>
    {error && <p role="alert" className="text-xs text-red-600 dark:text-red-300">{error}</p>}
    {result && <div aria-live="polite" className="grid grid-cols-2 gap-2 text-xs">{labels.map(([key,label]) => <div key={key} className="glass-pill rounded-xl p-2"><span>{label}: </span><strong>{BigInt(result[key]).toLocaleString("fa-IR")} ریال</strong></div>)}</div>}
  </form>;
}
