"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const API = process.env.NEXT_PUBLIC_API_URL;
const PAGE_SIZE = 50;

const SELECT_CLASS =
  "h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

type Votacao = {
  id: number;
  external_id: string;
  description: string | null;
  voted_at: string | null;
  vote_type: string | null;
  result: string | null;
  bill_id: number | null;
  bill_title: string | null;
  bill_short_title: string | null;
  bill_ementa: string | null;
  bill_type: string | null;
  bill_number: number | null;
  bill_year: number | null;
};

function resultBadge(result: string | null) {
  if (result === "1" || result?.toLowerCase().includes("aprovad")) {
    return <Badge className="bg-green-100 text-green-800 border-green-200">Aprovada</Badge>;
  }
  if (result === "0" || result?.toLowerCase().includes("rejeitad")) {
    return <Badge className="bg-red-100 text-red-800 border-red-200">Rejeitada</Badge>;
  }
  return <Badge variant="secondary">{result ?? "—"}</Badge>;
}

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
  const [items, setItems] = useState<Votacao[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [resultFilter, setResultFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params = new URLSearchParams({
      vote_type: "nominal",
      source: "camara",
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (resultFilter) params.set("result", resultFilter);

    setLoading(true);
    fetch(`${API}/votes/?${params}`)
      .then((r) => r.json())
      .then((data) => {
        setItems(data.items ?? []);
        setTotal(data.total ?? 0);
        setLoading(false);
      });
  }, [page, resultFilter]);

  useEffect(() => { setPage(1); }, [resultFilter]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <main className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-1">Base de Votações</h1>
        <p className="text-muted-foreground text-sm">
          {total.toLocaleString("pt-BR")} votações nominais registradas — Câmara dos Deputados
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <select
          value={resultFilter}
          onChange={(e) => setResultFilter(e.target.value)}
          className={SELECT_CLASS}
        >
          <option value="">Todos os resultados</option>
          <option value="1">Aprovadas</option>
          <option value="0">Rejeitadas</option>
        </select>
        {resultFilter && (
          <Button variant="ghost" size="sm" onClick={() => setResultFilter("")} className="text-muted-foreground">
            Limpar filtros
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
        <div className="text-center py-20 text-muted-foreground">Nenhuma votação encontrada.</div>
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-24">Data</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Proposição</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-28">Resultado</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map((v) => (
                <tr key={v.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                    {formatDate(v.voted_at)}
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/votacao/${v.id}`} className="hover:text-primary transition-colors">
                      <span className="font-medium line-clamp-2">{billLabel(v)}</span>
                      {v.bill_type && v.bill_number && v.bill_year && (
                        <span className="text-xs text-muted-foreground ml-2">
                          {v.bill_type} {v.bill_number}/{v.bill_year}
                        </span>
                      )}
                    </Link>
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

      <p className="text-xs text-muted-foreground mt-6 text-center">
        Apenas votações nominais são registradas individualmente. Votações simbólicas não têm registro por parlamentar.
      </p>
    </main>
  );
}
