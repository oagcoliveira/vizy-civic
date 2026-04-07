"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";

const API = process.env.NEXT_PUBLIC_API_URL;

type Bill = {
  id: number;
  source: string;
  external_id: number;
  type: string | null;
  number: number | null;
  year: number | null;
  title: string | null;
  ementa: string | null;
  short_title: string | null;
  summary: string | null;
  status: string | null;
  policy_area: string | null;
  policy_tags: string[] | null;
  author_label: string | null;
  full_text_url: string | null;
  author_politician_id: number | null;
  author_name: string | null;
  author_photo: string | null;
  author_state: string | null;
  author_party: string | null;
};

type VotacaoLink = {
  id: number;
  description: string | null;
  voted_at: string | null;
  result: string | null;
  vote_type: string | null;
  is_primary: boolean;
};

function statusColor(status: string | null) {
  if (!status) return "secondary";
  const s = status.toLowerCase();
  if (s.includes("norma jurídica") || s.includes("aprovad")) return "default";
  if (s.includes("arquivad") || s.includes("prejudicad")) return "destructive";
  return "secondary";
}

function resultBadge(result: string | null) {
  if (result === "1" || result?.toLowerCase().includes("aprovad"))
    return <Badge className="bg-green-100 text-green-800 border-green-200">Aprovada</Badge>;
  if (result === "0" || result?.toLowerCase().includes("rejeitad"))
    return <Badge className="bg-red-100 text-red-800 border-red-200">Rejeitada</Badge>;
  return <Badge variant="secondary">{result ?? "—"}</Badge>;
}

function formatDate(ts: string | null) {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function BillPage({ params }: { params: { id: string } }) {
  const [bill, setBill] = useState<Bill | null>(null);
  const [votacoes, setVotacoes] = useState<VotacaoLink[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/bills/${params.id}`)
      .then((r) => r.json())
      .then((data) => { setBill(data); setLoading(false); });

    fetch(`${API}/bills/${params.id}/votacoes?page_size=20`)
      .then((r) => r.json())
      .then((data) => setVotacoes(data.items ?? []));
  }, [params.id]);

  if (loading) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-muted rounded w-24" />
          <div className="h-10 bg-muted rounded w-3/4" />
          <div className="h-4 bg-muted rounded w-full" />
          <div className="h-4 bg-muted rounded w-5/6" />
        </div>
      </main>
    );
  }

  if (!bill) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-8">
        <p className="text-muted-foreground">Proposição não encontrada.</p>
        <Link href="/votacoes" className="text-primary text-sm mt-2 block">← Voltar</Link>
      </main>
    );
  }

  const headline = bill.short_title ?? bill.ementa ?? bill.title ?? "Sem título";
  const body = bill.summary ?? bill.ementa;

  return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <Link href="/votacoes" className="text-sm text-muted-foreground hover:text-primary mb-4 block">
        ← Base de Votações
      </Link>

      {/* Header */}
      <div className="mb-6">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {bill.type && bill.number && bill.year && (
            <Badge variant="outline" className="text-sm font-mono">
              {bill.type} {bill.number}/{bill.year}
            </Badge>
          )}
          {bill.status && (
            <Badge variant={statusColor(bill.status)} className="text-xs">
              {bill.status}
            </Badge>
          )}
          {bill.policy_area && (
            <Badge variant="secondary" className="text-xs">{bill.policy_area}</Badge>
          )}
        </div>
        <h1 className="text-2xl font-bold leading-snug mb-2">{headline}</h1>
        {bill.policy_tags && bill.policy_tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {bill.policy_tags.map((tag) => (
              <Badge key={tag} variant="outline" className="text-xs">{tag}</Badge>
            ))}
          </div>
        )}
      </div>

      {/* Author */}
      {(bill.author_name || bill.author_label) && (
        <div className="flex items-center gap-3 mb-6 p-3 rounded-lg border bg-muted/30">
          {bill.author_photo && (
            <img src={bill.author_photo} alt={bill.author_name ?? ""} className="w-10 h-10 rounded-full object-cover" />
          )}
          <div>
            <p className="text-xs text-muted-foreground">Autor</p>
            {bill.author_politician_id ? (
              <Link href={`/politico/${bill.author_politician_id}`} className="font-medium hover:text-primary transition-colors">
                {bill.author_name}
                {bill.author_party && <span className="text-muted-foreground text-sm ml-1">· {bill.author_party}-{bill.author_state}</span>}
              </Link>
            ) : (
              <p className="font-medium">{bill.author_label}</p>
            )}
          </div>
        </div>
      )}

      {/* O que é? */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">O que é?</h2>
        {body ? (
          <p className="text-muted-foreground leading-relaxed">{body}</p>
        ) : (
          <p className="text-muted-foreground italic">Resumo não disponível.</p>
        )}
        {bill.full_text_url && (
          <a
            href={bill.full_text_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary text-sm hover:underline mt-3 block"
          >
            Ler texto integral na Câmara dos Deputados →
          </a>
        )}
        {!bill.summary && bill.ementa && (
          <p className="text-xs text-muted-foreground mt-3 italic">
            Resumo simplificado em breve — exibindo ementa oficial.
          </p>
        )}
      </section>

      {/* Votações */}
      {votacoes.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold mb-3">Votações</h2>
          <div className="space-y-2">
            {votacoes.map((v) => (
              <Link
                key={v.id}
                href={`/votacao/${v.id}`}
                className="flex items-center justify-between p-3 rounded-lg border hover:border-primary/40 hover:bg-muted/30 transition-all group"
              >
                <div>
                  <p className="text-sm font-medium group-hover:text-primary transition-colors line-clamp-1">
                    {v.description ?? "Votação"}
                  </p>
                  <p className="text-xs text-muted-foreground">{formatDate(v.voted_at)}</p>
                </div>
                {resultBadge(v.result)}
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Tramitação placeholder */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Tramitação</h2>
        <p className="text-muted-foreground text-sm italic">
          Histórico legislativo em breve.
        </p>
      </section>
    </main>
  );
}
