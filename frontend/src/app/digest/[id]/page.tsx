"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useLanguage } from "@/contexts/LanguageContext";
import api from "@/lib/api";
import type { TranslationKey } from "@/lib/translations";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type NewsSource = {
  title: string;
  outlet: string;
  url: string;
  date: string;
};

type NewsEnrichment = {
  analysis: string;
  sources: NewsSource[];
};

type DeputyReport = {
  type: "deputy";
  politician_id: number;
  name: string;
  short_name: string;
  party: string;
  state: string;
  photo_url: string | null;
  key_numbers: { votes: number; speeches: number; bills_authored: number };
  intro_paragraph: string;
  long_text: string;
  news_enrichment: NewsEnrichment | null;
};

type BillReport = {
  type: "bill";
  bill_id: number;
  label: string;
  title: string;
  ementa: string;
  bill_type: string;
  number: number;
  year: number;
  presented_at: string;
  author: string;
  status: string;
  intro_paragraph: string;
  long_summary: string;
  news_enrichment: NewsEnrichment | null;
};

type Report = DeputyReport | BillReport;

type DigestContent = {
  reports: Report[];
  date_range: { start: string; end: string };
  language: string;
  model: string;
  enrichment: boolean;
  errors: string[];
};

type DigestRecord = {
  id: string;
  label: string;
  status: "processing" | "completed" | "failed";
  content: DigestContent | null;
  estimated_cost_usd: number | null;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
  });
}

function reportAnchor(r: Report) {
  return r.type === "deputy"
    ? `dep-${r.politician_id}`
    : `bill-${r.bill_id}`;
}

function reportTitle(r: Report) {
  return r.type === "deputy"
    ? `${r.short_name} (${r.party}-${r.state})`
    : r.label;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function KeyNumberCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center px-4 py-2 bg-muted rounded-lg">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-muted-foreground mt-0.5">{label}</div>
    </div>
  );
}

