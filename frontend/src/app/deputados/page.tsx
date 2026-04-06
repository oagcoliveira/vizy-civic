"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type Politician = {
  id: number;
  short_name: string;
  state: string;
  party: string;
  photo_url: string | null;
};

const STATES = [
  "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
  "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
];

const PAGE_SIZE = 54;

export default function DeputadosPage() {
  const [politicians, setPoliticians] = useState<Politician[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [partyFilter, setPartyFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params = new URLSearchParams({
      source: "camara",
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (search) params.set("search", search);
    if (stateFilter) params.set("state", stateFilter);
    if (partyFilter) params.set("party", partyFilter);

    setLoading(true);
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/politicians/?${params}`)
      .then((r) => r.json())
      .then((data) => {
        setPoliticians(data.items);
        setTotal(data.total);
        setLoading(false);
      });
  }, [page, search, stateFilter, partyFilter]);

  useEffect(() => { setPage(1); }, [search, stateFilter, partyFilter]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <main className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1">Deputados Federais</h1>
        <p className="text-muted-foreground text-sm">{total} deputados em exercício — 57ª Legislatura</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <Input
          type="search"
          placeholder="Buscar por nome..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-56"
        />
        <select
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value)}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <option value="">Todos os estados</option>
          {STATES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <Input
          type="text"
          placeholder="Partido (ex: PT)"
          value={partyFilter}
          onChange={(e) => setPartyFilter(e.target.value.toUpperCase())}
          className="w-36"
        />
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {Array.from({ length: PAGE_SIZE }).map((_, i) => (
            <div key={i} className="animate-pulse bg-muted rounded-lg h-44" />
          ))}
        </div>
      ) : politicians.length === 0 ? (
        <p className="text-muted-foreground text-center py-20">Nenhum deputado encontrado.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {politicians.map((p) => (
            <Link
              key={p.id}
              href={`/politico/${p.id}`}
              className="group flex flex-col items-center bg-card border rounded-lg p-4 hover:shadow-md hover:border-primary/40 transition-all"
            >
              <div className="w-16 h-16 rounded-full overflow-hidden bg-muted mb-3 ring-2 ring-border group-hover:ring-primary/30 transition-all">
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
                <Badge variant="secondary">{p.party}</Badge>
                <Badge variant="outline">{p.state}</Badge>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-4 mt-10">
          <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
            Anterior
          </Button>
          <span className="text-sm text-muted-foreground">
            Página {page} de {totalPages}
          </span>
          <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
            Próxima
          </Button>
        </div>
      )}
    </main>
  );
}
