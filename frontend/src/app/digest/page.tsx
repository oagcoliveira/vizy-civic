"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/contexts/LanguageContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";
import type { TranslationKey } from "@/lib/translations";

type DigestRecord = {
  id: string;
  label: string;
  status: "processing" | "completed" | "failed";
  parameters: Record<string, unknown>;
  estimated_cost_usd: number | null;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
};

function StatusBadge({ status, t }: { status: string; t: (k: TranslationKey) => string }) {
  if (status === "processing") return <Badge variant="secondary" className="text-xs">{t("digest.status_processing")}</Badge>;
  if (status === "completed") return <Badge variant="default" className="text-xs bg-green-600">{t("digest.status_completed")}</Badge>;
  return <Badge variant="outline" className="text-xs border-destructive text-destructive">{t("digest.status_failed")}</Badge>;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function DigestPage() {
  const { user, loading: authLoading } = useAuth();
  const { t } = useLanguage();
  const router = useRouter();

  const [digests, setDigests] = useState<DigestRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchDigests = useCallback(async () => {
    try {
      const res = await api.get("/digests");
      setDigests(res.data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && user) {
      fetchDigests();
      // Poll for processing digests
      const interval = setInterval(() => {
        fetchDigests();
      }, 8000);
      return () => clearInterval(interval);
    } else if (!authLoading) {
      setLoading(false);
    }
  }, [user, authLoading, fetchDigests]);

  async function handleDelete(id: string) {
    if (!confirm(t("digest.delete_confirm"))) return;
    setDeletingId(id);
    try {
      await api.delete(`/digests/${id}`);
      setDigests((prev) => prev.filter((d) => d.id !== id));
    } catch {
      // ignore
    } finally {
      setDeletingId(null);
    }
  }

  if (authLoading || loading) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-10">
        <div className="animate-pulse space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-20 bg-muted rounded-lg" />
          ))}
        </div>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-20 text-center">
        <h1 className="text-2xl font-bold mb-2">{t("digest.page_title")}</h1>
        <p className="text-muted-foreground mb-6">{t("digest.page_subtitle")}</p>
        <p className="text-muted-foreground mb-4">{t("digest.login_prompt")}</p>
        <Link
          href="/login"
          className="inline-block bg-primary text-primary-foreground px-6 py-2 rounded-md hover:bg-primary/90 transition-colors text-sm font-medium"
        >
          {t("digest.login_cta")}
        </Link>
      </main>
    );
  }

  if (showForm) {
    return (
      <DigestForm
        onCancel={() => setShowForm(false)}
        onCreated={(d) => {
          setDigests((prev) => [d, ...prev]);
          setShowForm(false);
        }}
        t={t}
      />
    );
  }

  return (
    <main className="max-w-4xl mx-auto px-4 py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">{t("digest.page_title")}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t("digest.page_subtitle")}</p>
        </div>
        <Button onClick={() => setShowForm(true)}>{t("digest.new_button")}</Button>
      </div>

      {digests.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-muted-foreground mb-4">{t("digest.history_empty")}</p>
          <button
            onClick={() => setShowForm(true)}
            className="text-primary hover:underline text-sm"
          >
            {t("digest.history_empty_cta")} →
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {digests.map((d) => (
            <div
              key={d.id}
              className="border rounded-lg p-4 flex items-center justify-between gap-4 hover:border-primary/30 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm truncate">{d.label}</span>
                  <StatusBadge status={d.status} t={t} />
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                  <span>{t("digest.created_at")}: {formatDate(d.created_at)}</span>
                  {d.estimated_cost_usd != null && (
                    <span>{t("digest.estimated_cost")}: ${d.estimated_cost_usd.toFixed(4)}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {d.status === "completed" && (
                  <Link
                    href={`/digest/${d.id}`}
                    className="text-xs text-primary hover:underline font-medium"
                  >
                    {t("digest.view")}
                  </Link>
                )}
                <button
                  onClick={() => handleDelete(d.id)}
                  disabled={deletingId === d.id}
                  className="text-xs text-muted-foreground hover:text-destructive transition-colors"
                >
                  {t("digest.delete")}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}

// ---------------------------------------------------------------------------
// Digest Creation Form (inline component)
// ---------------------------------------------------------------------------

type EstimateResult = {
  estimated_cost_usd: number;
  total_tokens: number;
  blocked: boolean;
  inactive_deputies: { id: number; name: string }[];
  inactive_bills: { id: number; label: string }[];
  active_deputies: { id: number; name: string; tokens: number }[];
  active_bills: { id: number; label: string; tokens: number }[];
  cost_limit_usd: number;
  model_label: string;
};

type SearchDeputy = { id: number; short_name: string; party: string; state: string; photo_url: string | null };
type SearchBill = { id: number; type: string; number: number; year: number; ementa: string; title: string };

function DigestForm({
  onCancel,
  onCreated,
  t,
}: {
  onCancel: () => void;
  onCreated: (d: DigestRecord) => void;
  t: (k: TranslationKey) => string;
}) {
  const [deputySearch, setDeputySearch] = useState("");
  const [deputyResults, setDeputyResults] = useState<SearchDeputy[]>([]);
  const [selectedDeputies, setSelectedDeputies] = useState<SearchDeputy[]>([]);
  const [deputyLoading, setDeputyLoading] = useState(false);

  const [billSearch, setBillSearch] = useState("");
  const [billResults, setBillResults] = useState<SearchBill[]>([]);
  const [selectedBills, setSelectedBills] = useState<SearchBill[]>([]);
  const [billLoading, setBillLoading] = useState(false);

  const [dateRange, setDateRange] = useState("last_7");
  const [language, setLanguage] = useState("pt");
  const [enrichment, setEnrichment] = useState(false);
  const [model, setModel] = useState("haiku");

  const [estimate, setEstimate] = useState<EstimateResult | null>(null);
  const [estimating, setEstimating] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalSelected = selectedDeputies.length + selectedBills.length;
  const atLimit = totalSelected >= 10;

  // Deputy search
  useEffect(() => {
    if (!deputySearch.trim() || deputySearch.length < 2) {
      setDeputyResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setDeputyLoading(true);
      try {
        const res = await api.get("/politicians/", {
          params: { source: "camara", search: deputySearch, page_size: 8, page: 1 },
        });
        setDeputyResults(res.data.items || []);
      } catch {
        setDeputyResults([]);
      } finally {
        setDeputyLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [deputySearch]);

  // Bill search
  useEffect(() => {
    if (!billSearch.trim() || billSearch.length < 2) {
      setBillResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setBillLoading(true);
      try {
        const res = await api.get("/bills/", {
          params: { search: billSearch, page_size: 8, page: 1 },
        });
        setBillResults(res.data.items || []);
      } catch {
        setBillResults([]);
      } finally {
        setBillLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [billSearch]);

  function addDeputy(dep: SearchDeputy) {
    if (atLimit) return;
    if (selectedDeputies.find((d) => d.id === dep.id)) return;
    setSelectedDeputies((prev) => [...prev, dep]);
    setDeputySearch("");
    setDeputyResults([]);
    setEstimate(null);
  }

  function removeDeputy(id: number) {
    setSelectedDeputies((prev) => prev.filter((d) => d.id !== id));
    setEstimate(null);
  }

  function addBill(bill: SearchBill) {
    if (atLimit) return;
    if (selectedBills.find((b) => b.id === bill.id)) return;
    setSelectedBills((prev) => [...prev, bill]);
    setBillSearch("");
    setBillResults([]);
    setEstimate(null);
  }

  function removeBill(id: number) {
    setSelectedBills((prev) => prev.filter((b) => b.id !== id));
    setEstimate(null);
  }

  async function handleEstimate() {
    setEstimating(true);
    setError(null);
    try {
      const res = await api.post("/digests/estimate", {
        deputy_ids: selectedDeputies.map((d) => d.id),
        bill_ids: selectedBills.map((b) => b.id),
        date_range: dateRange,
        enrichment,
        model,
      });
      setEstimate(res.data);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail ?? "Erro ao calcular estimativa.");
    } finally {
      setEstimating(false);
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const res = await api.post("/digests", {
        deputy_ids: selectedDeputies.map((d) => d.id),
        bill_ids: selectedBills.map((b) => b.id),
        date_range: dateRange,
        language,
        enrichment,
        model,
      });
      onCreated(res.data);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail ?? "Erro ao gerar Digest.");
    } finally {
      setGenerating(false);
    }
  }

  const SELECT_CLASS =
    "w-full border rounded-md px-3 py-2 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary/30";

  const dateOptions = [
    { value: "yesterday", label: t("digest.date_yesterday") },
    { value: "last_7", label: t("digest.date_last7") },
    { value: "last_15", label: t("digest.date_last15") },
    { value: "last_30", label: t("digest.date_last30") },
    { value: "last_60", label: t("digest.date_last60") },
  ];

  return (
    <main className="max-w-2xl mx-auto px-4 py-10">
      <button
        onClick={onCancel}
        className="text-sm text-muted-foreground hover:text-foreground mb-6 block"
      >
        ← {t("digest.report_back")}
      </button>

      <h1 className="text-2xl font-bold mb-6">{t("digest.form_title")}</h1>

      <div className="space-y-6">
        {/* Deputies */}
        <div>
          <label className="block text-sm font-medium mb-1">
            {t("digest.form_deputies")}
            {totalSelected > 0 && (
              <span className="ml-2 text-xs text-muted-foreground">
                ({totalSelected}/10)
              </span>
            )}
          </label>
          <p className="text-xs text-muted-foreground mb-2">{t("digest.form_deputies_hint")}</p>
          {/* Selected deputies */}
          {selectedDeputies.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {selectedDeputies.map((d) => (
                <span
                  key={d.id}
                  className="inline-flex items-center gap-1 bg-primary/10 text-primary text-xs px-2 py-1 rounded-full"
                >
                  {d.short_name} ({d.party}-{d.state})
                  <button onClick={() => removeDeputy(d.id)} className="hover:text-destructive ml-1">×</button>
                </span>
              ))}
            </div>
          )}
          {/* Search input */}
          {!atLimit && (
            <div className="relative">
              <input
                type="text"
                value={deputySearch}
                onChange={(e) => setDeputySearch(e.target.value)}
                placeholder={t("digest.form_deputies_hint")}
                className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
              {deputyLoading && (
                <span className="absolute right-3 top-2.5 text-xs text-muted-foreground">...</span>
              )}
              {deputyResults.length > 0 && (
                <div className="absolute z-20 w-full bg-white border rounded-md shadow-lg mt-1 max-h-52 overflow-y-auto">
                  {deputyResults.map((dep) => (
                    <button
                      key={dep.id}
                      onClick={() => addDeputy(dep)}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-muted flex items-center gap-2"
                    >
                      {dep.photo_url && (
                        <img src={dep.photo_url} alt="" className="w-6 h-6 rounded-full object-cover flex-shrink-0" />
                      )}
                      <span>{dep.short_name}</span>
                      <span className="text-xs text-muted-foreground ml-auto">{dep.party}-{dep.state}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          {atLimit && (
            <p className="text-xs text-amber-600 mt-1">{t("digest.form_limit")}</p>
          )}
        </div>

        {/* Bills */}
        <div>
          <label className="block text-sm font-medium mb-1">{t("digest.form_bills")}</label>
          <p className="text-xs text-muted-foreground mb-2">{t("digest.form_bills_hint")}</p>
          {/* Selected bills */}
          {selectedBills.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {selectedBills.map((b) => (
                <span
                  key={b.id}
                  className="inline-flex items-center gap-1 bg-primary/10 text-primary text-xs px-2 py-1 rounded-full"
                >
                  {b.type} {b.number}/{b.year}
                  <button onClick={() => removeBill(b.id)} className="hover:text-destructive ml-1">×</button>
                </span>
              ))}
            </div>
          )}
          {/* Search input */}
          {!atLimit && (
            <div className="relative">
              <input
                type="text"
                value={billSearch}
                onChange={(e) => setBillSearch(e.target.value)}
                placeholder={t("digest.form_bills_hint")}
                className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
              {billLoading && (
                <span className="absolute right-3 top-2.5 text-xs text-muted-foreground">...</span>
              )}
              {billResults.length > 0 && (
                <div className="absolute z-20 w-full bg-white border rounded-md shadow-lg mt-1 max-h-64 overflow-y-auto">
                  {billResults.map((bill) => (
                    <button
                      key={bill.id}
                      onClick={() => addBill(bill)}
                      className="w-full text-left px-3 py-2 text-sm hover:bg-muted"
                    >
                      <div className="font-medium">{bill.type} {bill.number}/{bill.year}</div>
                      <div className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                        {bill.ementa || bill.title}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Date range */}
        <div>
          <label className="block text-sm font-medium mb-1">{t("digest.form_date_range")}</label>
          <select value={dateRange} onChange={(e) => { setDateRange(e.target.value); setEstimate(null); }} className={SELECT_CLASS}>
            {dateOptions.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {/* Language */}
        <div>
          <label className="block text-sm font-medium mb-1">{t("digest.form_language")}</label>
          <select value={language} onChange={(e) => setLanguage(e.target.value)} className={SELECT_CLASS}>
            <option value="pt">{t("digest.form_language_pt")}</option>
            <option value="en">{t("digest.form_language_en")}</option>
          </select>
        </div>

        {/* Model */}
        <div>
          <label className="block text-sm font-medium mb-1">{t("digest.form_model")}</label>
          <select value={model} onChange={(e) => { setModel(e.target.value); setEstimate(null); }} className={SELECT_CLASS}>
            <option value="haiku">Claude Haiku (rápido, econômico)</option>
            <option value="sonnet">Claude Sonnet (mais capaz)</option>
          </select>
        </div>

        {/* Enrichment toggle */}
        <div className="flex items-start gap-3">
          <input
            id="enrichment"
            type="checkbox"
            checked={enrichment}
            onChange={(e) => { setEnrichment(e.target.checked); setEstimate(null); }}
            className="mt-0.5"
          />
          <div>
            <label htmlFor="enrichment" className="text-sm font-medium cursor-pointer">
              {t("digest.form_enrichment")}
            </label>
            <p className="text-xs text-muted-foreground mt-0.5">{t("digest.form_enrichment_hint")}</p>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="text-sm text-destructive bg-destructive/10 rounded-md px-3 py-2">
            {error}
          </div>
        )}

        {/* Estimate result */}
        {estimate && (
          <div className={`rounded-md border px-4 py-3 text-sm ${estimate.blocked ? "border-destructive/40 bg-destructive/5" : "border-green-300 bg-green-50"}`}>
            <p className="font-medium mb-1">{t("digest.estimate_title")}</p>
            <p className="text-muted-foreground text-xs">
              {estimate.total_tokens.toLocaleString()} {t("digest.estimate_tokens")} ·{" "}
              <span className={estimate.blocked ? "text-destructive font-semibold" : "font-semibold"}>
                {t("digest.estimate_cost")}: ${estimate.estimated_cost_usd.toFixed(4)}
              </span>
            </p>
            {estimate.blocked && (
              <p className="text-destructive text-xs mt-1">{t("digest.estimate_blocked")}</p>
            )}
            {estimate.inactive_deputies.length > 0 || estimate.inactive_bills.length > 0 ? (
              <p className="text-xs text-amber-700 mt-1">
                {t("digest.estimate_inactive")}{" "}
                {[...estimate.inactive_deputies.map((d) => d.name), ...estimate.inactive_bills.map((b) => b.label)].join(", ")}
              </p>
            ) : null}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <Button
            variant="outline"
            onClick={handleEstimate}
            disabled={estimating || totalSelected === 0}
          >
            {estimating ? t("shared.loading") : t("digest.form_estimate_btn")}
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={generating || totalSelected === 0 || (estimate?.blocked ?? false)}
          >
            {generating ? t("digest.form_generating") : t("digest.form_generate_btn")}
          </Button>
          <Button variant="ghost" onClick={onCancel}>
            Cancelar
          </Button>
        </div>
      </div>
    </main>
  );
}
