"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useLanguage } from "@/contexts/LanguageContext";
import { useAuth } from "@/contexts/AuthContext";
import { DonorModal } from "@/components/DonorModal";
import type { TranslationKey } from "@/lib/translations";

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
  votacao_id: number;
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

type Bill = {
  id: number;
  type: string | null;
  number: number | null;
  year: number | null;
  short_title: string | null;
  ementa: string | null;
  status: string | null;
  policy_area: string | null;
};

type Donor = {
  donor_id: number;
  name: string;
  donor_type: string;
  cpf_cnpj_masked: string | null;
  donor_state: string | null;
  amount_brl: number;
  election_year: number;
  source_type: string | null;
};

type ActivityItem = {
  event_type: "vote" | "speech";
  event_date: string;
  event_id: number;
  title: string | null;
  description: string | null;
  vote: string | null;
  votacao_id: number | null;
};

type Committee = {
  id: number;
  acronym: string | null;
  name: string | null;
  role: string | null;
  started_at: string | null;
  ended_at: string | null;
};

const VOTE_LABEL_MAP: Record<string, { labelKey: TranslationKey; color: string }> = {
  Sim:        { labelKey: "vote_label.sim",       color: "bg-green-100 text-green-800" },
  Não:        { labelKey: "vote_label.nao",       color: "bg-red-100 text-red-800" },
  Abstenção:  { labelKey: "vote_label.abstencao", color: "bg-yellow-100 text-yellow-800" },
  Obstrução:  { labelKey: "vote_label.obstrucao", color: "bg-orange-100 text-orange-800" },
};

