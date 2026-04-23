"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/LanguageContext";
import type { TranslationKey } from "@/lib/translations";

const API = process.env.NEXT_PUBLIC_API_URL;
const PAGE_SIZE = 600;

// Map organ acronym to translation key
const ORGAN_KEY: Record<string, TranslationKey> = {
  PLEN:       "organ.PLEN",
  MESA:       "organ.MESA",
  SEMIPLEN:   "organ.SEMIPLEN",
  CCJC:       "organ.CCJC",
  CCOM:       "organ.CCOM",
  CSPCCO:     "organ.CSPCCO",
  CSAUDE:     "organ.CSAUDE",
  CPD:        "organ.CPD",
  CE:         "organ.CE",
  CAPADR:     "organ.CAPADR",
  CFFC:       "organ.CFFC",
  CCULT:      "organ.CCULT",
  CFT:        "organ.CFT",
  CVT:        "organ.CVT",
  CPASF:      "organ.CPASF",
  CMADS:      "organ.CMADS",
  CMULHER:    "organ.CMULHER",
  CTRAB:      "organ.CTRAB",
  CASP:       "organ.CASP",
  CDHMIR:     "organ.CDHMIR",
  CME:        "organ.CME",
  CESPO:      "organ.CESPO",
  CLP:        "organ.CLP",
  CCP:        "organ.CCP",
  CREDN:      "organ.CREDN",
  CDU:        "organ.CDU",
  CIDOSO:     "organ.CIDOSO",
  CDC:        "organ.CDC",
  CDE:        "organ.CDE",
  CPOVOS:     "organ.CPOVOS",
  CINDRE:     "organ.CINDRE",
  CTUR:       "organ.CTUR",
  CCTI:       "organ.CCTI",
  CMO:        "organ.CMO",
  SECAP_SGM:  "organ.SECAP_SGM",
};

// Internal sentinel values for vote filter — kept in Portuguese to match API data
const VOTE_FILTER_INTERNAL = ["__all__", "Sim", "Não", "Abstenção", "Obstrução", "Artigo 17"] as const;

type Bill = {
  id: number;
  title: string | null;
  short_title: string | null;
  ementa: string | null;
  type: string | null;
  number: number | null;
  year: number | null;
  full_text_url: string | null;
  is_primary: boolean;
};

type VotacaoDetail = {
  id: number;
  external_id: string;
  description: string | null;
  voted_at: string | null;
  result: string | null;
  vote_type: string | null;
  session_label: string | null;
  bill_id: number | null;
  bill_short_title: string | null;
  bill_ementa: string | null;
  bill_type: string | null;
  bill_number: number | null;
  bill_year: number | null;
  bill_url: string | null;
  bills: Bill[];
};

type IndividualVote = {
  politician_id: number;
  short_name: string;
  name: string;
  photo_url: string | null;
  state: string | null;
  vote: string;
  party_at_time: string | null;
  party_orientation: string | null;
  followed_orientation: boolean | null;
};

