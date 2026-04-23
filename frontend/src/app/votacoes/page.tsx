"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/LanguageContext";
import type { TranslationKey } from "@/lib/translations";

const API = process.env.NEXT_PUBLIC_API_URL;
const PAGE_SIZE = 50;

const SELECT_CLASS =
  "h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

// Map organ acronym to translation key (used in the AcronymHelp tooltip)
const ORGAN_KEY: Record<string, TranslationKey> = {
  PLEN:           "organ.PLEN",
  CCJC:           "organ.CCJC",
  CCOM:           "organ.CCOM",
  CSPCCO:         "organ.CSPCCO",
  CSAUDE:         "organ.CSAUDE",
  CPD:            "organ.CPD",
  "SECAP(SGM)":   "organ.SECAP_SGM",
  MESA:           "organ.MESA",
  CE:             "organ.CE",
  CAPADR:         "organ.CAPADR",
  CFFC:           "organ.CFFC",
  CCULT:          "organ.CCULT",
  CFT:            "organ.CFT",
  CVT:            "organ.CVT",
  CPASF:          "organ.CPASF",
  CMADS:          "organ.CMADS",
  CMULHER:        "organ.CMULHER",
};

// Map bill type acronym to translation key
const BILL_TYPE_KEY: Record<string, TranslationKey> = {
  PL:   "bill_type_name.PL",
  PLP:  "bill_type_name.PLP",
  PEC:  "bill_type_name.PEC",
  REQ:  "bill_type_name.REQ",
  MPV:  "bill_type_name.MPV",
  PDL:  "bill_type_name.PDL",
  TVR:  "bill_type_name.TVR",
  PRC:  "bill_type_name.PRC",
  MSC:  "bill_type_name.MSC",
  REC:  "bill_type_name.REC",
  REP:  "bill_type_name.REP",
  SAP:  "bill_type_name.SAP",
  CMC:  "bill_type_name.CMC",
  PDC:  "bill_type_name.PDC",
};