export default function PoliticianPage({ params }: { params: { id: string } }) {
  const id = params.id;
  const { t, lang } = useLanguage();
  const dateLocale = lang === "en" ? "en-GB" : "pt-BR";

  function resolveVoteStyle(vote: string | null): { label: string; color: string } {
    const entry = VOTE_LABEL_MAP[vote ?? ""];
    if (entry) return { label: t(entry.labelKey), color: entry.color };
    return { label: vote ?? "—", color: "bg-muted text-muted-foreground" };
  }
  const { user, token } = useAuth();
  const [politician, setPolitician] = useState<Politician | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [activity, setActivity] = useState<ActivityItem[] | null>(null);
  const [votes, setVotes] = useState<Vote[] | null>(null);
  const [speeches, setSpeeches] = useState<Speech[] | null>(null);
  const [bills, setBills] = useState<Bill[] | null>(null);
  const [donors, setDonors] = useState<Donor[] | null>(null);
  const [committees, setCommittees] = useState<Committee[] | null>(null);
  const [activeDonor, setActiveDonor] = useState<{ id: number; name: string } | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [following, setFollowing] = useState<boolean | null>(null);
  const [followLoading, setFollowLoading] = useState(false);

  const TABS = [
    t("politician.tab_activity"),
    t("politician.tab_votes"),
    t("politician.tab_speeches"),
    t("politician.tab_bills"),
    t("politician.tab_donors"),
    t("politician.tab_committees"),
  ];

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

  // Fetch follow status when user is logged in
  useEffect(() => {
    if (!token) { setFollowing(null); return; }
    fetch(`${API}/politicians/${id}/follow`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setFollowing(d.following); })
      .catch(() => {});
  }, [id, token]);

  async function toggleFollow() {
    if (!token) { window.location.href = "/login"; return; }
    setFollowLoading(true);
    try {
      const method = following ? "DELETE" : "POST";
      const r = await fetch(`${API}/politicians/${id}/follow`, {
        method,
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) {
        const data = await r.json();
        setFollowing(data.following);
      }
    } finally {
      setFollowLoading(false);
    }
  }

  useEffect(() => {
    if (activeTab === 0 && activity === null) {
      fetch(`${API}/politicians/${id}/activity?page_size=20`)
        .then(r => r.json()).then(d => setActivity(d.items ?? [])).catch(() => setActivity([]));
    }
    if (activeTab === 1 && votes === null) {
      fetch(`${API}/politicians/${id}/votes?page_size=20`)
        .then(r => r.json()).then(d => setVotes(d.items ?? [])).catch(() => setVotes([]));
    }
    if (activeTab === 2 && speeches === null) {
      fetch(`${API}/politicians/${id}/speeches?page_size=20`)
        .then(r => r.json()).then(d => setSpeeches(d.items ?? [])).catch(() => setSpeeches([]));
    }
    if (activeTab === 3 && bills === null) {
      fetch(`${API}/bills/?author_politician_id=${id}&page_size=20`)
        .then(r => r.json()).then(d => setBills(d.items ?? [])).catch(() => setBills([]));
    }
    if (activeTab === 4 && donors === null) {
      fetch(`${API}/donations/politician/${id}`)
        .then(r => r.json()).then(d => setDonors(Array.isArray(d) ? d : [])).catch(() => setDonors([]));
    }
    if (activeTab === 5 && committees === null) {
      fetch(`${API}/politicians/${id}/committees`)
        .then(r => r.json()).then(d => setCommittees(Array.isArray(d) ? d : [])).catch(() => setCommittees([]));
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

  if (!politician) return <main className="max-w-5xl mx-auto px-4 py-10"><p>{t("politician.not_found")}</p></main>;

  const officeLabel = politician.current_office === "deputado"
    ? t("politician.office_deputy")
    : t("politician.office_senator");

  return (
    <main className="max-w-5xl mx-auto px-4 py-8">

      {/* Header */}
      <div className="mb-8 space-y-4">
        {/* Row 1: photo · name/badges · follow button */}
        <div className="flex gap-4 items-start">
          <div className="w-20 h-20 md:w-24 md:h-24 rounded-full overflow-hidden bg-muted ring-2 ring-border flex-shrink-0">
            {politician.photo_url ? (
              <img src={politician.photo_url} alt={politician.short_name} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-3xl font-bold text-muted-foreground">
                {politician.short_name?.[0]}
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold leading-tight">{politician.short_name}</h1>
            <div className="flex flex-wrap items-center gap-2 mt-1">
              <Badge variant="secondary">{politician.party}</Badge>
              <Badge variant="outline">{politician.state}</Badge>
              <Badge variant="outline">{officeLabel}</Badge>
            </div>
            <p className="text-sm text-muted-foreground mt-1">{politician.name}</p>
          </div>
          <Button
            variant={following ? "default" : "outline"}
            size="sm"
            className="flex-shrink-0"
            onClick={toggleFollow}
            disabled={followLoading}
          >
            {following ? t("politician.following") : t("politician.follow")}
          </Button>
        </div>

        {/* Row 2: bio + stats — full width on all screen sizes */}
        {(politician.ai_bio || stats?.votes !== undefined) && (
          <div>
            {politician.ai_bio && (
              <p className="text-sm text-foreground/80 mb-3">{politician.ai_bio}</p>
            )}
            {stats?.votes !== undefined && (
              <div className="flex flex-wrap gap-3 text-sm">
                <span className="bg-muted px-3 py-1 rounded-full text-muted-foreground">
                  <strong className="text-foreground">{stats.votes.toLocaleString("pt-BR")}</strong> {t("politician.stat_votes")}
                </span>
                <span className="bg-muted px-3 py-1 rounded-full text-muted-foreground">
                  <strong className="text-foreground">{stats.speeches.toLocaleString("pt-BR")}</strong> {t("politician.stat_speeches")}
                </span>
                <span className="bg-muted px-3 py-1 rounded-full text-muted-foreground">
                  <strong className="text-foreground">{stats.bills.toLocaleString("pt-BR")}</strong> {t("politician.stat_bills")}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b mb-6">
        <div className="flex gap-0 overflow-x-auto scrollbar-none -mx-4 px-4">
          {TABS.map((tab, i) => (
            <button
              key={tab}
              onClick={() => setActiveTab(i)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap flex-shrink-0 ${
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
        activity === null ? <TabSkeleton />
          : activity.length === 0
          ? <EmptyState message={t("politician.empty_activity")} />
          : <div className="space-y-3">
              {activity.map((item) => {
                const date = item.event_date
                  ? new Date(item.event_date).toLocaleDateString(dateLocale)
                  : "—";
                if (item.event_type === "vote") {
                  const voteStyle = resolveVoteStyle(item.vote);
                  const card = (
                    <Card>
                      <CardContent className="p-4 flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <Badge variant="outline" className="text-xs mb-1">{t("politician.badge_vote")}</Badge>
                          <p className="text-sm font-medium truncate">{item.title ?? t("politician.no_title")}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">{date}</p>
                        </div>
                        <span className={`text-xs font-semibold px-2 py-1 rounded-full flex-shrink-0 ${voteStyle.color}`}>
                          {voteStyle.label}
                        </span>
                      </CardContent>
                    </Card>
                  );
                  return item.votacao_id
                    ? <Link key={`vote-${item.event_id}`} href={`/votacao/${item.votacao_id}`} className="block hover:opacity-80 transition-opacity">{card}</Link>
                    : <div key={`vote-${item.event_id}`}>{card}</div>;
                }
                return (
                  <Card key={`speech-${item.event_id}`}>
                    <CardContent className="p-4">
                      <Badge variant="outline" className="text-xs mb-1">{t("politician.badge_speech")}</Badge>
                      <p className="text-sm font-medium">{item.title ?? t("politician.badge_speech")}</p>
                      {item.description && <p className="text-sm text-muted-foreground mt-1">{item.description}</p>}
                      <p className="text-xs text-muted-foreground mt-1">{date}</p>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
      )}

      {/* Votações */}
      {activeTab === 1 && (
        votes === null ? <TabSkeleton />
          : votes.length === 0
          ? <EmptyState message={t("politician.empty_votes")} />
          : <div className="space-y-3">
              {votes.map((v, i) => {
                const voteStyle = resolveVoteStyle(v.vote);
                return (
                  <Link key={i} href={`/votacao/${v.votacao_id}`} className="block hover:opacity-80 transition-opacity">
                    <Card>
                      <CardContent className="p-4 flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">
                            {v.short_title ?? v.description ?? t("politician.no_title")}
                          </p>
                          {v.type && v.number && (
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {v.type} {v.number}/{v.year}
                            </p>
                          )}
                          {v.party_orientation && v.followed_orientation === false && (
                            <p className="text-xs text-orange-600 mt-0.5">{t("politician.diverged")} ({v.party_orientation})</p>
                          )}
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <span className={`text-xs font-semibold px-2 py-1 rounded-full ${voteStyle.color}`}>
                            {voteStyle.label}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {v.voted_at ? new Date(v.voted_at).toLocaleDateString(dateLocale) : "—"}
                          </span>
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                );
              })}
            </div>
      )}

      {/* Discursos */}
      {activeTab === 2 && (
        speeches === null ? <TabSkeleton />
          : speeches.length === 0
          ? <EmptyState message={t("politician.empty_speeches")} />
          : <div className="space-y-3">
              {speeches.map((s) => (
                <Link key={s.id} href={`/discurso/${s.id}`}>
                  <Card className="hover:border-primary/40 hover:bg-muted/20 transition-all cursor-pointer">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4 mb-2">
                        <span className="text-xs text-muted-foreground">
                          {s.delivered_at ? new Date(s.delivered_at).toLocaleDateString(dateLocale) : "—"}
                          {s.phase && ` · ${s.phase}`}
                        </span>
                      </div>
                      <p className="text-sm">{s.summary ?? t("politician.no_summary")}</p>
                      {s.keywords && s.keywords.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {s.keywords.slice(0, 4).map((k) => <Badge key={k} variant="secondary" className="text-xs">{k}</Badge>)}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
      )}

      {/* Projetos de Lei */}
      {activeTab === 3 && (
        bills === null ? <TabSkeleton />
          : bills.length === 0
          ? <EmptyState message={t("politician.empty_bills_note")} />
          : <div className="space-y-3">
              {bills.map((b) => (
                <Link key={b.id} href={`/proposicao/${b.id}`} className="block hover:opacity-80 transition-opacity">
                  <Card>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium">
                            {b.short_title ?? b.ementa ?? t("bills.no_title")}
                          </p>
                          {b.type && b.number && (
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {b.type} {b.number}/{b.year}
                            </p>
                          )}
                          {b.policy_area && (
                            <Badge variant="secondary" className="mt-1 text-xs">{b.policy_area}</Badge>
                          )}
                        </div>
                        {b.status && (
                          <Badge variant="outline" className="flex-shrink-0 text-xs">{b.status}</Badge>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
      )}

      {/* Doadores */}
      {activeTab === 4 && (
        donors === null ? <TabSkeleton />
          : donors.length === 0
          ? <EmptyState message={t("politician.empty_donors")} />
          : <div>
              <p className="text-xs text-muted-foreground mb-3">
                {t("politician.donors_note")}
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs text-muted-foreground">
                      <th className="pb-2 font-medium">{t("politician.donors_col_name")}</th>
                      <th className="pb-2 font-medium">{t("politician.donors_col_type")}</th>
                      <th className="pb-2 font-medium">{t("politician.donors_col_year")}</th>
                      <th className="pb-2 font-medium text-right">{t("politician.donors_col_amount")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {donors.map((d, i) => (
                      <tr key={i} className="border-b last:border-0">
                        <td className="py-2 pr-4">
                          <button
                            className="text-left hover:text-primary transition-colors"
                            onClick={() => setActiveDonor({ id: d.donor_id, name: d.name })}
                          >
                            <p className="font-medium truncate max-w-[200px] underline-offset-2 hover:underline">{d.name}</p>
                            {d.cpf_cnpj_masked && (
                              <p className="text-xs text-muted-foreground">{d.cpf_cnpj_masked}</p>
                            )}
                          </button>
                        </td>
                        <td className="py-2 pr-4 text-xs text-muted-foreground whitespace-nowrap">
                          {d.donor_type === "individual" ? t("politician.donor_individual") : t("politician.donor_company")}
                        </td>
                        <td className="py-2 pr-4 text-xs text-muted-foreground">{d.election_year}</td>
                        <td className="py-2 text-right font-medium tabular-nums whitespace-nowrap">
                          {d.amount_brl.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
      )}

      {/* Comissões */}
      {activeTab === 5 && (
        committees === null ? <TabSkeleton />
          : committees.length === 0
          ? <EmptyState message={t("politician.empty_committees")} />
          : <div className="space-y-2">
              {committees.map((c) => (
                <div key={c.id} className="flex items-start justify-between gap-3 p-3 rounded-lg border">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{c.name ?? c.acronym ?? "—"}</p>
                    {c.acronym && c.name && (
                      <p className="text-xs text-muted-foreground">{c.acronym}</p>
                    )}
                  </div>
                  <div className="flex-shrink-0 text-right">
                    {c.role && (
                      <Badge variant={c.ended_at ? "secondary" : "default"} className="text-xs">
                        {c.role}
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
      )}


      {/* Donor detail modal */}
      {activeDonor && (
        <DonorModal
          donorId={activeDonor.id}
          donorName={activeDonor.name}
          onClose={() => setActiveDonor(null)}
        />
      )}
    </main>
  );
}
function EmptyState({ message }: { message: string }) {
  return (
    <div className="text-center py-16 text-muted-foreground text-sm">{message}</div>
  );
}

function TabSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="animate-pulse bg-muted rounded-lg h-16" />
      ))}
    </div>
  );
}
