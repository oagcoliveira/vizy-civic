"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { Badge } from "@/components/ui/badge";
import { useLanguage } from "@/contexts/LanguageContext";

const API = process.env.NEXT_PUBLIC_API_URL;

type SpeechDetail = {
  id: number;
  delivered_at: string | null;
  phase: string | null;
  summary: string | null;
  keywords: string[] | null;
  full_text_url: string | null;
  politician_id: number | null;
  politician_short_name: string | null;
  politician_full_name: string | null;
  politician_photo_url: string | null;
  party_acronym: string | null;
  state: string | null;
};

function formatDate(ts: string | null, locale: string) {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString(locale, {
    day: "2-digit", month: "long", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function DiscursoPage({ params }: { params: { id: string } }) {
  const { t, lang } = useLanguage();
  const [speech, setSpeech] = useState<SpeechDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const dateLocale = lang === "en" ? "en-GB" : "pt-BR";

  useEffect(() => {
    fetch(`${API}/speeches/${params.id}`)
      .then((r) => {
        if (r.status === 404) { setNotFound(true); setLoading(false); return null; }
        return r.json();
      })
      .then((data) => { if (data) { setSpeech(data); setLoading(false); } });
  }, [params.id]);

  if (loading) {
    return (
      <main className="max-w-3xl mx-auto px-4 py-10">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-muted rounded w-24" />
          <div className="h-7 bg-muted rounded w-3/4" />
          <div className="h-4 bg-muted rounded w-1/2" />
          <div className="h-32 bg-muted rounded" />
        </div>
      </main>
    );
  }

  if (notFound || !speech) {
    return (
      <main className="max-w-3xl mx-auto px-4 py-10">
        <p className="text-muted-foreground">{t("speech.not_found")}</p>
        <Link href="/" className="text-primary text-sm mt-2 block">{t("speech.back_home")}</Link>
      </main>
    );
  }

  return (
    <main className="max-w-3xl mx-auto px-4 py-10">
      {/* Back link */}
      {speech.politician_id && (
        <Link
          href={`/politico/${speech.politician_id}`}
          className="text-sm text-muted-foreground hover:text-primary mb-6 block"
        >
          ← {speech.politician_short_name ?? t("speech.lawmaker")}
        </Link>
      )}

      {/* Politician header */}
      {speech.politician_id && (
        <Link
          href={`/politico/${speech.politician_id}`}
          className="flex items-center gap-3 mb-6 group"
        >
          {speech.politician_photo_url && (
            <Image
              src={speech.politician_photo_url}
              alt={speech.politician_short_name ?? ""}
              width={48}
              height={48}
              className="rounded-full object-cover flex-shrink-0"
            />
          )}
          <div>
            <p className="font-semibold group-hover:text-primary transition-colors">
              {speech.politician_short_name}
            </p>
            <p className="text-sm text-muted-foreground">
              {[speech.party_acronym, speech.state].filter(Boolean).join(" · ")}
            </p>
          </div>
        </Link>
      )}

      {/* Meta */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {speech.phase && (
          <Badge variant="secondary">{speech.phase}</Badge>
        )}
        <span className="text-sm text-muted-foreground">{formatDate(speech.delivered_at, dateLocale)}</span>
      </div>

      <h1 className="text-2xl font-bold mb-6">{t("speech.title")}</h1>

      {/* Summary */}
      {speech.summary ? (
        <div className="prose prose-sm max-w-none mb-8">
          <p className="text-base leading-relaxed text-gray-800">{speech.summary}</p>
        </div>
      ) : (
        <p className="text-muted-foreground text-sm mb-8 italic">
          {t("speech.no_summary")}
        </p>
      )}

      {/* Keywords */}
      {speech.keywords && speech.keywords.length > 0 && (
        <div className="mb-8">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
            {t("speech.keywords")}
          </p>
          <div className="flex flex-wrap gap-2">
            {speech.keywords.map((k) => (
              <Badge key={k} variant="outline" className="text-xs">{k}</Badge>
            ))}
          </div>
        </div>
      )}

      {/* Full text link */}
      {speech.full_text_url && (
        <div className="border rounded-lg p-4 bg-muted/30">
          <p className="text-sm font-medium mb-1">{t("speech.full_text_title")}</p>
          <p className="text-xs text-muted-foreground mb-3">
            {t("speech.full_text_desc")}
          </p>
          <a
            href={speech.full_text_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-primary hover:underline font-medium"
          >
            {t("speech.full_text_link")}
          </a>
        </div>
      )}
    </main>
  );
}
