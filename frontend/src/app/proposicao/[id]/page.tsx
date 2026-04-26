"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { useLanguage } from "@/contexts/LanguageContext";
import { useAuth } from "@/contexts/AuthContext";

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
  // Completeness signals from the API
  needs_enrichment: boolean;
};

type LegislativeEvent = {
  id: number;
  sequence: number;
  event_date: string | null;
  stage: string | null;
  description: string | null;
  summary: string | null;
  venue: string | null;
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
  if (s.includes("arquivad") || s.includes("prejudicad")) return "outline";
  return "secondary";
}

function formatDate(ts: string | null) {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

type EnrichStatus = "idle" | "loading" | "success" | "error";

export default function BillPage({ params }: { params: { id: string } }) {
  const { t } = useLanguage();
  const { token } = useAuth();
  const [bill, setBill] = useState<Bill | null>(null);
  const [votacoes, setVotacoes] = useState<VotacaoLink[]>([]);
  const [events, setEvents] = useState<LegislativeEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [tracking, setTracking] = useState<boolean | null>(null);
  const [trackLoading, setTrackLoading] = useState(false);
  const [enrichStatus, setEnrichStatus] = useState<EnrichStatus>("idle");
  const [enrichMessage, setEnrichMessage] = useState<string | null>(null);

  function resultBadge(result: string | null) {
    if (result === "1" || result?.toLowerCase().includes("aprovad"))
      return <Badge className="bg-green-100 text-green-800 border-green-200">{t("votes.badge_approved")}</Badge>;
    if (result === "0" || result?.toLowerCase().includes("rejeitad"))
      return <Badge className="bg-red-100 text-red-800 border-red-200">{t("votes.badge_rejected")}</Badge>;
    return <Badge variant="secondary">{result ?? "—"}</Badge>;
  }

  useEffect(() => {
    fetch(`${API}/bills/${params.id}`)
      .then((r) => r.json())
      .then((data) => { setBill(data); setLoading(false); });

    fetch(`${API}/bills/${params.id}/votacoes?page_size=20`)
      .then((r) => r.json())
      .then((data) => setVotacoes(data.items ?? []));

    fetch(`${API}/bills/${params.id}/events`)
      .then((r) => r.json())
      .then((data) => setEvents(Array.isArray(data) ? data : []))
      .catch(() => {});
  }, [params.id]);

  useEffect(() => {
    if (!token) { setTracking(null); return; }
    fetch(`${API}/bills/${params.id}/track`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setTracking(d.tracking); })
      .catch(() => {});
  }, [params.id, token]);

  async function toggleTrack() {
    if (!token) { window.location.href = "/login"; return; }
    setTrackLoading(true);
    try {
      const method = tracking ? "DELETE" : "POST";
      const r = await fetch(`${API}/bills/${params.id}/track`, {
        method,
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) {
        const data = await r.json();
        setTracking(data.tracking);
      }
    } finally {
      setTrackLoading(false);
    }
  }

  async function handleEnrich() {
    if (!token) return;
    setEnrichStatus("loading");
    setEnrichMessage(null);
    try {
      const r = await fetch(`${API}/bills/${params.id}/enrich`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await r.json();
      if (r.status === 202) {
        setEnrichStatus("success");
        setEnrichMessage("Enriquecimento iniciado. Os dados serão atualizados em instantes.");
        // Reload bill data after a short delay so the user sees the updated fields
        setTimeout(() => {
          fetch(`${API}/bills/${params.id}`)
            .then((res) => res.json())
            .then((updated) => setBill(updated))
            .catch(() => {});
          fetch(`${API}/bills/${params.id}/events`)
            .then((res) => res.json())
            .then((data) => setEvents(Array.isArray(data) ? data : []))
            .catch(() => {});
        }, 8000);
      } else if (r.status === 409) {
        setEnrichStatus("idle");
        setEnrichMessage("Esta proposição já está completamente enriquecida.");
      } else {
        setEnrichStatus("error");
        setEnrichMessage(data.detail ?? "Erro ao iniciar enriquecimento.");
      }
    } catch {
      setEnrichStatus("error");
      setEnrichMessage("Erro de rede ao tentar enriquecer.");
    }
  }

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
        <p className="text-muted-foreground">{t("bill.not_found")}</p>
        <Link href="/votacoes" className="text-primary text-sm mt-2 block">{t("bill.back_short")}</Link>
      </main>
    );
  }

  const headline = bill.short_title ?? bill.ementa ?? bill.title ?? t("bills.no_title");
  const body = bill.summary ?? bill.ementa;

  return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <Link href="/votacoes" className="text-sm text-muted-foreground hover:text-primary mb-4 block">
        {t("bill.back")}
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
          <div className="ml-auto flex items-center gap-2">
            {/* Enrich button — shown to any logged-in user when the bill has missing data */}
            {token && bill.needs_enrichment && (
              <button
                onClick={handleEnrich}
                disabled={enrichStatus === "loading"}
                title="Enriquecer esta proposição com dados da API da Câmara e IA"
                className="text-sm font-medium px-3 py-1 rounded-md border transition-colors disabled:opacity-60 text-amber-700 border-amber-300 bg-amber-50 hover:bg-amber-100"
              >
                {enrichStatus === "loading" ? "Enriquecendo..." : "✦ Enriquecer"}
              </button>
            )}
            <button
              onClick={toggleTrack}
              disabled={trackLoading}
              className={`text-sm font-medium px-3 py-1 rounded-md border transition-colors disabled:opacity-60 ${
                tracking
                  ? "bg-primary text-primary-foreground border-primary"
                  : "text-muted-foreground hover:text-foreground border-border"
              }`}
            >
              {tracking ? t("bill.tracking") : t("bill.track")}
            </button>
          </div>
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

      {/* Enrich status message */}
      {enrichMessage && (
        <div className={`mb-4 px-4 py-2 rounded-md text-sm border ${
          enrichStatus === "success"
            ? "bg-green-50 border-green-200 text-green-800"
            : enrichStatus === "error"
            ? "bg-red-50 border-red-200 text-red-800"
            : "bg-amber-50 border-amber-200 text-amber-800"
        }`}>
          {enrichMessage}
        </div>
      )}

      {/* Author */}
      {(bill.author_name || bill.author_label) && (
        <div className="flex items-center gap-3 mb-6 p-3 rounded-lg border bg-muted/30">
          {bill.author_photo && (
            <img src={bill.author_photo} alt={bill.author_name ?? ""} className="w-10 h-10 rounded-full object-cover" />
          )}
          <div>
            <p className="text-xs text-muted-foreground">{t("bill.author")}</p>
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
        <h2 className="text-lg font-semibold mb-3">{t("bill.what_is")}</h2>
        {body ? (
          <p className="text-muted-foreground leading-relaxed">{body}</p>
        ) : (
          <p className="text-muted-foreground italic">{t("bill.no_summary")}</p>
        )}
        {bill.full_text_url && (
          <a
            href={bill.full_text_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary text-sm hover:underline mt-3 block"
          >
            {t("bill.read_full")}
          </a>
        )}
        {!bill.summary && bill.ementa && (
          <p className="text-xs text-muted-foreground mt-3 italic">
            {t("bill.summary_soon")}
          </p>
        )}
      </section>

      {/* Votações */}
      {votacoes.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold mb-3">{t("bill.votes_section")}</h2>
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

      {/* Tramitação */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">{t("bill.trail_section")}</h2>
        {events.length === 0 ? (
          <p className="text-muted-foreground text-sm italic">{t("bill.trail_soon")}</p>
        ) : (
          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-3 top-0 bottom-0 w-px bg-border" />
            <div className="space-y-4">
              {events.slice().reverse().map((ev) => (
                <div key={ev.id} className="relative pl-10">
                  {/* Dot */}
                  <div className="absolute left-2 top-1.5 w-2.5 h-2.5 rounded-full bg-primary border-2 border-background" />
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium">
                        {ev.summary ?? ev.stage ?? "—"}
                      </p>
                      {ev.description && ev.description !== ev.stage && (
                        <p className="text-xs text-muted-foreground mt-0.5">{ev.description}</p>
                      )}
                      {ev.venue && (
                        <span className="text-xs text-muted-foreground">{ev.venue}</span>
                      )}
                    </div>
                    <span className="text-xs text-muted-foreground flex-shrink-0">
                      {ev.event_date ? formatDate(ev.event_date) : "—"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