function NewsSection({ enrichment, t }: { enrichment: NewsEnrichment; t: (k: TranslationKey) => string }) {
  return (
    <div className="mt-6 border-t pt-5">
      <h4 className="font-semibold text-sm mb-2">{t("digest.report_news")}</h4>
      <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-line">
        {enrichment.analysis}
      </p>
      {enrichment.sources.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-muted-foreground mb-1">{t("digest.report_sources")}</p>
          <ul className="space-y-1">
            {enrichment.sources.map((s, i) => (
              <li key={i} className="text-xs">
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  {s.title}
                </a>
                <span className="text-muted-foreground ml-1">— {s.outlet}, {s.date}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function DeputyCard({ report, t }: { report: DeputyReport; t: (k: TranslationKey) => string }) {
  return (
    <section id={`dep-${report.politician_id}`} className="scroll-mt-20">
      {/* Header */}
      <div className="flex items-center gap-4 mb-4">
        {report.photo_url ? (
          <img
            src={report.photo_url}
            alt={report.name}
            className="w-16 h-16 rounded-full object-cover border flex-shrink-0"
          />
        ) : (
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center text-xl font-bold text-muted-foreground flex-shrink-0">
            {report.short_name.charAt(0)}
          </div>
        )}
        <div>
          <h2 className="text-xl font-bold">{report.name}</h2>
          <p className="text-sm text-muted-foreground">
            {report.party} · {report.state} ·{" "}
            <Link href={`/politico/${report.politician_id}`} className="text-primary hover:underline">
              ver perfil →
            </Link>
          </p>
        </div>
      </div>

      {/* Key numbers */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <KeyNumberCard label={t("digest.report_votes")} value={report.key_numbers.votes} />
        <KeyNumberCard label={t("digest.report_speeches")} value={report.key_numbers.speeches} />
        <KeyNumberCard label={t("digest.report_bills_authored")} value={report.key_numbers.bills_authored} />
      </div>

      {/* Intro */}
      <p className="text-sm leading-relaxed text-muted-foreground mb-4">{report.intro_paragraph}</p>

      {/* Long text */}
      <div className="text-sm leading-relaxed whitespace-pre-line">{report.long_text}</div>

      {/* News enrichment */}
      {report.news_enrichment && (
        <NewsSection enrichment={report.news_enrichment} t={t} />
      )}
    </section>
  );
}

function BillCard({ report, t }: { report: BillReport; t: (k: TranslationKey) => string }) {
  return (
    <section id={`bill-${report.bill_id}`} className="scroll-mt-20">
      {/* Header */}
      <div className="mb-4">
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <h2 className="text-xl font-bold">{report.label}</h2>
          {report.status && (
            <span className="text-xs border rounded-full px-2 py-0.5 text-muted-foreground">
              {report.status}
            </span>
          )}
        </div>
        <p className="text-sm text-muted-foreground line-clamp-3">{report.ementa}</p>
        <p className="text-xs text-muted-foreground mt-1">
          Autor: {report.author}
          {report.presented_at && ` · Apresentado em: ${report.presented_at}`}
        </p>
        <Link href={`/proposicao/${report.bill_id}`} className="text-xs text-primary hover:underline">
          ver proposição →
        </Link>
      </div>

      {/* Intro */}
      <p className="text-sm leading-relaxed text-muted-foreground mb-4">{report.intro_paragraph}</p>

      {/* Long summary */}
      <div className="text-sm leading-relaxed whitespace-pre-line">{report.long_summary}</div>

      {/* News enrichment */}
      {report.news_enrichment && (
        <NewsSection enrichment={report.news_enrichment} t={t} />
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Table of Contents
// ---------------------------------------------------------------------------

function TableOfContents({
  reports,
  t,
  activeId,
}: {
  reports: Report[];
  t: (k: TranslationKey) => string;
  activeId: string;
}) {
  return (
    <nav className="sticky top-20 w-56 flex-shrink-0 hidden lg:block">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
        {t("digest.report_toc")}
      </p>
      <ul className="space-y-1">
        {reports.map((r) => {
          const anchor = reportAnchor(r);
          const active = activeId === anchor;
          return (
            <li key={anchor}>
              <a
                href={`#${anchor}`}
                className={`block text-xs py-1 px-2 rounded transition-colors truncate ${
                  active
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <span className="text-[10px] uppercase mr-1 opacity-60">
                  {r.type === "deputy" ? "Dep" : "PL"}
                </span>
                {reportTitle(r)}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// PDF Export
// ---------------------------------------------------------------------------

function buildPdfHtml(digest: DigestRecord): string {
  const content = digest.content!;
  const reports = content.reports;

  const reportHtml = reports.map((r) => {
    if (r.type === "deputy") {
      const photo = r.photo_url
        ? `<img src="${r.photo_url}" style="width:60px;height:60px;border-radius:50%;object-fit:cover;border:1px solid #e5e7eb;flex-shrink:0;" />`
        : `<div style="width:60px;height:60px;border-radius:50%;background:#f3f4f6;display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:bold;color:#9ca3af;flex-shrink:0;">${r.short_name.charAt(0)}</div>`;

      const newsHtml = r.news_enrichment
        ? `<div style="margin-top:20px;border-top:1px solid #e5e7eb;padding-top:16px;">
            <h4 style="font-size:13px;font-weight:600;margin-bottom:8px;">Cobertura jornalística</h4>
            <p style="font-size:13px;color:#374151;line-height:1.6;">${r.news_enrichment.analysis}</p>
            ${r.news_enrichment.sources.length > 0 ? `<ul style="margin-top:8px;font-size:12px;color:#6b7280;">${r.news_enrichment.sources.map((s) => `<li><a href="${s.url}" style="color:#2563eb;">${s.title}</a> — ${s.outlet}, ${s.date}</li>`).join("")}</ul>` : ""}
          </div>`
        : "";

      return `<section style="margin-bottom:40px;padding-bottom:40px;border-bottom:1px solid #e5e7eb;">
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;">
          ${photo}
          <div>
            <h2 style="font-size:20px;font-weight:700;margin:0;">${r.name}</h2>
            <p style="font-size:13px;color:#6b7280;margin:4px 0 0;">${r.party} · ${r.state}</p>
          </div>
        </div>
        <div style="display:flex;gap:12px;margin-bottom:16px;">
          <div style="text-align:center;padding:8px 16px;background:#f3f4f6;border-radius:8px;">
            <div style="font-size:22px;font-weight:700;">${r.key_numbers.votes}</div>
            <div style="font-size:11px;color:#6b7280;">Votações</div>
          </div>
          <div style="text-align:center;padding:8px 16px;background:#f3f4f6;border-radius:8px;">
            <div style="font-size:22px;font-weight:700;">${r.key_numbers.speeches}</div>
            <div style="font-size:11px;color:#6b7280;">Discursos</div>
          </div>
          <div style="text-align:center;padding:8px 16px;background:#f3f4f6;border-radius:8px;">
            <div style="font-size:22px;font-weight:700;">${r.key_numbers.bills_authored}</div>
            <div style="font-size:11px;color:#6b7280;">Projetos</div>
          </div>
        </div>
        <p style="font-size:13px;color:#6b7280;line-height:1.6;margin-bottom:12px;">${r.intro_paragraph}</p>
        <p style="font-size:13px;line-height:1.7;white-space:pre-line;">${r.long_text}</p>
        ${newsHtml}
      </section>`;
    } else {
      const newsHtml = r.news_enrichment
        ? `<div style="margin-top:20px;border-top:1px solid #e5e7eb;padding-top:16px;">
            <h4 style="font-size:13px;font-weight:600;margin-bottom:8px;">Cobertura jornalística</h4>
            <p style="font-size:13px;color:#374151;line-height:1.6;">${r.news_enrichment.analysis}</p>
            ${r.news_enrichment.sources.length > 0 ? `<ul style="margin-top:8px;font-size:12px;color:#6b7280;">${r.news_enrichment.sources.map((s) => `<li><a href="${s.url}" style="color:#2563eb;">${s.title}</a> — ${s.outlet}, ${s.date}</li>`).join("")}</ul>` : ""}
          </div>`
        : "";

      return `<section style="margin-bottom:40px;padding-bottom:40px;border-bottom:1px solid #e5e7eb;">
        <div style="margin-bottom:16px;">
          <h2 style="font-size:20px;font-weight:700;margin:0 0 4px;">${r.label}</h2>
          <p style="font-size:12px;color:#6b7280;margin:0 0 4px;">${r.ementa}</p>
          <p style="font-size:12px;color:#6b7280;margin:0;">Autor: ${r.author}${r.presented_at ? ` · Apresentado em: ${r.presented_at}` : ""}</p>
        </div>
        <p style="font-size:13px;color:#6b7280;line-height:1.6;margin-bottom:12px;">${r.intro_paragraph}</p>
        <p style="font-size:13px;line-height:1.7;white-space:pre-line;">${r.long_summary}</p>
        ${newsHtml}
      </section>`;
    }
  });

  const tocHtml = `<div style="margin-bottom:32px;padding:16px;background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;">
    <h3 style="font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;color:#6b7280;margin:0 0 12px;">Índice</h3>
    <ol style="margin:0;padding-left:20px;font-size:13px;color:#374151;">
      ${reports.map((r, i) => `<li style="margin-bottom:4px;">${reportTitle(r)}</li>`).join("")}
    </ol>
  </div>`;

  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 40px; color: #111827; }
    a { color: #2563eb; }
    @media print { body { padding: 20px; } }
  </style>
</head>
<body>
  <div style="margin-bottom:32px;border-bottom:2px solid #111827;padding-bottom:16px;">
    <h1 style="font-size:28px;font-weight:700;margin:0 0 4px;">Digest</h1>
    <p style="font-size:13px;color:#6b7280;margin:0;">${digest.label}</p>
    <p style="font-size:12px;color:#9ca3af;margin:4px 0 0;">
      Período: ${content.date_range.start} – ${content.date_range.end} ·
      Gerado em: ${digest.completed_at ? fmtDate(digest.completed_at) : "—"}
    </p>
  </div>
  ${tocHtml}
  ${reportHtml.join("")}
</body>
</html>`;
}

function downloadPdf(digest: DigestRecord) {
  const html = buildPdfHtml(digest);
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const win = window.open(url, "_blank");
  if (win) {
    win.onload = () => {
      win.print();
    };
  }
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function DigestViewPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useLanguage();

  const [digest, setDigest] = useState<DigestRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState("");

  // Polling for processing state
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;

    async function fetch() {
      try {
        const res = await api.get(`/digests/${id}`);
        setDigest(res.data);
        if (res.data.status === "processing") {
          interval = setInterval(async () => {
            const r2 = await api.get(`/digests/${id}`);
            setDigest(r2.data);
            if (r2.data.status !== "processing") clearInterval(interval);
          }, 5000);
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }

    fetch();
    return () => clearInterval(interval);
  }, [id]);

  // Intersection observer for active TOC item
  const observerRef = useRef<IntersectionObserver | null>(null);
  useEffect(() => {
    if (!digest?.content?.reports) return;
    const anchors = digest.content.reports.map(reportAnchor);
    if (observerRef.current) observerRef.current.disconnect();
    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
            break;
          }
        }
      },
      { rootMargin: "-20% 0px -60% 0px" }
    );
    anchors.forEach((a) => {
      const el = document.getElementById(a);
      if (el) observerRef.current!.observe(el);
    });
    return () => observerRef.current?.disconnect();
  }, [digest]);

  if (loading) {
    return (
      <main className="max-w-5xl mx-auto px-4 py-10">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-muted rounded w-1/3" />
          <div className="h-4 bg-muted rounded w-1/4" />
          <div className="h-40 bg-muted rounded" />
        </div>
      </main>
    );
  }

  if (!digest) {
    return (
      <main className="max-w-5xl mx-auto px-4 py-10">
        <Link href="/digest" className="text-sm text-muted-foreground hover:text-foreground">
          {t("digest.report_back")}
        </Link>
        <p className="mt-6 text-muted-foreground">{t("digest.report_not_found")}</p>
      </main>
    );
  }

  if (digest.status === "processing") {
    return (
      <main className="max-w-5xl mx-auto px-4 py-10">
        <Link href="/digest" className="text-sm text-muted-foreground hover:text-foreground">
          {t("digest.report_back")}
        </Link>
        <div className="mt-10 text-center">
          <div className="inline-block w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-muted-foreground">{t("digest.report_processing")}</p>
          <p className="text-xs text-muted-foreground mt-1">{digest.label}</p>
        </div>
      </main>
    );
  }

  if (digest.status === "failed") {
    return (
      <main className="max-w-5xl mx-auto px-4 py-10">
        <Link href="/digest" className="text-sm text-muted-foreground hover:text-foreground">
          {t("digest.report_back")}
        </Link>
        <p className="mt-6 text-destructive">{t("digest.report_failed")}</p>
        {digest.error_message && (
          <p className="text-xs text-muted-foreground mt-2">{digest.error_message}</p>
        )}
      </main>
    );
  }

  const content = digest.content!;
  const reports = content.reports;

  return (
    <main className="max-w-6xl mx-auto px-4 py-10">
      {/* Top bar */}
      <div className="flex items-start justify-between gap-4 mb-8">
        <div>
          <Link href="/digest" className="text-sm text-muted-foreground hover:text-foreground block mb-2">
            {t("digest.report_back")}
          </Link>
          <h1 className="text-2xl font-bold">{digest.label}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {t("digest.report_period")}: {content.date_range.start} – {content.date_range.end}
            {digest.completed_at && (
              <> · {t("digest.report_generated")}: {fmtDate(digest.completed_at)}</>
            )}
            {digest.estimated_cost_usd != null && (
              <> · {t("digest.estimated_cost")}: ${digest.estimated_cost_usd.toFixed(4)}</>
            )}
          </p>
        </div>
        <button
          onClick={() => downloadPdf(digest)}
          className="flex-shrink-0 text-sm border rounded-md px-4 py-2 hover:bg-muted transition-colors"
        >
          {t("digest.download_pdf")}
        </button>
      </div>

      {/* Layout: TOC + content */}
      <div className="flex gap-10">
        {/* TOC sidebar */}
        {reports.length > 1 && (
          <TableOfContents reports={reports} t={t} activeId={activeId} />
        )}

        {/* Report cards */}
        <div className="flex-1 min-w-0 space-y-12">
          {reports.map((r) =>
            r.type === "deputy" ? (
              <DeputyCard key={`dep-${r.politician_id}`} report={r} t={t} />
            ) : (
              <BillCard key={`bill-${r.bill_id}`} report={r} t={t} />
            )
          )}

          {/* Errors notice */}
          {content.errors.length > 0 && (
            <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-4 py-3">
              <p className="font-medium mb-1">Alguns itens não puderam ser processados:</p>
              <ul className="list-disc list-inside space-y-0.5">
                {content.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
