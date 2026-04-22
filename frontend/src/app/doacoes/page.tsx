"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  AreaChart, Area, CartesianGrid, Legend,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import { useLanguage } from "@/contexts/LanguageContext";

const API = process.env.NEXT_PUBLIC_API_URL;
const YEARS = [2010, 2014, 2018, 2022];

type SourceCategory = "" | "individual" | "company" | "party" | "other";

function sourceCategory(raw: string): SourceCategory {
  const s = raw.toLowerCase();
  if (s.includes("pessoa") && (s.includes("física") || s.includes("fisic"))) return "individual";
  if (s.includes("pessoa") && (s.includes("jurídica") || s.includes("juridic"))) return "company";
  if (s.includes("fundo") || s.includes("partido")) return "party";
  return "other";
}
const COLORS = ["#2563eb","#16a34a","#dc2626","#d97706","#7c3aed",
                "#0891b2","#be185d","#65a30d","#ea580c","#6d28d9"];
const UFS = ["AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
             "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"];

const SELECT_CLASS =
  "h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

function brl(n: number) {
  if (n >= 1e9) return `R$ ${(n / 1e9).toFixed(1)} bi`;
  if (n >= 1e6) return `R$ ${(n / 1e6).toFixed(1)} mi`;
  if (n >= 1e3) return `R$ ${(n / 1e3).toFixed(0)} mil`;
  return `R$ ${n.toFixed(0)}`;
}

