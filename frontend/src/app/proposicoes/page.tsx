"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLanguage } from "@/contexts/LanguageContext";

const API = process.env.NEXT_PUBLIC_API_URL;
const PAGE_SIZE = 50;

// All bill types shown in the filter, with human-readable labels
const BILL_TYPES: { value: string; label: string }[] = [
  { value: "PL",  label: "PL — Projeto de Lei" },
  { value: "PEC", label: "PEC — Proposta de Emenda Constitucional" },
  { value: "MPV", label: "MPV — Medida Provisória" },
  { value: "PDL", label: "PDL — Projeto de Decreto Legislativo" },
  { value: "PLP", label: "PLP — Projeto de Lei Complementar" },
  { value: "PRC", label: "PRC — Projeto de Resolução" },
  { value: "MSC", label: "MSC — Mensagem" },
  { value: "REQ", label: "REQ — Requerimento" },
];

// Types selected by default (REQ and MSC are intentionally excluded)
const DEFAULT_SELECTED = new Set(
  BILL_TYPES.map((t) => t.value).filter((v) => v !== "REQ" && v !== "MSC")
);

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
  presented_at: string | null;
};

function statusColor(status: string | null) {
  if (!status) return "secondary";
  const s = status.toLowerCase();
  if (s.includes("norma jurídica") || s.includes("sancionad")) return "default";
  if (s.includes("arquivad") || s.includes("prejudicad")) return "outline";
  return "secondary";
}

// ── Multi-select dropdown component ──────────────────────────────────────────

type MultiSelectProps = {
  options: { value: string; label: string }[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
  placeholder: string;
};

function MultiSelect({ options, selected, onChange, placeholder }: MultiSelectProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  const allSelected = selected.size === options.length;
  const noneSelected = selected.size === 0;

  const toggle = (value: string) => {
    const next = new Set(selected);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    onChange(next);
  };

  const toggleAll = () => {
    if (allSelected) onChange(new Set());
    else onChange(new Set(options.map((o) => o.value)));
  };

  // Summary label shown on the button
  const summary =
    noneSelected
      ? placeholder
      : allSelected
      ? placeholder
      : selected.size === 1
      ? [...selected][0]
      : `${selected.size} tipos`;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="h-9 min-w-[160px] rounded-md border border-input bg-background px-3 text-sm shadow-sm text-left flex items-center justify-between gap-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        <span className="truncate text-muted-foreground">{summary}</span>
        <svg className="h-4 w-4 shrink-0 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-72 rounded-md border bg-popover shadow-md text-sm">
          {/* Select all / none */}
          <div className="border-b px-3 py-2 flex items-center gap-2 cursor-pointer hover:bg-muted/50" onClick={toggleAll}>
            <input
              type="checkbox"
              readOnly
              checked={allSelected}
              ref={(el) => { if (el) el.indeterminate = !allSelected && !noneSelected; }}
              className="h-4 w-4 rounded border-input accent-primary"
            />
            <span className="font-medium">{allSelected ? "Desmarcar todos" : "Selecionar todos"}</span>
          </div>
          {/* Individual options */}
          <div className="max-h-64 overflow-y-auto py-1">
            {options.map((opt) => (
              <div
                key={opt.value}
                className="flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-muted/50"
                onClick={() => toggle(opt.value)}
              >
                <input
                  type="checkbox"
                  readOnly
                  checked={selected.has(opt.value)}
                  className="h-4 w-4 rounded border-input accent-primary"
                />
                <span>{opt.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ProposicoesPage() {
  const { t } = useLanguage();
  const [items, setItems] = useState<Bill[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(DEFAULT_SELECTED);
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
    // Pass selected types as comma-separated; if all selected, omit for efficiency
    if (selectedTypes.size > 0 && selectedTypes.size < BILL_TYPES.length) {
      params.set("types", [...selectedTypes].join(","));
    }

    setLoading(true);
    fetch(`${API}/bills/?${params}`)
      .then((r) => r.json())
      .then((data) => {
        setItems(data.items ?? []);
        setTotal(data.total ?? 0);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [page, debouncedSearch, selectedTypes]);

  useEffect(() => { setPage(1); }, [debouncedSearch, selectedTypes]);

  const isDefaultFilter =
    search === "" &&
    selectedTypes.size === DEFAULT_SELECTED.size &&
    [...selectedTypes].every((v) => DEFAULT_SELECTED.has(v));

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const handleClear = () => {
    setSearch("");
    setSelectedTypes(DEFAULT_SELECTED);
  };

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
        <MultiSelect
          options={BILL_TYPES}
          selected={selectedTypes}
          onChange={(next) => setSelectedTypes(next)}
          placeholder={t("bills.all_types")}
        />
        {!isDefaultFilter && (
          <Button variant="ghost" size="sm" onClick={handleClear} className="text-muted-foreground">
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
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-28">{t("bills.col_type")}</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">{t("bills.col_bill")}</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-48 hidden md:table-cell">{t("bills.col_author")}</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-24 hidden sm:table-cell">{t("bills.col_date")}</th>
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
                  <td className="px-4 py-3 text-muted-foreground text-xs hidden sm:table-cell whitespace-nowrap">
                    {b.presented_at
                      ? new Date(b.presented_at).toLocaleDateString("pt-BR", {
                          day: "2-digit",
                          month: "2-digit",
                          year: "numeric",
                        })
                      : "—"}
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell">
                    {b.status ? (
                      <Badge variant={statusColor(b.status)} className="text-xs whitespace-nowrap">
                        {b.status}
                      </Badge>
                    ) : (
                      "—"
                    )}
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
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            {t("shared.prev")}
          </Button>
          <span className="text-sm text-muted-foreground">
            {t("shared.page_of", { page, total: totalPages })}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            {t("shared.next")}
          </Button>
        </div>
      )}
    </main>
  );
}
