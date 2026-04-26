"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { useLanguage } from "@/contexts/LanguageContext";
import { useAuth } from "@/contexts/AuthContext";

const API = process.env.NEXT_PUBLIC_API_URL;

type FeedItem = {
  event_type: "vote" | "speech" | "bill_vote";
  id: number;
  politician_id: number | null;
  bill_id: number | null;
  votacao_id: number | null;
  occurred_at: string | null;
  title: string | null;
  detail: string | null;
};

type FollowedPolitician = {
  politician_id: number;
  short_name: string;
  state: string | null;
  party: string | null;
  photo_url: string | null;
};

type TrackedBill = {
  bill_id: number;
  type: string | null;
  number: number | null;
  year: number | null;
  short_title: string | null;
  status: string | null;
};

function formatDate(ts: string | null, locale: string) {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/** Colour-coded badge for vote results (Aprovada / Rejeitada / other) */
function ResultBadge({ result }: { result: string | null }) {
  if (!result) return null;
  const lower = result.toLowerCase();
  const approved = lower.includes("aprovad");
  const rejected = lower.includes("rejeitad");
  const cls = approved
    ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
    : rejected
    ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"
    : "bg-muted text-muted-foreground";
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${cls}`}>
      {result}
    </span>
  );
}

export default function FeedPage() {
  const { t, lang } = useLanguage();
  const { token, loading: authLoading } = useAuth();
  const dateLocale = lang === "en" ? "en-GB" : "pt-BR";

  const [follows, setFollows] = useState<FollowedPolitician[]>([]);
  const [tracks, setTracks] = useState<TrackedBill[]>([]);
  const [items, setItems] = useState<FeedItem[]>([]);
  const [filter, setFilter] = useState<"" | "vote" | "speech" | "bill_vote">("");
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);

  // Fetch followed politicians for sidebar
  useEffect(() => {
    if (!token) return;
    fetch(`${API}/auth/me/follows`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => setFollows(Array.isArray(data) ? data : []))
      .catch(() => {});
  }, [token]);

  // Fetch tracked bills for sidebar
  useEffect(() => {
    if (!token) return;
    fetch(`${API}/auth/me/tracks`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => setTracks(Array.isArray(data) ? data : []))
      .catch(() => {});
  }, [token]);

  const fetchFeed = useCallback(
    async (pageNum: number, eventType: string, append: boolean) => {
      if (!token) return;
      setLoading(true);
      try {
        const params = new URLSearchParams({
          page: String(pageNum),
          page_size: "20",
        });
        if (eventType) params.set("event_type", eventType);

        const r = await fetch(`${API}/feed/?${params}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await r.json();
        const newItems: FeedItem[] = data.items ?? [];
        setItems((prev) => (append ? [...prev, ...newItems] : newItems));
        setHasMore(newItems.length === 20);
      } finally {
        setLoading(false);
      }
    },
    [token]
  );

  useEffect(() => {
    if (authLoading || !token) {
      if (!authLoading) setLoading(false);
      return;
    }
    setPage(1);
    fetchFeed(1, filter, false);
  }, [token, filter, authLoading, fetchFeed]);

  function loadMore() {
    const next = page + 1;
    setPage(next);
    fetchFeed(next, filter, true);
  }

  const hasAnyFollows = follows.length > 0 || tracks.length > 0;

  // Redirect if not logged in
  if (!authLoading && !token) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-16 text-center">
        <p className="text-muted-foreground mb-4">{t("feed.not_logged_in")}</p>
        <Link href="/login" className="text-primary hover:underline">
          {t("nav.login")}
        </Link>
      </main>
    );
  }

  return (
    <main className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">{t("feed.title")}</h1>

      <div className="flex gap-6">
        {/* Sidebar */}
        <aside className="hidden md:block w-56 flex-shrink-0 space-y-6">

          {/* Followed politicians */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              {t("feed.following_title")}
            </p>
            {follows.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("feed.no_follows")}</p>
            ) : (
              <ul className="space-y-2">
                {follows.map((p) => (
                  <li key={p.politician_id}>
                    <Link
                      href={`/politico/${p.politician_id}`}
                      className="flex items-center gap-2 group"
                    >
                      {p.photo_url ? (
                        <img
                          src={p.photo_url}
                          alt={p.short_name}
                          className="w-7 h-7 rounded-full object-cover flex-shrink-0"
                        />
                      ) : (
                        <div className="w-7 h-7 rounded-full bg-muted flex-shrink-0" />
                      )}
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
                          {p.short_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {[p.party, p.state].filter(Boolean).join("-")}
                        </p>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-3">
              <Link href="/deputados" className="text-xs text-primary hover:underline">
                + {t("feed.browse_deputies")}
              </Link>
            </div>
          </div>

          {/* Tracked bills */}
          <div className="pt-4 border-t">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              {t("feed.tracking_title")}
            </p>
            {tracks.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("feed.no_tracks")}</p>
            ) : (
              <ul className="space-y-2">
                {tracks.map((b) => (
                  <li key={b.bill_id}>
                    <Link
                      href={`/proposicao/${b.bill_id}`}
                      className="group block"
                    >
                      <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
                        {(b.short_title ?? `${b.type ?? ""}${b.number ? ` ${b.number}` : ""}${b.year ? `/${b.year}` : ""}`.trim()) || `#${b.bill_id}`}
                      </p>
                      {b.status && (
                        <p className="text-xs text-muted-foreground truncate">{b.status}</p>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-3">
              <Link href="/proposicoes" className="text-xs text-primary hover:underline">
                + {t("feed.browse_bills")}
              </Link>
            </div>
          </div>

        </aside>

        {/* Main feed */}
        <div className="flex-1 min-w-0">
          {/* Filter bar */}
          <div className="flex gap-2 mb-5 flex-wrap">
            {(
              [
                { key: "", label: t("feed.filter_all") },
                { key: "vote", label: t("feed.filter_votes") },
                { key: "speech", label: t("feed.filter_speeches") },
                { key: "bill_vote", label: t("feed.filter_bill_votes") },
              ] as { key: "" | "vote" | "speech" | "bill_vote"; label: string }[]
            ).map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium border transition-colors ${
                  filter === key
                    ? "bg-primary text-primary-foreground border-primary"
                    : "text-muted-foreground hover:text-foreground border-border"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* No follows/tracks state */}
          {!loading && !hasAnyFollows && (
            <div className="text-center py-16">
              <p className="text-muted-foreground mb-1">{t("feed.no_follows")}</p>
              <p className="text-sm text-muted-foreground">{t("feed.no_follows_cta")}</p>
              <Link
                href="/deputados"
                className="mt-4 inline-block text-sm text-primary hover:underline"
              >
                {t("home.cta_deputies")} →
              </Link>
            </div>
          )}

          {/* Feed items */}
          {loading && items.length === 0 ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="animate-pulse rounded-lg border p-4">
                  <div className="flex gap-3">
                    <div className="w-8 h-8 rounded-full bg-muted flex-shrink-0" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 bg-muted rounded w-1/3" />
                      <div className="h-3 bg-muted rounded w-3/4" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : items.length === 0 && hasAnyFollows ? (
            <p className="text-muted-foreground text-sm italic py-8 text-center">
              {t("feed.empty_combined")}
            </p>
          ) : (
            <div className="space-y-3">
              {items.map((item, idx) => {
                const isBillVote = item.event_type === "bill_vote";
                const isVote = item.event_type === "vote";
                const politician = follows.find(
                  (f) => f.politician_id === item.politician_id
                );
                const trackedBill = tracks.find(
                  (b) => b.bill_id === item.bill_id
                );

                const cardContent = (
                  <div className="flex items-start gap-3 p-4 rounded-lg border hover:border-primary/40 hover:bg-muted/30 transition-all">
                    {/* Avatar / bill icon */}
                    {isBillVote ? (
                      <div className="w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <span className="text-xs font-bold text-primary">
                          {trackedBill?.type ?? "PL"}
                        </span>
                      </div>
                    ) : politician?.photo_url ? (
                      <img
                        src={politician.photo_url}
                        alt={politician.short_name}
                        className="w-8 h-8 rounded-full object-cover flex-shrink-0 mt-0.5"
                      />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-muted flex-shrink-0 mt-0.5" />
                    )}

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        {/* Subject label */}
                        {isBillVote ? (
                          <span className="text-sm font-medium">
                            {trackedBill
                              ? (`${trackedBill.type ?? ""}${trackedBill.number ? ` ${trackedBill.number}` : ""}${trackedBill.year ? `/${trackedBill.year}` : ""}`.trim() || `#${item.bill_id}`)
                              : `#${item.bill_id}`}
                          </span>
                        ) : (
                          <span className="text-sm font-medium">
                            {politician?.short_name ?? t("feed.lawmaker_fallback", { id: String(item.politician_id) })}
                          </span>
                        )}

                        {/* Event type badge */}
                        <Badge variant="secondary" className="text-xs">
                          {isBillVote
                            ? t("feed.event_bill_vote")
                            : isVote
                            ? t("feed.event_voted")
                            : t("feed.event_speech")}
                        </Badge>

                        {/* Vote value (for politician votes) */}
                        {item.detail && isVote && (
                          <span className="text-xs font-semibold text-foreground/70 uppercase tracking-wide">
                            {item.detail}
                          </span>
                        )}

                        {/* Result badge (for bill votes) */}
                        {isBillVote && <ResultBadge result={item.detail} />}

                        {/* Date */}
                        <span className="text-xs text-muted-foreground ml-auto">
                          {formatDate(item.occurred_at, dateLocale)}
                        </span>
                      </div>

                      {/* Title / description */}
                      {item.title && (
                        <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                          {item.title}
                        </p>
                      )}
                      {!item.title && !isVote && !isBillVote && item.detail && (
                        <p className="text-sm text-muted-foreground mt-1 line-clamp-2 italic">
                          {item.detail}
                        </p>
                      )}
                    </div>
                  </div>
                );

                // All vote-related events link to the votacao detail page
                const linkTarget =
                  isBillVote && item.votacao_id
                    ? `/votacao/${item.votacao_id}`
                    : isVote
                    ? `/votacao/${item.id}`
                    : null;

                return linkTarget ? (
                  <Link key={`${item.event_type}-${item.id}-${idx}`} href={linkTarget}>
                    {cardContent}
                  </Link>
                ) : (
                  <div key={`${item.event_type}-${item.id}-${idx}`}>
                    {cardContent}
                  </div>
                );
              })}
            </div>
          )}

          {/* Load more */}
          {hasMore && !loading && (
            <div className="mt-6 text-center">
              <button
                onClick={loadMore}
                className="text-sm text-primary hover:underline"
              >
                {t("feed.load_more")}
              </button>
            </div>
          )}
          {loading && items.length > 0 && (
            <p className="text-center text-sm text-muted-foreground mt-4">
              {t("shared.loading")}
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