export default function VotacaoPage({ params }: { params: { id: string } }) {
  const { t, lang } = useLanguage();
  const [votacao, setVotacao] = useState<VotacaoDetail | null>(null);
  const [individualVotes, setIndividualVotes] = useState<IndividualVote[]>([]);
  const [totalVotes, setTotalVotes] = useState(0);
  const [search, setSearch] = useState("");
  const [voteFilter, setVoteFilter] = useState<string>("__all__");
  const [loading, setLoading] = useState(true);

  const dateLocale = lang === "en" ? "en-GB" : "pt-BR";

  function formatDate(ts: string | null) {
    if (!ts) return "—";
    return new Date(ts).toLocaleDateString(dateLocale, {
      day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  }

  // Map vote value to translated label + colour class
  function voteStyle(vote: string): { label: string; color: string } {
    const map: Record<string, { labelKey: TranslationKey; color: string }> = {
      "Sim":       { labelKey: "vote_label.sim",       color: "bg-green-100 text-green-800 border-green-200" },
      "Não":       { labelKey: "vote_label.nao",       color: "bg-red-100 text-red-800 border-red-200" },
      "Abstenção": { labelKey: "vote_label.abstencao", color: "bg-yellow-100 text-yellow-800 border-yellow-200" },
      "Obstrução": { labelKey: "vote_label.obstrucao", color: "bg-orange-100 text-orange-800 border-orange-200" },
      "Artigo 17": { labelKey: "vote_label.artigo17",  color: "bg-gray-100 text-gray-700 border-gray-200" },
    };
    const entry = map[vote];
    return entry ? { label: t(entry.labelKey), color: entry.color } : { label: vote, color: "bg-muted" };
  }

  function voteBadge(vote: string) {
    const { label, color } = voteStyle(vote);
    return <Badge className={color}>{label}</Badge>;
  }

  function resultBadge(result: string | null) {
    if (result === "1" || result?.toLowerCase().includes("aprovad"))
      return <Badge className="bg-green-100 text-green-800 border-green-200 text-base px-3 py-1">{t("votes.badge_approved")}</Badge>;
    if (result === "0" || result?.toLowerCase().includes("rejeitad"))
      return <Badge className="bg-red-100 text-red-800 border-red-200 text-base px-3 py-1">{t("votes.badge_rejected")}</Badge>;
    return <Badge variant="secondary">{result ?? "—"}</Badge>;
  }

  useEffect(() => {
    fetch(`${API}/votes/${params.id}`)
      .then((r) => r.json())
      .then((data) => { setVotacao(data); setLoading(false); });

    fetch(`${API}/votes/${params.id}/individual?page_size=${PAGE_SIZE}`)
      .then((r) => r.json())
      .then((data) => { setIndividualVotes(data.items ?? []); setTotalVotes(data.total ?? 0); });
  }, [params.id]);

  const filtered = individualVotes.filter((iv) => {
    const matchesVote = voteFilter === "__all__" || iv.vote === voteFilter;
    const matchesSearch = !search ||
      iv.short_name?.toLowerCase().includes(search.toLowerCase()) ||
      iv.name?.toLowerCase().includes(search.toLowerCase());
    return matchesVote && matchesSearch;
  });

  if (loading) {
    return (
      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-muted rounded w-3/4" />
          <div className="h-4 bg-muted rounded w-1/2" />
          <div className="h-32 bg-muted rounded" />
        </div>
      </main>
    );
  }

  if (!votacao) {
    return (
      <main className="max-w-5xl mx-auto px-4 py-8">
        <p className="text-muted-foreground">{t("vote.not_found")}</p>
        <Link href="/votacoes" className="text-primary text-sm mt-2 block">{t("vote.back_long")}</Link>
      </main>
    );
  }

  const primaryBill = votacao.bills.find((b) => b.is_primary) ?? votacao.bills[0] ?? null;
  const billLabel = primaryBill?.short_title ?? primaryBill?.title ??
    (primaryBill?.type && primaryBill?.number && primaryBill?.year
      ? `${primaryBill.type} ${primaryBill.number}/${primaryBill.year}`
      : votacao.description);

  // Count votes
  const simCount = individualVotes.filter((v) => v.vote === "Sim").length;
  const naoCount = individualVotes.filter((v) => v.vote === "Não").length;
  const abstCount = individualVotes.filter((v) => v.vote === "Abstenção").length;
  const outroCount = individualVotes.filter((v) => !["Sim", "Não", "Abstenção"].includes(v.vote)).length;

  // Vote summary cards use translated labels
  const voteSummaryCards = [
    { labelKey: "vote.summary_sim" as TranslationKey,       count: simCount,   color: "text-green-700 bg-green-50 border-green-200" },
    { labelKey: "vote.summary_nao" as TranslationKey,       count: naoCount,   color: "text-red-700 bg-red-50 border-red-200" },
    { labelKey: "vote.summary_abstencao" as TranslationKey, count: abstCount,  color: "text-yellow-700 bg-yellow-50 border-yellow-200" },
    { labelKey: "vote.summary_outros" as TranslationKey,    count: outroCount, color: "text-gray-600 bg-gray-50 border-gray-200" },
  ];

  return (
    <main className="max-w-5xl mx-auto px-4 py-8">
      <Link href="/votacoes" className="text-sm text-muted-foreground hover:text-primary mb-4 block">
        {t("vote.back")}
      </Link>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start gap-3 mb-3">
          {resultBadge(votacao.result)}
          <span className="text-sm text-muted-foreground mt-1">{formatDate(votacao.voted_at)}</span>
          {votacao.session_label && (
            <span className="text-sm text-muted-foreground mt-1">
              · {ORGAN_KEY[votacao.session_label] ? t(ORGAN_KEY[votacao.session_label]) : votacao.session_label}
            </span>
          )}
          {votacao.vote_type === "nominal" && (
            <Badge className="bg-blue-100 text-blue-800 border-blue-200 mt-1">{t("vote.nominal_badge")}</Badge>
          )}
          {(!votacao.vote_type || votacao.vote_type === "none") && (
            <Badge className="bg-gray-100 text-gray-600 border-gray-200 mt-1">{t("vote.no_votes_badge")}</Badge>
          )}
        </div>
        <h1 className="text-2xl font-bold mb-2">{billLabel}</h1>
        {primaryBill?.ementa && primaryBill.ementa !== billLabel && (
          <p className="text-muted-foreground text-sm mt-2 italic">{primaryBill.ementa}</p>
        )}
        {votacao.description && votacao.description !== billLabel && votacao.description !== primaryBill?.ementa && (
          <div className="mt-3 rounded-md border border-blue-100 bg-blue-50 px-3 py-2">
            <p className="text-xs font-semibold text-blue-700 mb-1">{t("vote.about_section")}</p>
            <p className="text-sm text-blue-900">{votacao.description}</p>
          </div>
        )}
        {votacao.vote_type === "symbolic" && (
          <div className="mt-3 flex items-start gap-2 rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-800">
            <Badge className="bg-yellow-100 text-yellow-800 border-yellow-300 flex-shrink-0">{t("vote.symbolic_badge")}</Badge>
            <span>{t("vote.symbolic_note")}</span>
          </div>
        )}
      </div>

      {/* Vote counts */}
      {totalVotes > 0 && (
        <div className="grid grid-cols-4 gap-3 mb-6">
          {voteSummaryCards.map(({ labelKey, count, color }) => (
            <div key={labelKey} className={`rounded-lg border px-4 py-3 text-center ${color}`}>
              <p className="text-2xl font-bold">{count}</p>
              <p className="text-xs font-medium">{t(labelKey)}</p>
            </div>
          ))}
        </div>
      )}

      {/* Linked bills */}
      {votacao.bills.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
            {t("vote.related_bills")}
          </h2>
          <div className="space-y-2">
            {votacao.bills.map((b) => (
              <Link
                key={b.id}
                href={`/proposicao/${b.id}`}
                className="flex items-start gap-3 p-3 rounded-lg border hover:border-primary/40 hover:bg-muted/30 transition-all group"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    {b.type && <Badge variant="outline" className="text-xs">{b.type} {b.number}/{b.year}</Badge>}
                    {b.is_primary && <Badge variant="secondary" className="text-xs">{t("vote.primary")}</Badge>}
                  </div>
                  <p className="text-sm font-medium group-hover:text-primary transition-colors line-clamp-2">
                    {b.short_title ?? b.title ?? b.ementa ?? "—"}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Party breakdown */}
      {individualVotes.length > 0 && (() => {
        const partyMap: Record<string, { sim: number; nao: number; outros: number }> = {};
        individualVotes.forEach((iv) => {
          const p = iv.party_at_time ?? "—";
          if (!partyMap[p]) partyMap[p] = { sim: 0, nao: 0, outros: 0 };
          if (iv.vote === "Sim") partyMap[p].sim++;
          else if (iv.vote === "Não") partyMap[p].nao++;
          else partyMap[p].outros++;
        });
        const parties = Object.entries(partyMap).sort((a, b) => (b[1].sim + b[1].nao + b[1].outros) - (a[1].sim + a[1].nao + a[1].outros));
        return (
          <div className="mb-6">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              {t("vote.party_breakdown")}
            </h2>
            <div className="rounded-lg border overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium text-muted-foreground">{t("vote.col_party")}</th>
                    <th className="text-right px-4 py-2 font-medium text-green-700">{t("vote.col_sim")}</th>
                    <th className="text-right px-4 py-2 font-medium text-green-600 text-xs w-14">{t("vote.col_pct_sim")}</th>
                    <th className="text-right px-4 py-2 font-medium text-red-700">{t("vote.col_nao")}</th>
                    <th className="text-right px-4 py-2 font-medium text-red-600 text-xs w-14">{t("vote.col_pct_nao")}</th>
                    <th className="text-right px-4 py-2 font-medium text-muted-foreground hidden sm:table-cell">{t("vote.col_others")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {parties.map(([party, counts]) => {
                    const total = counts.sim + counts.nao + counts.outros;
                    const pctSim = total > 0 ? Math.round((counts.sim / total) * 100) : 0;
                    const pctNao = total > 0 ? Math.round((counts.nao / total) * 100) : 0;
                    return (
                      <tr key={party} className="hover:bg-muted/20">
                        <td className="px-4 py-2 font-medium">{party}</td>
                        <td className="px-4 py-2 text-right text-green-700">{counts.sim || "—"}</td>
                        <td className="px-4 py-2 text-right text-green-600 text-xs">{counts.sim > 0 ? `${pctSim}%` : "—"}</td>
                        <td className="px-4 py-2 text-right text-red-700">{counts.nao || "—"}</td>
                        <td className="px-4 py-2 text-right text-red-600 text-xs">{counts.nao > 0 ? `${pctNao}%` : "—"}</td>
                        <td className="px-4 py-2 text-right text-muted-foreground hidden sm:table-cell">{counts.outros || "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );
      })()}

      {/* Individual votes */}
      {totalVotes > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
            {t("vote.individual")} ({totalVotes})
          </h2>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <Input
              type="search"
              placeholder={t("vote.search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-48 h-8 text-sm"
            />
            <div className="flex gap-1">
              {VOTE_FILTER_INTERNAL.map((f) => {
                const label = f === "__all__" ? t("vote.filter_all") : voteStyle(f).label;
                return (
                  <Button
                    key={f}
                    variant={voteFilter === f ? "default" : "outline"}
                    size="sm"
                    className="h-8 text-xs"
                    onClick={() => setVoteFilter(f)}
                  >
                    {label}
                  </Button>
                );
              })}
            </div>
          </div>

          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">{t("vote.col_politician")}</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground w-16">{t("vote.col_state")}</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground w-20">{t("vote.col_party")}</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground w-24">{t("vote.col_vote")}</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground w-28">{t("vote.col_orientation")}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filtered.map((iv) => (
                  <tr key={iv.politician_id} className="hover:bg-muted/20 transition-colors">
                    <td className="px-4 py-2">
                      <Link href={`/politico/${iv.politician_id}`} className="flex items-center gap-2 hover:text-primary transition-colors">
                        {iv.photo_url && (
                          <img src={iv.photo_url} alt={iv.short_name} className="w-6 h-6 rounded-full object-cover flex-shrink-0" />
                        )}
                        <span className="font-medium">{iv.short_name ?? iv.name}</span>
                        {iv.followed_orientation === false && (
                          <Badge variant="outline" className="text-[10px] text-orange-600 border-orange-300 ml-1">{t("vote.diverged")}</Badge>
                        )}
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">{iv.state ?? "—"}</td>
                    <td className="px-4 py-2 text-muted-foreground">{iv.party_at_time ?? "—"}</td>
                    <td className="px-4 py-2">{voteBadge(iv.vote)}</td>
                    <td className="px-4 py-2 text-muted-foreground text-xs">{iv.party_orientation ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {filtered.length === 0 && (
            <p className="text-center py-8 text-muted-foreground text-sm">{t("vote.empty")}</p>
          )}
        </div>
      )}
    </main>
  );
}
