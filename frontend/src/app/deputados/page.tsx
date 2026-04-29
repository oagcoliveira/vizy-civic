"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/LanguageContext";

type Politician = {
  id: number;
  short_name: string;
  state: string;
  party: string;
  photo_url: string | null;
};

type CommitteeOption = {
  id: number;
  acronym: string | null;
  name: string;
  display_name: string | null;
  member_count: number;
};

const STATES = [
  "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
  "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
];

const PARTIES = [
  "AVANTE","CIDADANIA","MDB","MISSÃO","NOVO","PCdoB","PDT","PL","PODE",
  "PP","PRD","PSB","PSD","PSDB","PSOL","PT","PV","REDE","REPUBLICANOS",
  "SOLIDARIEDADE","UNIÃO",
];

const PAGE_SIZE = 54;

const SELECT_CLASS =
  "h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

export default function DeputadosPage() {
  const { t } = useLanguage();
  const [politicians, setPoliticians] = useState<Politician[]>([]);
  const [committees, setCommittees] = useState<CommitteeOption[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [partyFilter, setPartyFilter] = useState("");
  const [committeeFilter, setCommitteeFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/politicians/filters/committees?source=camara`)
      .then((r) => r.json())
      .then((data) => setCommittees(Array.isArray(data) ? data : []))
      .catch(() => setCommittees([]));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams({
      source: "camara",
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (search) params.set("search", search);
    if (stateFilter) params.set("state", stateFilter);
    if (partyFilter) params.set("party", partyFilter);
    if (committeeFilter) params.set("committee_id", committeeFilter);

    setLoading(true);
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/politicians/?${params}`)
      .then((r) => r.json())
      .then((data) => {
        setPoliticians(data.items);
        setTotal(data.total);
        setLoading(false);
      });
  }, [page, search, stateFilter, partyFilter, committeeFilter]);

  useEffect(() => { setPage(1); }, [search, stateFilter, partyFilter, committeeFilter]);

  const hasFilters = search !== "" || stateFilter !== "" || partyFilter !== "" || committeeFilter !== "";

  function clearFilters() {
    setSearch("");
    setStateFilter("");
    setPartyFilter("");
    setCommitteeFilter("");
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <main className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-1">{t("deputies.title")}</h1>
        <p className="text-muted-foreground text-sm">
          {total.toLocaleString("pt-BR")} {t("deputies.subtitle")}
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <Input
          type="search"
          placeholder={t("deputies.search")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-52"
        />
        <select
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}
          className={SELECT_CLASS}
        >
          <option value="">{t("deputies.all_states")}</option>
          {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select
          value={partyFilter}
          onChange={(e) => setPartyFilter(e.target.value)}
          className={SELECT_CLASS}
        >
          <option value="">{t("deputies.all_parties")}</option>
          {PARTIES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select
          value={committeeFilter}
          onChange={(e) => setCommitteeFilter(e.target.value)}
          className={`${SELECT_CLASS} w-72 max-w-full`}
        >
          <option value="">{t("deputies.all_commissions")}</option>
          {committees.map((c) => (
            <option key={c.id} value={String(c.id)}>
              {c.acronym ? `${c.acronym} — ${c.display_name ?? c.name}` : c.display_name ?? c.name} ({c.member_count})
            </option>
          ))}
        </select>
        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={clearFilters} className="text-muted-foreground">
            {t("deputies.clear")}
          </Button>
        )}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {Array.from({ length: PAGE_SIZE }).map((_, i) => (
            <div key={i} className="animate-pulse bg-muted rounded-lg h-44" />
          ))}
        </div>
      ) : politicians.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-muted-foreground">{t("deputies.empty")}</p>
          {hasFilters && (
            <Button variant="ghost" size="sm" onClick={clearFilters} className="mt-2">
              {t("deputies.clear")}
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {politicians.map((p) => (
            <Link
              key={p.id}
              href={`/politico/${p.id}`}
              className="group flex flex-col items-center bg-card border rounded-lg p-4 hover:shadow-md hover:border-primary/40 transition-all"
            >
              <div className="w-16 h-16 rounded-full overflow-hidden bg-muted mb-3 ring-2 ring-border group-hover:ring-primary/30 transition-all flex-shrink-0">
                {p.photo_url ? (
                  <img src={p.photo_url} alt={p.short_name} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-muted-foreground text-xl font-bold">
                    {p.short_name?.[0]}
                  </div>
                )}
              </div>
              <p className="text-xs font-semibold text-center leading-tight mb-2 group-hover:text-primary transition-colors line-clamp-2">
                {p.short_name}
              </p>
              <div className="flex gap-1 flex-wrap justify-center">
                <Badge variant="secondary" className="text-[10px] px-1.5">{p.party}</Badge>
                <Badge variant="outline" className="text-[10px] px-1.5">{p.state}</Badge>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-4 mt-10">
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
    </main>
  );
}
