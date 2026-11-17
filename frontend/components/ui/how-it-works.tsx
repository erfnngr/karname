"use client";

import React from "react";
import { LazyMotion, domAnimation, m } from "motion/react";
import { Check, ChevronLeft } from "lucide-react";

export type StepColorTheme =
  | "sky"
  | "amber"
  | "violet"
  | "rose"
  | "cyan"
  | "indigo"
  | "emerald"
  | "orange"
  | "blue"
  | "purple";

interface CardProps {
  index: number;
  number: string;
  title: string;
  description: string;
  done?: boolean;
  isNext?: boolean;
  isActive?: boolean;
  colorTheme?: StepColorTheme;
  className?: string;
  style?: React.CSSProperties;
  rotate?: string;
  colors?: {
    bg: string;
    text: string;
    border: string;
  };
  onClick?: () => void;
}

const Pin = ({ className }: { className?: string }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="currentColor"
    className={className}
    aria-hidden="true"
  >
    <path stroke="none" d="M0 0h24v24H0z" fill="none" />
    <path d="M16 3a1 1 0 0 1 .117 1.993l-.117 .007v4.764l1.894 3.789a1 1 0 0 1 .1 .331l.006 .116v2a1 1 0 0 1 -.883 .993l-.117 .007h-4v4a1 1 0 0 1 -1.993 .117l-.007 -.117v-4h-4a1 1 0 0 1 -.993 -.883l-.007 -.117v-2a1 1 0 0 1 .06 -.34l.046 -.107l1.894 -3.791v-4.762a1 1 0 0 1 -.117 -1.993l.117 -.007h8z" />
  </svg>
);

const COLOR_PALETTE: Record<
  StepColorTheme,
  {
    outer: string;
    inner: string;
    text: string;
    badge: string;
    glow: string;
  }
