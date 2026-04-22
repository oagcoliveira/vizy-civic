"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { useLanguage } from "@/contexts/LanguageContext";

const API = process.env.NEXT_PUBLIC_API_URL;

type Party = {
  id: number;
  acronym: string;
  name: string;
  ideology: string | null;
  deputy_count: number;
};

// Colour palette (cycles for parties beyond this list)
const COLORS = [
  "#4f46e5","#0ea5e9","#22c55e","#f59e0b","#ef4444",
  "#8b5cf6","#ec4899","#14b8a6","#f97316","#64748b",
  "#a3e635","#fb7185","#38bdf8","#34d399","#fbbf24",
  "#e879f9","#2dd4bf","#facc15","#60a5fa","#f87171",
];

function renderCustomLabel({
  cx, cy, midAngle, innerRadius, outerRadius, percent,
}: {
  cx: number; cy: number; midAngle: number;
  innerRadius: number; outerRadius: number; percent: number;
}) {
  if (percent < 0.04) return null;
  const RADIAN = Math.PI / 180;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.6;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={600}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
}

export default function PartidosPage() {
  const { t } = useLanguage();
  const [parties, setParties] = useState<Party[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/parties/`)
      .then((r) => r.json())
      .then((data) => { setParties(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  // Only include parties with at least 1 deputy in the chart
  const chartData = parties
    .filter((p) => p.deputy_count > 0)
    .sort((a, b) => b.deputy_count - a.deputy_count);

  return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold mb-1">{t("parties.title")}</h1>
        <p className="text-muted-foreground text-sm">
          {parties.length} {t("parties.subtitle")}
        </p>
      </div>

      {/* Pie chart */}
      {!loading && chartData.length > 0 && (
        <div className="mb-8 rounded-lg border p-4">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
            {t("parties.chart_title")}
          </h2>
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={chartData}
                dataKey="deputy_count"
                nameKey="acronym"
                cx="50%"
                cy="50%"
                outerRadius={130}
                labelLine={false}
                label={renderCustomLabel}
              >
                {chartData.map((entry, index) => (
                  <Cell key={entry.id} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value, name) => [`${value} deputados`, name]}
              />
              <Legend
                formatter={(value) => (
                  <span className="text-xs">{value}</span>
                )}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="animate-pulse bg-muted rounded-lg h-12" />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground w-24">{t("parties.col_acronym")}</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">{t("parties.col_name")}</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground w-32">{t("parties.col_deputies")}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {parties.map((p) => (
                <tr key={p.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3">
                    <Link href={`/partidos/${p.id}`} className="font-bold hover:text-primary transition-colors">
                      {p.acronym}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    <Link href={`/partidos/${p.id}`} className="hover:text-foreground transition-colors">
                      {p.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground">
                    {p.deputy_count > 0 ? p.deputy_count : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
