"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLanguage } from "@/contexts/LanguageContext";

const API = process.env.NEXT_PUBLIC_API_URL;
const PAGE_SIZE = 50;

const SELECT_CLASS =
  "h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

const TYPES = ["PL", "PEC", "MPV", "PDL", "PLP", "REQ", "PRC", "MSC"];

type Bill = {
  id: number;
  type: string | null;
  number: number | null;
  year: number | null;
  title: string | null;
  ementa: string | null;
  short_title: string | null;
  status: string | null;
  policy_area: string | null;
  author_label: string | null;
};

function statusColor(status: string | null) {
  if (!status) return "secondary";
  const s = status.toLowerCase();
  if (s.includes("norma jurídica") || s.includes("sancionad")) return "default";
  if (s.includes("arquivad") || s.includes("prejudicad")) return "outline";
  return "secondary";
}

export default function ProposicoesPage() {
  const { t } = useLanguage();
  const [items, setItems] = useState<Bill[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [loading, setLoading] = useState(true);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    const params = new URLSearchParams({
      source: "camara",
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (debouncedSearch) params.set("search", debouncedSearch);
    if (typeFilter) params.set("type", typeFilter);

    setLoading(true);
    fetch(`${API}/bills/?${params}`)
      .then((r) => r.json())
      .then((data) => {
        setItems(data.items ?? []);
        setTotal(data.total ?? 0);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [page, debouncedSearch, typeFilter]);

  useEffect(() => { setPage(1); }, [debouncedSearch, typeFilter]);

  const hasFilters = search !== "" || typeFilter !== "";
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <main className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-1">{t("bills.title")}</h1>
        <p className="text-muted-foreground text-sm">
          {total.toLocaleString("pt-BR")} {t("bills.subtitle")}
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <Input
          type="search"
          placeholder={t("bills.search")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-72"
        />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className={SELECT_CLASS}
        >
          <option value="">{t("bills.all_types")}</option>
          {TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
        </select>
        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={() => { setSearch(""); setTypeFilter(""); }} className="text-muted-foreground">
            {t("bills.clear")}
          </Button>
        )}
      </div>

      {/* Table */}
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 15 }).map((_, i) => (
            <div key={i} className="animate-pulse bg-muted rounded-lg h-14" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">{t("bills.empty")}</div>
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-24">{t("bills.col_type")}</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">{t("bills.col_bill")}</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-48 hidden md:table-cell">{t("bills.col_author")}</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-40 hidden sm:table-cell">{t("bills.col_status")}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map((b) => (
                <tr key={b.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3">
                    {b.type && b.number && b.year ? (
                      <span className="font-mono text-xs text-muted-foreground">
                        {b.type} {b.number}/{b.year}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/proposicao/${b.id}`} className="hover:text-primary transition-colors">
                      <span className="font-medium line-clamp-2">
                        {b.short_title ?? b.ementa ?? b.title ?? t("bills.no_title")}
                      </span>
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs hidden md:table-cell">
                    <span className="line-clamp-1">{b.author_label ?? "—"}</span>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    {b.status ? (
                      <Badge variant={statusColor(b.status)} className="text-xs whitespace-nowrap">
                        {b.status}
                      </Badge>
                    ) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-4 mt-8">
          <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
            {t("shared.prev")}
          </Button>
          <span className="text-sm text-muted-foreground">
            {t("shared.page_of", { page, total: totalPages })}
          </span>
          <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
            {t("shared.next")}
          </Button>
        </div>
      )}
    </main>
  );
}
