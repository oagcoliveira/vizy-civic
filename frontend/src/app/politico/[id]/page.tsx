"use client";

import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const API = process.env.NEXT_PUBLIC_API_URL;

type Politician = {
  id: number;
  short_name: string;
  name: string;
  state: string;
  current_office: string;
  photo_url: string | null;
  party: string;
  gender: string;
  ai_bio: string | null;
  email: string | null;
  website_url: string | null;
};

type Stats = { votes: number; speeches: number; bills: number };

type Vote = {
  vote: string;
  voted_at: string;
  short_title: string | null;
  description: string | null;
  type: string | null;
  number: number | null;
  year: number | null;
  party_orientation: string | null;
  followed_orientation: boolean | null;
};

type Speech = {
  id: number;
  delivered_at: string;
  phase: string | null;
  summary: string | null;
  keywords: string[] | null;
  full_text_url: string | null;
};

const VOTE_LABEL: Record<string, { label: string; color: string }> = {
  Sim:        { label: "Sim",        color: "bg-green-100 text-green-800" },
  Não:        { label: "Não",        color: "bg-red-100 text-red-800" },
  Abstenção:  { label: "Abstenção",  color: "bg-yellow-100 text-yellow-800" },
  Obstrução:  { label: "Obstrução",  color: "bg-orange-100 text-orange-800" },
};

const TABS = ["Atividade recente", "Votações", "Discursos", "Projetos de Lei", "Doadores"];

export default function PoliticianPage({ params }: { params: { id: string } }) {
  const id = params.id;
  const [politician, setPolitician] = useState<Politician | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [votes, setVotes] = useState<Vote[]>([]);
  const [speeches, setSpeeches] = useState<Speech[]>([]);
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/politicians/${id}`).then(r => r.json()),
      fetch(`${API}/politicians/${id}/stats`).then(r => r.json()),
    ]).then(([pol, st]) => {
      setPolitician(pol);
      setStats(st);
      setLoading(false);
    });
  }, [id]);

  useEffect(() => {
    if (activeTab === 1 && votes.length === 0) {
      fetch(`${API}/politicians/${id}/votes?page_size=20`).then(r => r.json()).then(d => setVotes(d.items));
    }
    if (activeTab === 2 && speeches.length === 0) {
      fetch(`${API}/politicians/${id}/speeches?page_size=20`).then(r => r.json()).then(d => setSpeeches(d.items));
    }
  }, [activeTab, id]);

  if (loading) return (
    <main className="max-w-5xl mx-auto px-4 py-10">
      <div className="animate-pulse space-y-4">
        <div className="flex gap-6 items-center">
          <div className="w-24 h-24 rounded-full bg-muted" />
          <div className="space-y-2">
            <div className="h-6 w-48 bg-muted rounded" />
            <div className="h-4 w-32 bg-muted rounded" />
          </div>
        </div>
      </div>
    </main>
  );

  if (!politician) return <main className="max-w-5xl mx-auto px-4 py-10"><p>Parlamentar não encontrado.</p></main>;

  const officeLabel = politician.current_office === "deputado" ? "Deputado Federal" : "Senador";

  return (
    <main className="max-w-5xl mx-auto px-4 py-8">

      {/* Header */}
      <div className="flex gap-6 items-start mb-8">
        <div className="w-24 h-24 rounded-full overflow-hidden bg-muted ring-2 ring-border flex-shrink-0">
          {politician.photo_url ? (
            <img src={politician.photo_url} alt={politician.short_name} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-3xl font-bold text-muted-foreground">
              {politician.short_name?.[0]}
            </div>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold">{politician.short_name}</h1>
            <Badge variant="secondary">{politician.party}</Badge>
            <Badge variant="outline">{politician.state}</Badge>
            <Badge variant="outline">{officeLabel}</Badge>
          </div>
          <p className="text-sm text-muted-foreground mb-3">{politician.name}</p>
          {politician.ai_bio && (
            <p className="text-sm text-foreground/80 mb-3">{politician.ai_bio}</p>
          )}
          {/* Stats */}
          {stats?.votes !== undefined && (
            <div className="flex flex-wrap gap-3 text-sm">
              <span className="bg-muted px-3 py-1 rounded-full text-muted-foreground">
                <strong className="text-foreground">{stats.votes.toLocaleString("pt-BR")}</strong> votos nominais
              </span>
              <span className="bg-muted px-3 py-1 rounded-full text-muted-foreground">
                <strong className="text-foreground">{stats.speeches.toLocaleString("pt-BR")}</strong> discursos
              </span>
              <span className="bg-muted px-3 py-1 rounded-full text-muted-foreground">
                <strong className="text-foreground">{stats.bills.toLocaleString("pt-BR")}</strong> projetos de lei
              </span>
            </div>
          )}
        </div>
        <Button variant="outline" size="sm" className="flex-shrink-0">+ Seguir</Button>
      </div>

      {/* Tabs */}
      <div className="border-b mb-6">
        <div className="flex gap-0">
          {TABS.map((tab, i) => (
            <button
              key={tab}
              onClick={() => setActiveTab(i)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === i
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}

      {/* Atividade recente */}
      {activeTab === 0 && (
        <EmptyState message="Execute o ETL de votos e discursos para ver a atividade recente." />
      )}

      {/* Votações */}
      {activeTab === 1 && (
        votes.length === 0
          ? <EmptyState message="Nenhum voto nominal registrado ainda." />
          : <div className="space-y-3">
              {votes.map((v, i) => {
                const voteStyle = VOTE_LABEL[v.vote] ?? { label: v.vote, color: "bg-muted text-muted-foreground" };
                return (
                  <Card key={i}>
                    <CardContent className="p-4 flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {v.short_title ?? v.description ?? "Votação sem título"}
                        </p>
                        {v.type && v.number && (
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {v.type} {v.number}/{v.year}
                          </p>
                        )}
                        {v.party_orientation && v.followed_orientation === false && (
                          <p className="text-xs text-orange-600 mt-0.5">Divergiu da orientação do partido ({v.party_orientation})</p>
                        )}
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className={`text-xs font-semibold px-2 py-1 rounded-full ${voteStyle.color}`}>
                          {voteStyle.label}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {v.voted_at ? new Date(v.voted_at).toLocaleDateString("pt-BR") : "—"}
                        </span>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
      )}

      {/* Discursos */}
      {activeTab === 2 && (
        speeches.length === 0
          ? <EmptyState message="Nenhum discurso registrado ainda." />
          : <div className="space-y-3">
              {speeches.map((s) => (
                <Card key={s.id}>
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-4 mb-2">
                      <span className="text-xs text-muted-foreground">
                        {s.delivered_at ? new Date(s.delivered_at).toLocaleDateString("pt-BR") : "—"}
                        {s.phase && ` · ${s.phase}`}
                      </span>
                      {s.full_text_url && (
                        <a href={s.full_text_url} target="_blank" rel="noopener noreferrer"
                          className="text-xs text-primary hover:underline flex-shrink-0">
                          Ver íntegra
                        </a>
                      )}
                    </div>
                    <p className="text-sm">{s.summary ?? "Resumo não disponível."}</p>
                    {s.keywords && s.keywords.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {s.keywords.map((k) => <Badge key={k} variant="secondary">{k}</Badge>)}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
      )}

      {/* Projetos de Lei */}
      {activeTab === 3 && <EmptyState message="Nenhum projeto de lei registrado ainda." />}

      {/* Doadores */}
      {activeTab === 4 && <EmptyState message="Dados do TSE não carregados ainda." />}

    </main>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="text-center py-16 text-muted-foreground text-sm">{message}</div>
  );
}