> = {
  sky: {
    outer:
      "border-white/80 bg-white/75 shadow-[0_14px_34px_-12px_rgba(14,165,233,0.28)] dark:border-sky-300/20 dark:bg-slate-900/65 dark:shadow-[0_18px_36px_-14px_rgba(0,0,0,0.65)]",
    inner:
      "bg-gradient-to-br from-sky-100/85 via-cyan-50/75 to-white/70 border-sky-200/90 dark:from-sky-500/20 dark:via-cyan-500/12 dark:to-slate-900/40 dark:border-sky-400/30",
    text: "text-sky-600 dark:text-sky-300",
    badge:
      "bg-sky-500/15 text-sky-700 border-sky-300/60 dark:bg-sky-400/20 dark:text-sky-200 dark:border-sky-400/30",
    glow: "ring-2 ring-sky-400/60 dark:ring-sky-300/50",
  },
  amber: {
    outer:
      "border-white/80 bg-white/75 shadow-[0_14px_34px_-12px_rgba(245,158,11,0.28)] dark:border-amber-300/20 dark:bg-slate-900/65 dark:shadow-[0_18px_36px_-14px_rgba(0,0,0,0.65)]",
    inner:
      "bg-gradient-to-br from-amber-100/85 via-orange-50/75 to-white/70 border-amber-200/90 dark:from-amber-500/20 dark:via-orange-500/12 dark:to-slate-900/40 dark:border-amber-400/30",
    text: "text-amber-600 dark:text-amber-300",
    badge:
      "bg-amber-500/15 text-amber-800 border-amber-300/60 dark:bg-amber-400/20 dark:text-amber-200 dark:border-amber-400/30",
    glow: "ring-2 ring-amber-400/60 dark:ring-amber-300/50",
  },
  violet: {
    outer:
      "border-white/80 bg-white/75 shadow-[0_14px_34px_-12px_rgba(139,92,246,0.28)] dark:border-violet-300/20 dark:bg-slate-900/65 dark:shadow-[0_18px_36px_-14px_rgba(0,0,0,0.65)]",
    inner:
      "bg-gradient-to-br from-violet-100/85 via-fuchsia-50/75 to-white/70 border-violet-200/90 dark:from-violet-500/20 dark:via-fuchsia-500/12 dark:to-slate-900/40 dark:border-violet-400/30",
    text: "text-violet-600 dark:text-violet-300",
    badge:
      "bg-violet-500/15 text-violet-700 border-violet-300/60 dark:bg-violet-400/20 dark:text-violet-200 dark:border-violet-400/30",
    glow: "ring-2 ring-violet-400/60 dark:ring-violet-300/50",
  },
  rose: {
    outer:
      "border-white/80 bg-white/75 shadow-[0_14px_34px_-12px_rgba(244,63,94,0.26)] dark:border-rose-300/20 dark:bg-slate-900/65 dark:shadow-[0_18px_36px_-14px_rgba(0,0,0,0.65)]",
    inner:
      "bg-gradient-to-br from-rose-100/85 via-pink-50/75 to-white/70 border-rose-200/90 dark:from-rose-500/20 dark:via-pink-500/12 dark:to-slate-900/40 dark:border-rose-400/30",
    text: "text-rose-600 dark:text-rose-300",
    badge:
      "bg-rose-500/15 text-rose-700 border-rose-300/60 dark:bg-rose-400/20 dark:text-rose-200 dark:border-rose-400/30",
    glow: "ring-2 ring-rose-400/60 dark:ring-rose-300/50",
  },
  cyan: {
    outer:
      "border-white/80 bg-white/75 shadow-[0_14px_34px_-12px_rgba(6,182,212,0.26)] dark:border-cyan-300/20 dark:bg-slate-900/65 dark:shadow-[0_18px_36px_-14px_rgba(0,0,0,0.65)]",
    inner:
      "bg-gradient-to-br from-cyan-100/85 via-teal-50/75 to-white/70 border-cyan-200/90 dark:from-cyan-500/20 dark:via-teal-500/12 dark:to-slate-900/40 dark:border-cyan-400/30",
    text: "text-cyan-600 dark:text-cyan-300",
    badge:
      "bg-cyan-500/15 text-cyan-700 border-cyan-300/60 dark:bg-cyan-400/20 dark:text-cyan-200 dark:border-cyan-400/30",
    glow: "ring-2 ring-cyan-400/60 dark:ring-cyan-300/50",
  },
  indigo: {
    outer:
      "border-white/80 bg-white/75 shadow-[0_14px_34px_-12px_rgba(99,102,241,0.28)] dark:border-indigo-300/20 dark:bg-slate-900/65 dark:shadow-[0_18px_36px_-14px_rgba(0,0,0,0.65)]",
    inner:
      "bg-gradient-to-br from-indigo-100/85 via-blue-50/75 to-white/70 border-indigo-200/90 dark:from-indigo-500/20 dark:via-blue-500/12 dark:to-slate-900/40 dark:border-indigo-400/30",
    text: "text-indigo-600 dark:text-indigo-300",
    badge:
      "bg-indigo-500/15 text-indigo-700 border-indigo-300/60 dark:bg-indigo-400/20 dark:text-indigo-200 dark:border-indigo-400/30",
    glow: "ring-2 ring-indigo-400/60 dark:ring-indigo-300/50",
  },
  emerald: {
    outer:
      "border-emerald-300/90 bg-emerald-50/88 shadow-[0_14px_34px_-12px_rgba(16,185,129,0.3)] dark:border-emerald-400/40 dark:bg-emerald-950/60 dark:shadow-[0_18px_36px_-14px_rgba(0,0,0,0.65)]",
    inner:
      "bg-gradient-to-br from-emerald-100/90 via-green-50/85 to-emerald-50/75 border-emerald-300/90 dark:from-emerald-500/22 dark:via-green-500/16 dark:to-emerald-950/50 dark:border-emerald-400/40",
    text: "text-emerald-600 dark:text-emerald-300",
    badge:
      "bg-emerald-500/20 text-emerald-800 border-emerald-400/70 dark:bg-emerald-400/25 dark:text-emerald-100 dark:border-emerald-400/45",
    glow: "ring-2 ring-emerald-400/70 dark:ring-emerald-400/55",
  },
  orange: {
    outer:
      "border-white/80 bg-white/75 shadow-[0_14px_34px_-12px_rgba(249,115,22,0.28)] dark:border-orange-300/20 dark:bg-slate-900/65 dark:shadow-[0_18px_36px_-14px_rgba(0,0,0,0.65)]",
    inner:
      "bg-gradient-to-br from-orange-100/85 via-amber-50/75 to-white/70 border-orange-200/90 dark:from-orange-500/20 dark:via-amber-500/12 dark:to-slate-900/40 dark:border-orange-400/30",
    text: "text-orange-600 dark:text-orange-300",
    badge:
      "bg-orange-500/15 text-orange-800 border-orange-300/60 dark:bg-orange-400/20 dark:text-orange-200 dark:border-orange-400/30",
    glow: "ring-2 ring-orange-400/60 dark:ring-orange-300/50",
  },
  blue: {
    outer:
      "border-white/80 bg-white/75 shadow-[0_14px_34px_-12px_rgba(59,130,246,0.28)] dark:border-blue-300/20 dark:bg-slate-900/65 dark:shadow-[0_18px_36px_-14px_rgba(0,0,0,0.65)]",
    inner:
      "bg-gradient-to-br from-blue-100/85 via-sky-50/75 to-white/70 border-blue-200/90 dark:from-blue-500/20 dark:via-sky-500/12 dark:to-slate-900/40 dark:border-blue-400/30",
    text: "text-blue-600 dark:text-blue-300",
    badge:
      "bg-blue-500/15 text-blue-700 border-blue-300/60 dark:bg-blue-400/20 dark:text-blue-200 dark:border-blue-400/30",
    glow: "ring-2 ring-blue-400/60 dark:ring-blue-300/50",
  },
  purple: {
    outer:
      "border-white/80 bg-white/75 shadow-[0_14px_34px_-12px_rgba(168,85,247,0.28)] dark:border-purple-300/20 dark:bg-slate-900/65 dark:shadow-[0_18px_36px_-14px_rgba(0,0,0,0.65)]",
    inner:
      "bg-gradient-to-br from-purple-100/85 via-violet-50/75 to-white/70 border-purple-200/90 dark:from-purple-500/20 dark:via-violet-500/12 dark:to-slate-900/40 dark:border-purple-400/30",
    text: "text-purple-600 dark:text-purple-300",
    badge:
      "bg-purple-500/15 text-purple-700 border-purple-300/60 dark:bg-purple-400/20 dark:text-purple-200 dark:border-purple-400/30",
    glow: "ring-2 ring-purple-400/60 dark:ring-purple-300/50",
  },
};

