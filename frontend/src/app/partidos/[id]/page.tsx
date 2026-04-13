"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useLanguage } from "@/contexts/LanguageContext";

const API = process.env.NEXT_PUBLIC_API_URL;

type Member = {
  id: number;
  short_name: string;
  name: string;
  state: string;
  photo_url: string | null;
  current_office: string;
};

type Party = {
  id: number;
  acronym: string;
  name: string;
  ideology: string | null;
  website_url: string | null;
  description: string | null;
  members: Member[];
};

export default function PartyPage() {
  const { id } = useParams();
  const { t } = useLanguage();
  const [party, setParty] = useState<Party | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    fetch(`${API}/parties/${id}`)
      .then((r) => r.json())
      .then((data) => { setParty(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      <div className="animate-pulse space-y-4">
        <div className="h-8 bg-muted rounded w-48" />
        <div className="h-4 bg-muted rounded w-72" />
        <div className="h-64 bg-muted rounded" />
      </div>
    </main>
  );

  if (!party) return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      <p className="text-muted-foreground">{t("party.not_found")}</p>
    </main>
  );

  return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-baseline gap-3 mb-1">
          <h1 className="text-3xl font-bold">{party.acronym}</h1>
          <span className="text-lg text-muted-foreground">{party.name}</span>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground mt-2">
          {party.ideology && <span>{party.ideology}</span>}
          {party.website_url && (
            <a href={party.website_url} target="_blank" rel="noopener noreferrer"
               className="hover:text-foreground transition-colors underline underline-offset-2">
              {t("party.official_site")}
            </a>
          )}
        </div>
        {party.description && (
          <p className="mt-4 text-sm leading-relaxed">{party.description}</p>
        )}
      </div>

      {/* Members */}
      <div>
        <h2 className="text-lg font-semibold mb-4">
          {t("party.deputies_title")} ({party.members.length})
        </h2>
        {party.members.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t("party.empty")}</p>
        ) : (
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">{t("party.col_name")}</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground w-16">{t("party.col_state")}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {party.members.map((m) => (
                  <tr key={m.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-2">
                      <Link href={`/politico/${m.id}`}
                            className="flex items-center gap-3 hover:text-primary transition-colors">
                        {m.photo_url && (
                          <img src={m.photo_url} alt={m.short_name}
                               className="w-7 h-7 rounded-full object-cover shrink-0" />
                        )}
                        <span>{m.short_name || m.name}</span>
                      </Link>
                    </td>
                    <td className="px-4 py-2 text-muted-foreground">{m.state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