function brlFull(n: number) {
  return "R$ " + n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Rotated X-axis tick for column chart party labels
function RotatedTick({ x, y, payload, partyLinks }: any) {
  const href = partyLinks?.[payload.value] ?? "#";
  return (
    <g transform={`translate(${x},${y})`}>
      <a href={href}>
        <text
          transform="rotate(-75)"
          x={0} y={0} dy={4}
          textAnchor="end"
          fill="#6b7280"
          fontSize={10}
          style={{ cursor: "pointer", textDecoration: "underline" }}
        >
          {payload.value}
        </text>
      </a>
    </g>
  );
}

type Politician = { id: number; short_name: string; state: string; party: string };

function PoliticianCombobox({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const { t } = useLanguage();
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const [politicians, setPoliticians] = useState<Politician[]>([]);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API}/politicians/autocomplete/all`)
      .then(r => r.json())
      .then(setPoliticians)
      .catch(() => {});
  }, []);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = search.length >= 2
    ? politicians.filter(p =>
        p.short_name.toLowerCase().includes(search.toLowerCase())
      ).slice(0, 10)
    : [];

  return (
    <div ref={ref} className="relative">
      <input
        type="text"
        placeholder={t("donations.search")}
        value={search}
        onChange={e => {
          setSearch(e.target.value);
          setOpen(true);
          if (!e.target.value) onChange("");
        }}
        onFocus={() => { if (search.length >= 2) setOpen(true); }}
        className={SELECT_CLASS + " w-44"}
      />
      {open && filtered.length > 0 && (
        <div className="absolute top-full left-0 z-50 mt-1 w-64 max-h-60 overflow-auto rounded-md border bg-background shadow-md">
          {filtered.map(p => (
            <button
              key={p.id}
              className="w-full text-left px-3 py-2 text-sm hover:bg-muted"
              onMouseDown={e => e.preventDefault()}
              onClick={() => {
                setSearch(`${p.short_name} (${p.party}-${p.state})`);
                onChange(String(p.id));
                setOpen(false);
              }}
            >
              {p.short_name}{" "}
              <span className="text-muted-foreground">{p.party}-{p.state}</span>
            </button>
          ))}
        </div>
      )}
      {value && (
        <button
          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground text-xs"
          onClick={() => { setSearch(""); onChange(""); }}
        >
          ✕
        </button>
      )}
    </div>
  );
}

type Summary      = { total_amount: number; donor_count: number; politician_count: number };
type PartyBar     = { id: number; acronym: string; name: string; total_amount: number };
type YearSourceRow = { election_year: number; source_type: string; total_amount: number };
type TopPol       = { id: number; short_name: string; state: string; photo_url: string | null; party_acronym: string; total_amount: number; donor_count: number };
type TopDonor     = { id: number; name: string; donor_type: string; donor_state: string | null; total_amount: number; recipient_count: number };
type Party        = { id: number; acronym: string };

export default function DoacoesPage() {
  const { t } = useLanguage();
  const [year, setYear]                 = useState("");
  const [partyId, setPartyId]           = useState("");
  const [state, setState]               = useState("");
  const [sourceCat, setSourceCat]       = useState<SourceCategory>("");
  const [donorType, setDonorType]       = useState("");
  const [politicianId, setPoliticianId] = useState("");

  const [parties, setParties]         = useState<Party[]>([]);

  const [summary,      setSummary]      = useState<Summary | null>(null);
  const [byYearRaw,    setByYearRaw]    = useState<YearSourceRow[]>([]);
  const [byParty,      setByParty]      = useState<PartyBar[]>([]);
  const [topPols,      setTopPols]      = useState<TopPol[]>([]);
  const [topDonors,    setTopDonors]    = useState<TopDonor[]>([]);

  useEffect(() => {
    fetch(`${API}/parties/`).then(r => r.json()).then(setParties).catch(() => {});
  }, []);

  useEffect(() => {
    const p = new URLSearchParams();
    if (year)         p.set("year", year);
    if (partyId)      p.set("party_id", partyId);
    if (state)        p.set("state", state);
    if (donorType)    p.set("donor_type", donorType);
    if (politicianId) p.set("politician_id", politicianId);
    const qs = p.toString();
    const get = (path: string) => {
      const sep = path.includes("?") ? "&" : "?";
      const url = qs ? `${API}/donations/${path}${sep}${qs}` : `${API}/donations/${path}`;
      return fetch(url).then(r => r.json());
    };

    setSummary(null);
    get("summary").then(setSummary).catch(() => {});
    get("by-year").then(setByYearRaw).catch(() => setByYearRaw([]));
    get("by-party").then(setByParty).catch(() => setByParty([]));
    get("top-politicians?limit=20").then(setTopPols).catch(() => setTopPols([]));
    get("top-donors?limit=20").then(setTopDonors).catch(() => setTopDonors([]));
  }, [year, partyId, state, donorType, politicianId]);

  // Pivot raw (year, source_type, total) rows into { election_year, [key]: amount, ... }
  // When sourceCat is set, group by category; otherwise by raw source_type
  const filteredByYearRaw = useMemo(() => {
    if (!sourceCat) return byYearRaw;
    return byYearRaw.filter(r => sourceCategory(r.source_type) === sourceCat);
  }, [byYearRaw, sourceCat]);

  const byYear = useMemo(() => {
    const map: Record<number, any> = {};
    filteredByYearRaw.forEach(r => {
      const key = sourceCat ? sourceCat : r.source_type;
      if (!map[r.election_year]) map[r.election_year] = { election_year: r.election_year };
      map[r.election_year][key] = (map[r.election_year][key] ?? 0) + Number(r.total_amount);
    });
    return Object.values(map).sort((a, b) => a.election_year - b.election_year);
  }, [filteredByYearRaw, sourceCat]);

  const sourceKeys = useMemo(
    () => sourceCat ? [sourceCat] : Array.from(new Set(byYearRaw.map(r => r.source_type))),
    [byYearRaw, sourceCat]
  );

  const partyLinks: Record<string, string> = {};
  byParty.forEach(p => { partyLinks[p.acronym] = `/partidos/${p.id}`; });

  const hasFilters = year || partyId || state || sourceCat || donorType || politicianId;
  const clearAll = () => {
    setYear(""); setPartyId(""); setState("");
    setSourceCat(""); setDonorType(""); setPoliticianId("");
  };

  return (
    <main className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-1">{t("donations.title")}</h1>
        <p className="text-muted-foreground text-sm">{t("donations.subtitle")}</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-8 p-4 rounded-lg border bg-muted/30">
        <select value={year} onChange={e => setYear(e.target.value)} className={SELECT_CLASS}>
          <option value="">{t("donations.all_years")}</option>
          {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        <select value={partyId} onChange={e => setPartyId(e.target.value)} className={SELECT_CLASS}>
          <option value="">{t("donations.all_parties")}</option>
          {parties.map(p => <option key={p.id} value={p.id}>{p.acronym}</option>)}
        </select>
        <select value={state} onChange={e => setState(e.target.value)} className={SELECT_CLASS}>
          <option value="">{t("donations.all_states")}</option>
          {UFS.map(uf => <option key={uf} value={uf}>{uf}</option>)}
        </select>
        <select value={sourceCat} onChange={e => setSourceCat(e.target.value as SourceCategory)} className={SELECT_CLASS}>
          <option value="">{t("donations.all_sources")}</option>
          <option value="individual">{t("donations.cat_individual")}</option>
          <option value="company">{t("donations.cat_company")}</option>
          <option value="party">{t("donations.cat_party")}</option>
          <option value="other">{t("donations.cat_other")}</option>
        </select>
        <select value={donorType} onChange={e => setDonorType(e.target.value)} className={SELECT_CLASS}>
          <option value="">{t("donations.all_donors")}</option>
          <option value="individual">{t("donations.donor_individual")}</option>
          <option value="company">{t("donations.donor_company")}</option>
        </select>
        <PoliticianCombobox value={politicianId} onChange={setPoliticianId} />
        {hasFilters && (
          <button onClick={clearAll}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            {t("donations.clear")}
          </button>
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { label: t("donations.total"),      value: summary ? brl(Number(summary.total_amount))                        : t("donations.loading") },
          { label: t("donations.unique_donors"), value: summary ? Number(summary.donor_count).toLocaleString("pt-BR")   : t("donations.loading") },
          { label: t("donations.candidates"), value: summary ? Number(summary.politician_count).toLocaleString("pt-BR") : t("donations.loading") },
        ].map(c => (
          <div key={c.label} className="rounded-lg border p-5">
            <p className="text-sm text-muted-foreground mb-1">{c.label}</p>
            <p className="text-2xl font-bold">{c.value}</p>
          </div>
        ))}
      </div>

      {/* Row 2: Stacked area chart | Column party chart — same height */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">

        <div className="rounded-lg border p-5">
          <h2 className="text-base font-semibold mb-4">{t("donations.chart1_title")}</h2>
          {byYear.length === 0 ? (
            <div className="h-[280px] flex items-center justify-center text-muted-foreground text-sm">{t("donations.loading")}</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={byYear} margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="election_year" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={brl} tick={{ fontSize: 10 }} width={68} />
                <Tooltip formatter={(v) => v != null ? brlFull(Number(v)) : ""} />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                {sourceKeys.map((key, i) => (
                  <Area key={key} type="monotone" dataKey={key} stackId="a"
                        stroke={COLORS[i % COLORS.length]}
                        fill={COLORS[i % COLORS.length]} fillOpacity={0.65} />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="rounded-lg border p-5">
          <h2 className="text-base font-semibold mb-1">{t("donations.chart2_title")}</h2>
          <p className="text-xs text-muted-foreground mb-3">{t("donations.chart2_hint")}</p>
          {byParty.length === 0 ? (
            <div className="h-[280px] flex items-center justify-center text-muted-foreground text-sm">{t("donations.loading")}</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={byParty} margin={{ left: 8, right: 8, top: 4, bottom: 72 }}>
                <XAxis dataKey="acronym" interval={0}
                       tick={<RotatedTick partyLinks={partyLinks} />} />
                <YAxis tickFormatter={brl} tick={{ fontSize: 10 }} width={60} />
                <Tooltip
                  formatter={(v) => [v != null ? brlFull(Number(v)) : "", t("donations.chart_total")]}
                  labelFormatter={label => byParty.find(p => p.acronym === label)?.name ?? label}
                />
                <Bar dataKey="total_amount" radius={[4, 4, 0, 0]}>
                  {byParty.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Row 3: Top candidatos | Top doadores — same height */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        <div className="rounded-lg border p-5 flex flex-col" style={{ maxHeight: 460 }}>
          <h2 className="text-base font-semibold mb-4">{t("donations.top_candidates")}</h2>
          <div className="overflow-auto flex-1">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-background border-b">
                <tr>
                  <th className="text-left py-2 pr-2 text-muted-foreground font-medium w-6">{t("donations.col_rank")}</th>
                  <th className="text-left py-2 text-muted-foreground font-medium">{t("donations.col_name")}</th>
                  <th className="text-right py-2 text-muted-foreground font-medium">{t("donations.col_total")}</th>
                  <th className="text-right py-2 text-muted-foreground font-medium hidden sm:table-cell">{t("donations.col_donors")}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {topPols.map((p, i) => (
                  <tr key={p.id} className="hover:bg-muted/30">
                    <td className="py-2 pr-2 text-muted-foreground text-xs">{i + 1}</td>
                    <td className="py-2">
                      <Link href={`/politico/${p.id}`}
                            className="flex items-center gap-2 hover:text-primary transition-colors">
                        {p.photo_url && (
                          <img src={p.photo_url} alt={p.short_name}
                               className="w-6 h-6 rounded-full object-cover shrink-0" />
                        )}
                        <div>
                          <span className="font-medium">{p.short_name}</span>
                          <span className="text-muted-foreground text-xs ml-1">{p.party_acronym}-{p.state}</span>
                        </div>
                      </Link>
                    </td>
                    <td className="py-2 text-right font-mono text-xs">{brl(Number(p.total_amount))}</td>
                    <td className="py-2 text-right text-muted-foreground text-xs hidden sm:table-cell">
                      {Number(p.donor_count).toLocaleString("pt-BR")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-lg border p-5 flex flex-col" style={{ maxHeight: 460 }}>
          <h2 className="text-base font-semibold mb-4">{t("donations.top_donors")}</h2>
          <div className="overflow-auto flex-1">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-background border-b">
                <tr>
                  <th className="text-left py-2 pr-2 text-muted-foreground font-medium w-6">{t("donations.col_rank")}</th>
                  <th className="text-left py-2 text-muted-foreground font-medium">{t("donations.col_donor")}</th>
                  <th className="text-right py-2 text-muted-foreground font-medium">{t("donations.col_donated")}</th>
                  <th className="text-right py-2 text-muted-foreground font-medium hidden sm:table-cell">{t("donations.col_politicians")}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {topDonors.map((d, i) => (
                  <tr key={d.id} className="hover:bg-muted/30">
                    <td className="py-2 pr-2 text-muted-foreground text-xs">{i + 1}</td>
                    <td className="py-2">
                      <div className="flex items-center gap-2">
                        <Badge variant={d.donor_type === "company" ? "secondary" : "outline"}
                               className="text-xs shrink-0">
                          {d.donor_type === "company" ? "PJ" : d.donor_type === "individual" ? "PF" : "?"}
                        </Badge>
                        <div className="min-w-0">
                          <span className="font-medium line-clamp-1">{d.name}</span>
                          {d.donor_state && (
                            <span className="text-muted-foreground text-xs ml-1">· {d.donor_state}</span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="py-2 text-right font-mono text-xs">{brl(Number(d.total_amount))}</td>
                    <td className="py-2 text-right text-muted-foreground text-xs hidden sm:table-cell">
                      {d.recipient_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </main>
  );
}
