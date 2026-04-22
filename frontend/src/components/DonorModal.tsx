"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useLanguage } from "@/contexts/LanguageContext";

const API = process.env.NEXT_PUBLIC_API_URL;

function brl(n: number) {
  if (n >= 1e9) return `R$ ${(n / 1e9).toFixed(1)} bi`;
  if (n >= 1e6) return `R$ ${(n / 1e6).toFixed(1)} mi`;
  if (n >= 1e3) return `R$ ${(n / 1e3).toFixed(0)} mil`;
  return `R$ ${n.toFixed(0)}`;
}

function brlFull(n: number, lang: string) {
  const locale = lang === "en" ? "en-US" : "pt-BR";
  return "R$ " + Number(n).toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

type DonorSummary = {
  id: number;
  name: string;
  donor_type: string;
  cpf_cnpj_masked: string | null;
  donor_state: string | null;
  total_amount: number;
  recipient_count: number;
  election_count: number;
};

type DonationRow = {
  politician_id: number;
  politician_name: string;
  politician_state: string;
  politician_photo: string | null;
  party_acronym: string;
  election_year: number;
  amount_brl: number;
  receipt_date: string | null;
  source_type: string | null;
};

type DonorData = {
  donor: DonorSummary;
  donations: DonationRow[];
};

type Props = {
  donorId: number;
  donorName: string;
  onClose: () => void;
};

export function DonorModal({ donorId, donorName, onClose }: Props) {
  const { t, lang } = useLanguage();
  const [data, setData] = useState<DonorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    fetch(`${API}/donations/donor/${donorId}`)
      .then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, [donorId]);

  // Close on Escape
  const handleKey = useCallback(
    (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); },
    [onClose]
  );
  useEffect(() => {
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [handleKey]);

  // Prevent body scroll while open
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Panel */}
      <div className="relative w-full max-w-3xl max-h-[90vh] flex flex-col rounded-xl border bg-background shadow-xl">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 px-6 py-4 border-b">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold truncate">{donorName}</h2>
            {data && (
              <p className="text-sm text-muted-foreground mt-0.5">
                {data.donor.donor_type === "company"
                  ? t("donor.type_company")
                  : t("donor.type_individual")}
                {data.donor.cpf_cnpj_masked && (
                  <span className="ml-2 font-mono">{data.donor.cpf_cnpj_masked}</span>
                )}
                {data.donor.donor_state && (
                  <span className="ml-2">· {data.donor.donor_state}</span>
                )}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            aria-label={t("donor.close")}
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Summary strip */}
        {data && (
          <div className="flex flex-wrap gap-6 px-6 py-3 bg-muted/30 border-b text-sm">
            <div>
              <span className="text-muted-foreground">{t("donor.total_donated")}</span>
              <span className="ml-2 font-semibold tabular-nums">{brl(Number(data.donor.total_amount))}</span>
            </div>
            <div>
              <span className="text-muted-foreground">{t("donor.recipients")}</span>
              <span className="ml-2 font-semibold">{data.donor.recipient_count}</span>
            </div>
            <div>
              <span className="text-muted-foreground">{t("donor.elections")}</span>
              <span className="ml-2 font-semibold">{data.donor.election_count}</span>
            </div>
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading && (
            <div className="space-y-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="animate-pulse bg-muted rounded h-10" />
              ))}
            </div>
          )}
          {error && (
            <p className="text-center py-12 text-muted-foreground">
              {t("donor.error")}
            </p>
          )}
          {data && data.donations.length === 0 && (
            <p className="text-center py-12 text-muted-foreground">
              {t("donor.empty")}
            </p>
          )}
          {data && data.donations.length > 0 && (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-background border-b">
                <tr className="text-left text-xs text-muted-foreground">
                  <th className="pb-2 font-medium">{t("donor.col_candidate")}</th>
                  <th className="pb-2 font-medium hidden sm:table-cell">{t("donor.col_party_uf")}</th>
                  <th className="pb-2 font-medium">{t("donor.col_year")}</th>
                  <th className="pb-2 font-medium text-right">{t("donor.col_amount")}</th>
                  <th className="pb-2 font-medium hidden md:table-cell">{t("donor.col_source")}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.donations.map((row, i) => (
                  <tr key={i} className="hover:bg-muted/30 transition-colors">
                    <td className="py-2 pr-3">
                      <Link
                        href={`/politico/${row.politician_id}`}
                        className="flex items-center gap-2 hover:text-primary transition-colors"
                        onClick={onClose}
                      >
                        {row.politician_photo && (
                          <img
                            src={row.politician_photo}
                            alt={row.politician_name}
                            className="w-6 h-6 rounded-full object-cover shrink-0"
                          />
                        )}
                        <span className="font-medium line-clamp-1">{row.politician_name}</span>
                      </Link>
                    </td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground whitespace-nowrap hidden sm:table-cell">
                      {row.party_acronym}-{row.politician_state}
                    </td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground">{row.election_year}</td>
                    <td className="py-2 text-right font-mono text-xs font-medium tabular-nums whitespace-nowrap">
                      {brlFull(row.amount_brl, lang)}
                    </td>
                    <td className="py-2 pl-3 text-xs text-muted-foreground hidden md:table-cell">
                      <span className="line-clamp-1">{row.source_type ?? "—"}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t text-xs text-muted-foreground">
          {t("donor.footer_note")}
          {data && data.donations.length >= 500 && (
            <span className="ml-2 text-orange-600">{t("donor.cap_warning")}</span>
          )}
        </div>
      </div>
    </div>
  );
}