function AcronymHelp({ titleKey, keyMap }: {
  titleKey: TranslationKey;
  keyMap: Record<string, TranslationKey>;
}) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref} className="relative flex-shrink-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-5 h-5 rounded-full bg-muted border text-muted-foreground text-xs font-bold leading-none flex items-center justify-center hover:bg-muted/80 transition-colors"
        aria-label={t(titleKey)}
      >
        ?
      </button>
      {open && (
        <div className="absolute left-0 top-7 z-50 w-80 rounded-lg border border-gray-200 bg-white shadow-lg p-3">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">{t(titleKey)}</p>
          <div className="space-y-1 max-h-72 overflow-y-auto">
            {Object.entries(keyMap).map(([acronym, tKey]) => (
              <div key={acronym} className="flex gap-2 text-xs">
                <span className="font-mono font-semibold text-gray-900 w-16 flex-shrink-0">{acronym}</span>
                <span className="text-gray-600">{t(tKey)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

type Votacao = {
  id: number;
  external_id: string;
  description: string | null;
  voted_at: string | null;
  vote_type: string | null;
  result: string | null;
  session_label: string | null;
  bill_id: number | null;
  bill_title: string | null;
  bill_short_title: string | null;
  bill_ementa: string | null;
  bill_type: string | null;
  bill_number: number | null;
  bill_year: number | null;
};

function billLabel(v: Votacao) {
  if (v.bill_short_title) return v.bill_short_title;
  if (v.bill_title) return v.bill_title;
  if (v.bill_type && v.bill_number && v.bill_year)
    return `${v.bill_type} ${v.bill_number}/${v.bill_year}`;
  return v.description ?? "—";
}

export default function VotacoesPage() {
  const { t, lang } = useLanguage();
  const dateLocale = lang === "en" ? "en-GB" : "pt-BR";

  function formatDate(ts: string | null) {
    if (!ts) return "—";
    return new Date(ts).toLocaleDateString(dateLocale, { day: "2-digit", month: "2-digit", year: "numeric" });
  }

  const [items, setItems] = useState<Votacao[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [resultFilter, setResultFilter] = useState("");
  const [voteTypeFilter, setVoteTypeFilter] = useState("");
  const [sessionFilter, setSessionFilter] = useState("");
  const [billTypeFilter, setBillTypeFilter] = useState("");
  const [sessionLabels, setSessionLabels] = useState<string[]>([]);
  const [sessionOutrosCount, setSessionOutrosCount] = useState(0);
  const [billTypes, setBillTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  // Load filter options once
  useEffect(() => {
    fetch(`${API}/votes/filter-options`)
      .then((r) => r.json())
      .then((d) => {
        setSessionLabels(d.session_labels ?? []);
        setSessionOutrosCount(d.session_labels_outros_count ?? 0);
        setBillTypes(d.bill_types ?? []);
      })
      .catch(() => {});
  }, []);

  function resultBadge(result: string | null) {
    if (result === "1" || result?.toLowerCase().includes("aprovad"))
      return <Badge className="bg-green-100 text-green-800 border-green-200">{t("votes.badge_approved")}</Badge>;
    if (result === "0" || result?.toLowerCase().includes("rejeitad"))
      return <Badge className="bg-red-100 text-red-800 border-red-200">{t("votes.badge_rejected")}</Badge>;
    return <Badge variant="secondary">{result ?? "—"}</Badge>;
  }

  function voteTypeBadge(vt: string | null) {
    if (vt === "nominal")   return <Badge className="bg-blue-100 text-blue-800 border-blue-200 text-xs">{t("votes.type_nominal")}</Badge>;
    if (vt === "symbolic")  return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200 text-xs">{t("votes.type_symbolic")}</Badge>;
    return null;
  }

  useEffect(() => {
    const params = new URLSearchParams({
      source: "camara",
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (resultFilter)   params.set("result", resultFilter);
    if (voteTypeFilter) params.set("vote_type", voteTypeFilter);
    if (sessionFilter)  params.set("session_label", sessionFilter);
    if (billTypeFilter) params.set("bill_type", billTypeFilter);

    setLoading(true);
    fetch(`${API}/votes/?${params}`)
      .then((r) => r.json())
      .then((data) => {
        setItems(data.items ?? []);
        setTotal(data.total ?? 0);
        setLoading(false);
      });
  }, [page, resultFilter, voteTypeFilter, sessionFilter, billTypeFilter]);

  // Reset to page 1 when any filter changes
  useEffect(() => { setPage(1); }, [resultFilter, voteTypeFilter, sessionFilter, billTypeFilter]);

  const hasFilter = resultFilter || voteTypeFilter || sessionFilter || billTypeFilter;
  const clearAll = () => {
    setResultFilter(""); setVoteTypeFilter("");
    setSessionFilter(""); setBillTypeFilter("");
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <main className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-1">{t("votes.title")}</h1>
        <p className="text-muted-foreground text-sm">
          {total.toLocaleString(dateLocale)} {t("votes.subtitle")}
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6 p-4 rounded-lg border bg-muted/30">
        {/* Vote type */}
        <select value={voteTypeFilter} onChange={(e) => setVoteTypeFilter(e.target.value)} className={SELECT_CLASS}>
          <option value="">{t("votes.all_types")}</option>
          <option value="nominal">{t("votes.type_nominal")}</option>
          <option value="symbolic">{t("votes.type_symbolic")}</option>
        </select>

        {/* Result */}
        <select value={resultFilter} onChange={(e) => setResultFilter(e.target.value)} className={SELECT_CLASS}>
          <option value="">{t("votes.all_results")}</option>
          <option value="1">{t("votes.approved")}</option>
          <option value="0">{t("votes.rejected")}</option>
        </select>

        {/* Commission / session */}
        <div className="flex items-center gap-1">
          <select value={sessionFilter} onChange={(e) => setSessionFilter(e.target.value)} className={SELECT_CLASS}>
            <option value="">{t("votes.all_commissions")}</option>
            {sessionLabels.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
            {sessionOutrosCount > 0 && (
              <option value="__outros__">{t("votes.type_outros", { count: String(sessionOutrosCount) })}</option>
            )}
          </select>
          <AcronymHelp titleKey="votes.help_commissions" keyMap={ORGAN_KEY} />
        </div>

        {/* Bill type */}
        <div className="flex items-center gap-1">
          <select value={billTypeFilter} onChange={(e) => setBillTypeFilter(e.target.value)} className={SELECT_CLASS}>
            <option value="">{t("votes.all_bill_types")}</option>
            {billTypes.map((bt) => (
              <option key={bt} value={bt}>{bt}</option>
            ))}
          </select>
          <AcronymHelp titleKey="votes.help_bill_types" keyMap={BILL_TYPE_KEY} />
        </div>

        {hasFilter && (
          <Button variant="ghost" size="sm" onClick={clearAll} className="text-muted-foreground">
            {t("votes.clear")}
          </Button>
        )}
      </div>

      {/* Table */}
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 15 }).map((_, i) => (
            <div key={i} className="animate-pulse bg-muted rounded-lg h-14" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">{t("votes.empty")}</div>
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-24">{t("votes.col_date")}</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">{t("votes.col_bill")}</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-24 hidden sm:table-cell">{t("votes.col_commission")}</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-24 hidden md:table-cell">{t("votes.col_type")}</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-28">{t("votes.col_result")}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map((v) => (
                <tr key={v.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 text-muted-foreground whitespace-nowrap text-xs">
                    {formatDate(v.voted_at)}
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/votacao/${v.id}`} className="hover:text-primary transition-colors">
                      <span className="font-medium line-clamp-2">{billLabel(v)}</span>
                      {v.bill_type && v.bill_number && v.bill_year && (() => {
                        const ref = `${v.bill_type} ${v.bill_number}/${v.bill_year}`;
                        return billLabel(v) !== ref ? (
                          <span className="text-xs text-muted-foreground ml-2">{ref}</span>
                        ) : null;
                      })()}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground hidden sm:table-cell">
                    {v.session_label ?? "—"}
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    {voteTypeBadge(v.vote_type)}
                  </td>
                  <td className="px-4 py-3">{resultBadge(v.result)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-4 mt-8">
          <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
            {t("shared.prev")}
          </Button>
          <span className="text-sm text-muted-foreground">
            {t("shared.page_of", { page, total: totalPages })}
          </span>
          <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
            {t("shared.next")}
          </Button>
        </div>
      )}

      <p className="text-xs text-muted-foreground mt-6 text-center">
        {t("votes.disclaimer")}
      </p>
    </main>
  );
}