const CYCLE_THEMES: StepColorTheme[] = [
  "sky",
  "amber",
  "violet",
  "rose",
  "cyan",
  "indigo",
];

const formatPersianStepNumber = (index: number) => {
  const num = index + 1;
  const fa = num.toLocaleString("fa-IR");
  return num < 10 ? `۰${fa}` : fa;
};

const Card = ({
  index,
  number,
  title,
  description,
  done = false,
  isNext = false,
  isActive = false,
  colorTheme = "sky",
  className = "",
  style,
  rotate = "",
  colors: customColors,
  onClick,
}: CardProps) => {
  const resolvedTheme: StepColorTheme = done ? "emerald" : colorTheme;
  const palette = COLOR_PALETTE[resolvedTheme] || COLOR_PALETTE.sky;
  const innerBg = customColors?.bg && !done ? customColors.bg : palette.inner;
  const textColor =
    customColors?.text && !done ? customColors.text : palette.text;
  const innerBorder =
    customColors?.border && !done ? customColors.border : "";

  return (
    <button
      type="button"
      dir="rtl"
      data-tax-step-index={index}
      data-tax-step-done={done ? "true" : "false"}
      onClick={onClick}
      style={style}
      className={`group relative w-full text-right md:w-[300px] cursor-pointer focus:outline-none transition-all duration-300 hover:z-30 hover:scale-[1.03] hover:rotate-0 ${rotate} ${className}`}
    >
      <div
        className={`rounded-[26px] border p-2.5 backdrop-blur-xl transition-all duration-300 ${palette.outer} ${
          isActive || isNext ? palette.glow : ""
        }`}
      >
        <div className="mb-2.5 flex items-center justify-between px-2 pt-0.5">
          <span
            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${palette.badge}`}
          >
            {done ? (
              <>
                <Check className="size-3.5 stroke-[2.5]" />
                <span>تکمیل شد</span>
              </>
            ) : isNext ? (
              <span>مرحله جاری</span>
            ) : (
              <span>مشاهده کارها</span>
            )}
          </span>
          <Pin
            className={`h-7 w-7 ${textColor} transition-transform duration-300 group-hover:-translate-y-0.5`}
          />
          <span className="inline-flex size-6 items-center justify-center rounded-full bg-white/50 text-slate-600 transition-transform duration-300 group-hover:-translate-x-0.5 dark:bg-white/10 dark:text-slate-300">
            <ChevronLeft className="size-3.5" />
          </span>
        </div>

        <div
          className={`relative flex min-h-[168px] flex-col justify-between overflow-hidden rounded-[17px] border p-4 backdrop-blur-md transition-colors duration-300 ${innerBg} ${innerBorder}`}
        >
          <div className="mb-2.5 flex items-start justify-between gap-2">
            <span
              className={`${textColor} text-3xl font-extrabold leading-none tracking-tight tabular-nums`}
            >
              {number}
            </span>
            {done && (
              <span
                aria-label="تکمیل‌شده"
                className="flex size-8 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white shadow-sm shadow-emerald-500/40"
              >
                <Check className="size-4 stroke-[2.75]" />
              </span>
            )}
          </div>

          <div className="space-y-1.5 text-right">
            <h3 className="text-base font-bold leading-snug text-slate-900 dark:text-slate-50">
              {title}
            </h3>
            <p className="line-clamp-3 text-xs leading-6 text-slate-700 dark:text-slate-200/85">
              {description}
            </p>
          </div>
        </div>
      </div>
    </button>
  );
};

export interface Step {
  title: string;
  description: string;
  done?: boolean;
  isNext?: boolean;
  colorTheme?: StepColorTheme;
  colors?: {
    bg: string;
    text: string;
    border: string;
  };
}

export interface StepPosition {
  className?: string;
  rotate?: string;
}

export interface HowItWorksProps {
  steps?: Step[];
  features?: Step[];
  className?: string;
  stepPositions?: StepPosition[];
  activeStepIndex?: number | null;
  onStepClick?: (index: number) => void;
}

function computeDesktopLayout(count: number) {
  const coords = Array.from({ length: count }, (_, index) => {
    const pair = Math.floor(index / 2);
    const isRight = index % 2 === 0;
    const topPx = pair * 315 + (isRight ? 16 : 148);
    // Card width is 300px inside max-w-[980px] container
    // Anchor right cards near 8% from right edge, left cards near 8% from left edge
    const sideOffsetPct = pair % 2 === 1 ? "10%" : "7%";
    const style: React.CSSProperties = isRight
      ? { top: `${topPx}px`, right: sideOffsetPct }
      : { top: `${topPx}px`, left: sideOffsetPct };
    const rotate = isRight ? "md:-rotate-2" : "md:rotate-2";
    // SVG normalized X (viewBox 0..1000) & pixel Y at card visual center
    const svgX = isRight ? (pair % 2 === 1 ? 745 : 775) : pair % 2 === 1 ? 255 : 225;
    const svgY = topPx + 128;
    return { style, rotate, topPx, svgX, svgY };
  });

  const lastTop = count > 0 ? coords[count - 1].topPx : 0;
  const height = Math.max(380, lastTop + 285);
  return { coords, height };
}

export default function HowItWorks({
  steps,
  features,
  className = "",
  activeStepIndex = null,
  onStepClick,
}: HowItWorksProps) {
  const data =
    steps && steps.length > 0
      ? steps
      : features && features.length > 0
      ? features
      : [];

  const firstPendingIndex = data.findIndex((s) => !s.done);
  const { coords, height } = computeDesktopLayout(data.length);

  if (data.length === 0) {
    return (
      <div
        dir="rtl"
        className={`flex min-h-[280px] items-center justify-center rounded-3xl border border-dashed border-slate-300/70 bg-white/40 p-8 text-center backdrop-blur-md dark:border-white/15 dark:bg-slate-900/40 ${className}`}
      >
        <p className="text-sm text-slate-600 dark:text-slate-300">
          برای این بخش مالیاتی هنوز مرحله‌ای تعریف نشده است.
        </p>
      </div>
    );
  }

  return (
    <LazyMotion features={domAnimation}>
      <div className={`relative py-6 px-3 sm:px-6 ${className}`}>
        {/* Subtle ruled blueprint lines adapted for glass surfaces */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.06] dark:opacity-0"
          style={{
            backgroundImage: "linear-gradient(#0f172a 1px, transparent 1px)",
            backgroundSize: "100% 34px",
          }}
        />
        <div
          className="pointer-events-none absolute inset-0 opacity-0 dark:opacity-[0.09]"
          style={{
            backgroundImage: "linear-gradient(#e2e8f0 1px, transparent 1px)",
            backgroundSize: "100% 34px",
          }}
        />

        <div className="relative z-10 mx-auto max-w-5xl">
          {/* Coordinate canvas uses dir="ltr" so right/left offsets and SVG viewBox match 1:1, while each card uses dir="rtl" */}
          <div
            dir="ltr"
            className="relative mx-auto flex h-auto w-full max-w-[980px] flex-col items-center gap-0 md:block md:h-[var(--md-height)]"
            style={{ "--md-height": `${height}px` } as React.CSSProperties}
          >
            {data.length > 1 && (
              <svg
                className="pointer-events-none absolute inset-0 z-0 hidden h-full w-full md:block"
                viewBox={`0 0 1000 ${height}`}
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                {data.slice(0, -1).map((step, index) => {
                  const p1 = coords[index];
                  const p2 = coords[index + 1];
                  const dx = (p2.svgX - p1.svgX) * 0.45;
                  const pathD = `M ${p1.svgX} ${p1.svgY} C ${p1.svgX + dx} ${
                    p1.svgY + 18
                  }, ${p2.svgX - dx} ${p2.svgY - 18}, ${p2.svgX} ${p2.svgY}`;
                  const segmentDone = Boolean(step.done);
                  return (
                    <m.path
                      key={`connector-${index}`}
                      d={pathD}
                      stroke="currentColor"
                      className={
                        segmentDone
                          ? "text-emerald-500/75 dark:text-emerald-400/65"
                          : "text-sky-500/55 dark:text-sky-300/40"
                      }
                      strokeWidth="2.5"
                      strokeDasharray="8 6"
                      fill="none"
                      strokeLinecap="round"
                      vectorEffect="non-scaling-stroke"
                      initial={{ strokeDashoffset: 0 }}
                      animate={{ strokeDashoffset: -140 }}
                      transition={{
                        duration: 3.2,
                        repeat: Infinity,
                        ease: "linear",
                      }}
                    />
                  );
                })}
              </svg>
            )}

            {data.map((step, index) => {
              const pos = coords[index];
              const theme =
                step.colorTheme || CYCLE_THEMES[index % CYCLE_THEMES.length];
              const isNext =
                typeof step.isNext === "boolean"
                  ? step.isNext
                  : !step.done && index === firstPendingIndex;

              return (
                <React.Fragment key={`${index}-${step.title}`}>
                  <Card
                    index={index}
                    number={formatPersianStepNumber(index)}
                    title={step.title}
                    description={step.description}
                    done={step.done}
                    isNext={isNext}
                    isActive={activeStepIndex === index}
                    colorTheme={theme}
                    colors={step.colors}
                    rotate={pos.rotate}
                    style={pos.style}
                    className="md:absolute z-10"
                    onClick={() => onStepClick?.(index)}
                  />
                  {/* Mobile vertical dashed connector between stacked cards */}
                  {index < data.length - 1 && (
                    <div
                      aria-hidden="true"
                      className={`my-1 h-8 w-0.5 border-l-2 border-dashed md:hidden ${
                        step.done
                          ? "border-emerald-500/70 dark:border-emerald-400/60"
                          : "border-sky-400/70 dark:border-sky-300/45"
                      }`}
                    />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>
    </LazyMotion>
  );
}
