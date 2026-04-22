"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/LanguageContext";

const API = process.env.NEXT_PUBLIC_API_URL;
const PAGE_SIZE = 50;

const SELECT_CLASS =
  "h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

const ORGAN_NAMES_PT: Record<string, string> = {
  PLEN:         "Plenário da Câmara",
  CCJC:         "Constituição, Justiça e Cidadania",
  CCOM:         "Comunicação",
  CSPCCO:       "Segurança Pública e Combate ao Crime Organizado",
  CSAUDE:       "Saúde",
  CPD:          "Previdência, Assistência Social, Infância, Juventude e Família",
  "SECAP(SGM)": "Secretaria de Capacitação e Gestão",
  MESA:         "Mesa Diretora",
  CE:           "Educação",
  CAPADR:       "Agricultura, Pecuária, Abastecimento e Desenvolvimento Rural",
  CFFC:         "Fiscalização Financeira e Controle",
  CCULT:        "Cultura",
  CFT:          "Finanças e Tributação",
  CVT:          "Viação e Transportes",
  CPASF:        "Previdência, Assistência Social, Infância e Família",
  CMADS:        "Meio Ambiente e Desenvolvimento Sustentável",
  CMULHER:      "Defesa dos Direitos da Mulher",
};

const ORGAN_NAMES_EN: Record<string, string> = {
  PLEN:         "Chamber Plenary",
  CCJC:         "Constitution, Justice and Citizenship",
  CCOM:         "Communications",
  CSPCCO:       "Public Security and Organized Crime",
  CSAUDE:       "Health",
  CPD:          "Social Security, Welfare, Children, Youth and Family",
  "SECAP(SGM)": "Training and Management Secretariat",
  MESA:         "Bureau / Presiding Officers",
  CE:           "Education",
  CAPADR:       "Agriculture, Livestock, Supply and Rural Development",
  CFFC:         "Financial Oversight and Control",
  CCULT:        "Culture",
  CFT:          "Finance and Taxation",
  CVT:          "Transportation and Roads",
  CPASF:        "Social Security, Children and Family",
  CMADS:        "Environment and Sustainable Development",
  CMULHER:      "Women's Rights",
};

const BILL_TYPE_NAMES_PT: Record<string, string> = {
  PL:   "Projeto de Lei",
  PLP:  "Projeto de Lei Complementar",
  PEC:  "Proposta de Emenda à Constituição",
  REQ:  "Requerimento",
  MPV:  "Medida Provisória",
  PDL:  "Projeto de Decreto Legislativo",
  TVR:  "Televisão e Rádio (renovação de concessão)",
  PRC:  "Projeto de Resolução da Câmara",
  MSC:  "Mensagem do Executivo",
  REC:  "Recurso",
  REP:  "Requerimento de Plenário",
  SAP:  "Solicitação de Apoio",
  CMC:  "Comissão Mista de Controle",
  PDC:  "Projeto de Decreto do Congresso",
};

const BILL_TYPE_NAMES_EN: Record<string, string> = {
  PL:   "Bill",
  PLP:  "Complementary Law Bill",
  PEC:  "Constitutional Amendment Proposal",
  REQ:  "Motion / Request",
  MPV:  "Provisional Measure (Executive Order)",
  PDL:  "Legislative Decree Bill",
  TVR:  "Radio/TV Concession Renewal",
  PRC:  "Chamber Resolution Bill",
  MSC:  "Executive Message",
  REC:  "Appeal",
  REP:  "Plenary Request",
  SAP:  "Support Request",
  CMC:  "Joint Control Commission",
  PDC:  "Congressional Decree Bill",
};

function AcronymHelp({ titleKey, mapPt, mapEn }: {
  titleKey: string;
  mapPt: Record<string, string>;
  mapEn: Record<string, string>;
}) {
  const { t, lang } = useLanguage();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const map = lang === "en" ? mapEn : mapPt;

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
            {Object.entries(map).map(([acronym, name]) => (
              <div key={acronym} className="flex gap-2 text-xs">
                <span className="font-mono font-semibold text-gray-900 w-16 flex-shrink-0">{acronym}</span>
                <span className="text-gray-600">{name}</span>
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

function formatDate(ts: string | null) {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function VotacoesPage() {
  const { t } = useLanguage();
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
    if (vt === "nominal") return <Badge className="bg-blue-100 text-blue-800 border-blue-200 text-xs">Nominal</Badge>;
    if (vt === "symbolic") return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200 text-xs">Simbólica</Badge>;
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
          {total.toLocaleString("pt-BR")} {t("votes.subtitle")}
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6 p-4 rounded-lg border bg-muted/30">
        {/* Vote type */}
        <select value={voteTypeFilter} onChange={(e) => setVoteTypeFilter(e.target.value)} className={SELECT_CLASS}>
          <option value="">{t("votes.all_types")}</option>
          <option value="nominal">Nominal</option>
          <option value="symbolic">Simbólica</option>
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
            <option value="__outros__">Outras ({sessionOutrosCount} votações)</option>
          )}
        </select>
        <AcronymHelp titleKey="votes.help_commissions" mapPt={ORGAN_NAMES_PT} mapEn={ORGAN_NAMES_EN} />
        </div>

        {/* Bill type */}
        <div className="flex items-center gap-1">
          <select value={billTypeFilter} onChange={(e) => setBillTypeFilter(e.target.value)} className={SELECT_CLASS}>
            <option value="">{t("votes.all_bill_types")}</option>
            {billTypes.map((bt) => (
              <option key={bt} value={bt}>{bt}</option>
            ))}
          </select>
          <AcronymHelp titleKey="votes.help_bill_types" mapPt={BILL_TYPE_NAMES_PT} mapEn={BILL_TYPE_NAMES_EN} />
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
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-24 hidden sm:table-cell">Comissão</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-24 hidden md:table-cell">Tipo</th>
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
