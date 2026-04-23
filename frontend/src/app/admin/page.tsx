"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const ADMIN_EMAIL = "oagcoliveira@gmail.com";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ADMIN_KEY = process.env.NEXT_PUBLIC_ADMIN_API_KEY ?? "";

type JobInfo = {
  id: string;
  name: string;
  next_run: string | null;
};

type ActionStatus = "idle" | "loading" | "success" | "error";

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
    timeZone: "America/Sao_Paulo",
  });
}

function ActionButton({
  label,
  description,
  status,
  result,
  onClick,
}: {
  label: string;
  description: string;
  status: ActionStatus;
  result: string | null;
  onClick: () => void;
}) {
  return (
    <div className="rounded-xl border bg-card p-6 flex flex-col gap-3">
      <div>
        <h2 className="text-lg font-semibold">{label}</h2>
        <p className="text-sm text-muted-foreground mt-1">{description}</p>
      </div>
      <Button
        onClick={onClick}
        disabled={status === "loading"}
        className="w-fit"
      >
        {status === "loading" ? "Iniciando..." : label}
      </Button>
      {status === "success" && result && (
        <p className="text-sm text-green-600 font-medium">{result}</p>
      )}
      {status === "error" && result && (
        <p className="text-sm text-destructive font-medium">{result}</p>
      )}
    </div>
  );
}

export default function AdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [jobs, setJobs] = useState<JobInfo[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);

  const [refreshStatus, setRefreshStatus] = useState<ActionStatus>("idle");
  const [refreshResult, setRefreshResult] = useState<string | null>(null);

  const [enrichStatus, setEnrichStatus] = useState<ActionStatus>("idle");
  const [enrichResult, setEnrichResult] = useState<string | null>(null);

  // Redirect non-admin users
  useEffect(() => {
    if (!loading && (!user || user.email !== ADMIN_EMAIL)) {
      router.replace("/");
    }
  }, [user, loading, router]);

  const fetchSchedule = useCallback(async () => {
    if (!ADMIN_KEY) return;
    setJobsLoading(true);
    try {
      const res = await fetch(`${API}/admin/schedule`, {
        headers: { "X-Admin-Key": ADMIN_KEY },
      });
      if (res.ok) {
        const data = await res.json();
        setJobs(data.jobs ?? []);
      }
    } catch {
      // silently ignore
    } finally {
      setJobsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user?.email === ADMIN_EMAIL) {
      fetchSchedule();
    }
  }, [user, fetchSchedule]);

  async function handleRefresh() {
    setRefreshStatus("loading");
    setRefreshResult(null);
    try {
      const res = await fetch(`${API}/admin/refresh`, {
        method: "POST",
        headers: { "X-Admin-Key": ADMIN_KEY },
      });
      const data = await res.json();
      if (res.ok) {
        setRefreshStatus("success");
        setRefreshResult(`Jobs iniciados: ${(data.jobs as string[]).join(", ")}`);
        setTimeout(fetchSchedule, 3000);
      } else {
        setRefreshStatus("error");
        setRefreshResult(data.detail ?? "Erro desconhecido");
      }
    } catch (e: unknown) {
      setRefreshStatus("error");
      setRefreshResult(e instanceof Error ? e.message : "Erro de rede");
    }
  }

  async function handleEnrich() {
    setEnrichStatus("loading");
    setEnrichResult(null);
    try {
      const res = await fetch(`${API}/admin/enrich`, {
        method: "POST",
        headers: { "X-Admin-Key": ADMIN_KEY },
      });
      const data = await res.json();
      if (res.ok) {
        setEnrichStatus("success");
        setEnrichResult(`Jobs iniciados: ${(data.jobs as string[]).join(", ")}`);
        setTimeout(fetchSchedule, 3000);
      } else {
        setEnrichStatus("error");
        setEnrichResult(data.detail ?? "Erro desconhecido");
      }
    } catch (e: unknown) {
      setEnrichStatus("error");
      setEnrichResult(e instanceof Error ? e.message : "Erro de rede");
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <p className="text-muted-foreground text-sm">Carregando...</p>
      </div>
    );
  }

  if (!user || user.email !== ADMIN_EMAIL) {
    return null;
  }

  return (
    <main className="max-w-3xl mx-auto px-4 py-10 space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Painel Admin</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Controles de ETL e enriquecimento de dados. Apenas para uso interno.
        </p>
      </div>

      {/* Action buttons */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <ActionButton
          label="Atualizar Dados"
          description="Executa todos os jobs de ingestão de dados (votos, proposições, discursos, tramitações). Não inclui enriquecimento com IA."
          status={refreshStatus}
          result={refreshResult}
          onClick={handleRefresh}
        />
        <ActionButton
          label="Enriquecimento IA"
          description="Executa os jobs de enriquecimento com IA (short_title/summary de proposições, discursos, eventos legislativos, perfis de deputados)."
          status={enrichStatus}
          result={enrichResult}
          onClick={handleEnrich}
        />
      </div>

      {/* Schedule table */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold">Próximas execuções agendadas</h2>
          <Button variant="ghost" size="sm" onClick={fetchSchedule} disabled={jobsLoading}>
            {jobsLoading ? "Atualizando..." : "Atualizar"}
          </Button>
        </div>
        {jobs.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {jobsLoading ? "Carregando agenda..." : "Nenhum job encontrado."}
          </p>
        ) : (
          <div className="rounded-xl border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Job</th>
                  <th className="text-left px-4 py-2 font-medium text-muted-foreground">Próxima execução (BRT)</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job, i) => (
                  <tr key={job.id} className={i % 2 === 0 ? "bg-background" : "bg-muted/20"}>
                    <td className="px-4 py-2 font-mono text-xs">{job.id}</td>
                    <td className="px-4 py-2">
                      {job.next_run ? (
                        <Badge variant="outline" className="text-xs font-normal">
                          {formatDate(job.next_run)}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
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
