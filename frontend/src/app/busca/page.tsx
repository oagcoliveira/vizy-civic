"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import Image from "next/image";
import { useLanguage } from "@/contexts/LanguageContext";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Politician = {
  id: number;
  short_name: string;
  full_name: string;
  party_acronym: string | null;
  state: string | null;
  photo_url: string | null;
};

type Bill = {
  id: number;
  type: string | null;
  number: number | null;
  year: number | null;
  short_title: string | null;
  ementa: string | null;
};

type Speech = {
  id: number;
  politician_id: number;
  politician_name: string | null;
  summary: string | null;
  delivered_at: string | null;
};

type SearchResults = {
  politicians: Politician[];
  bills: Bill[];
  speeches: Speech[];
};

export default function BuscaPage() {
  const { t, lang } = useLanguage();
  const dateLocale = lang === "en" ? "en-GB" : "pt-BR";
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResults | null>(null);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (query.length < 2) {
      setResults(null);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API}/search?q=${encodeURIComponent(query)}`);
        if (r.ok) setResults(await r.json());
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query]);

  const total = results
    ? results.politicians.length + results.bills.length + results.speeches.length
    : 0;

  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <h1 className="text-3xl font-bold mb-6">{t("search.title")}</h1>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t("search.placeholder")}
        className="w-full border rounded-lg px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-blue-500"
        autoFocus
      />

      {loading && (
        <div className="mt-6 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {!loading && results && total === 0 && (
        <p className="mt-8 text-gray-500 text-sm">{t("search.no_results", { query })}</p>
      )}

      {!loading && results && total > 0 && (
        <div className="mt-6 space-y-8">

          {results.politicians.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                {t("search.section_politicians")}
              </h2>
              <ul className="space-y-2">
                {results.politicians.map((p) => (
                  <li key={p.id}>
                    <Link
                      href={`/politico/${p.id}`}
                      className="flex items-center gap-3 p-3 rounded-lg border hover:bg-gray-50 transition"
                    >
                      {p.photo_url && (
                        <Image
                          src={p.photo_url}
                          alt={p.short_name}
                          width={40}
                          height={40}
                          className="rounded-full object-cover flex-shrink-0"
                        />
                      )}
                      <div>
                        <p className="font-medium">{p.short_name}</p>
                        <p className="text-sm text-gray-500">
                          {[p.party_acronym, p.state].filter(Boolean).join(" · ")}
                        </p>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {results.bills.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                {t("search.section_bills")}
              </h2>
              <ul className="space-y-2">
                {results.bills.map((b) => (
                  <li key={b.id}>
                    <Link
                      href={`/proposicao/${b.id}`}
                      className="flex items-start gap-3 p-3 rounded-lg border hover:bg-gray-50 transition"
                    >
                      {b.type && b.number && b.year && (
                        <span className="mt-0.5 flex-shrink-0 text-xs font-mono bg-gray-100 text-gray-600 px-2 py-1 rounded">
                          {b.type} {b.number}/{b.year}
                        </span>
                      )}
                      <p className="text-sm">
                        {b.short_title || b.ementa || "—"}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {results.speeches.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
                {t("search.section_speeches")}
              </h2>
              <ul className="space-y-2">
                {results.speeches.map((s) => (
                  <li key={s.id}>
                    <div className="p-3 rounded-lg border">
                      <div className="flex items-center justify-between mb-1">
                        {s.politician_id ? (
                          <Link
                            href={`/politico/${s.politician_id}`}
                            className="text-sm font-medium hover:underline"
                          >
                            {s.politician_name ?? t("speech.lawmaker")}
                          </Link>
                        ) : (
                          <span className="text-sm font-medium">{s.politician_name ?? t("speech.lawmaker")}</span>
                        )}
                        {s.delivered_at && (
                          <span className="text-xs text-gray-400">
                            {new Date(s.delivered_at).toLocaleDateString(dateLocale)}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 line-clamp-2">{s.summary ?? "—"}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <p className="text-xs text-gray-400 pt-2 border-t">{t("search.coverage_note")}</p>
        </div>
      )}
    </main>
  );
}
