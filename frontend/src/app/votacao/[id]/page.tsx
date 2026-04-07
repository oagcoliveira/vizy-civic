"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const API = process.env.NEXT_PUBLIC_API_URL;
const PAGE_SIZE = 100;

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

function voteBadge(vote: string) {
  const map: Record<string, string> = {
    "Sim": "bg-green-100 text-green-800 border-green-200",
    "Não": "bg-red-100 text-red-800 border-red-200",
    "Abstenção": "bg-yellow-100 text-yellow-800 border-yellow-200",
    "Obstrução": "bg-orange-100 text-orange-800 border-orange-200",
    "Artigo 17": "bg-gray-100 text-gray-700 border-gray-200",
  };
  return <Badge className={map[vote] ?? "bg-muted"}>{vote}</Badge>;
}

function resultBadge(result: string | null) {
  if (result === "1" || result?.toLowerCase().includes("aprovad"))
    return <Badge className="bg-green-100 text-green-800 border-green-200 text-base px-3 py-1">Aprovada</Badge>;
  if (result === "0" || result?.toLowerCase().includes("rejeitad"))
    return <Badge className="bg-red-100 text-red-800 border-red-200 text-base px-3 py-1">Rejeitada</Badge>;
  return <Badge variant="secondary">{result ?? "—"}</Badge>;
}

function formatDate(ts: string | null) {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString("pt-BR", {
    day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

const VOTE_FILTERS = ["Todos", "Sim", "Não", "Abstenção", "Obstrução", "Artigo 17"];

export default function VotacaoPage({ params }: { params: { id: string } }) {
  const [votacao, setVotacao] = useState<VotacaoDetail | null>(null);
  const [individualVotes, setIndividualVotes] = useState<IndividualVote[]>([]);
  const [totalVotes, setTotalVotes] = useState(0);
  const [search, setSearch] = useState("");
  const [voteFilter, setVoteFilter] = useState("Todos");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/votes/${params.id}`)
      .then((r) => r.json())
      .then((data) => { setVotacao(data); setLoading(false); });

    fetch(`${API}/votes/${params.id}/individual?page_size=${PAGE_SIZE}`)
      .then((r) => r.json())
      .then((data) => { setIndividualVotes(data.items ?? []); setTotalVotes(data.total ?? 0); });
  }, [params.id]);

  const filtered = individualVotes.filter((iv) => {
    const matchesVote = voteFilter === "Todos" || iv.vote === voteFilter;
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
        <p className="text-muted-foreground">Votação não encontrada.</p>
        <Link href="/votacoes" className="text-primary text-sm mt-2 block">← Voltar à base de votações</Link>
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

  return (
    <main className="max-w-5xl mx-auto px-4 py-8">
      <Link href="/votacoes" className="text-sm text-muted-foreground hover:text-primary mb-4 block">
        ← Base de Votações
      </Link>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start gap-3 mb-3">
          {resultBadge(votacao.result)}
          <span className="text-sm text-muted-foreground mt-1">{formatDate(votacao.voted_at)}</span>
        </div>
        <h1 className="text-2xl font-bold mb-2">{billLabel}</h1>
        {votacao.description && votacao.description !== billLabel && (
          <p className="text-muted-foreground text-sm">{votacao.description}</p>
        )}
      </div>

      {/* Vote counts */}
      {totalVotes > 0 && (
        <div className="grid grid-cols-4 gap-3 mb-6">
          {[
            { label: "Sim", count: simCount, color: "text-green-700 bg-green-50 border-green-200" },
            { label: "Não", count: naoCount, color: "text-red-700 bg-red-50 border-red-200" },
            { label: "Abstenção", count: abstCount, color: "text-yellow-700 bg-yellow-50 border-yellow-200" },
            { label: "Outros", count: outroCount, color: "text-gray-600 bg-gray-50 border-gray-200" },
          ].map(({ label, count, color }) => (
            <div key={label} className={`rounded-lg border px-4 py-3 text-center ${color}`}>
              <p className="text-2xl font-bold">{count}</p>
              <p className="text-xs font-medium">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Linked bills */}
      {votacao.bills.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
            Proposições relacionadas
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
                    {b.is_primary && <Badge variant="secondary" className="text-xs">Principal</Badge>}
                  </div>
                  <p className="text-sm font-medium group-hover:text-primary transition-colors line-clamp-2">
                    {b.short_title ?? b.ementa ?? b.title ?? "—"}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Individual votes */}
      {totalVotes > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
            Votos individuais ({totalVotes})
          </h2>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <Input
              type="search"
              placeholder="Buscar parlamentar..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-48 h-8 text-sm"
            />
            <div className="flex gap-1">
              {VOTE_FILTERS.map((f) => (
                <Button
                  key={f}
                  variant={voteFilter === f ? "default" : "outline"}
                  size="sm"
                  className="h-8 text-xs"
                  onClick={() => setVoteFilter(f)}
                >
                  {f}
                </Button>
              ))}
            </div>
          </div>

          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Parlamentar</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground w-16">UF</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground w-20">Partido</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground w-24">Voto</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground w-28">Orientação</th>
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
                          <Badge variant="outline" className="text-[10px] text-orange-600 border-orange-300 ml-1">Divergiu</Badge>
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
            <p className="text-center py-8 text-muted-foreground text-sm">Nenhum resultado encontrado.</p>
          )}
        </div>
      )}
    </main>
  );
}
