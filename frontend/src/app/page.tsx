"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL;

type Stats = { politicians: number; votes: number; speeches: number };

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/politicians/?source=camara&page_size=1`).then((r) => r.json()),
      fetch(`${API}/votes/`).then((r) => r.json()).catch(() => null),
      fetch(`${API}/speeches/`).then((r) => r.json()).catch(() => null),
    ]).then(([pols, votes, speeches]) => {
      setStats({
        politicians: pols?.total ?? 513,
        votes: votes?.total ?? 0,
        speeches: speeches?.total ?? 0,
      });
    });
  }, []);

  return (
    <main className="min-h-screen">
      {/* Hero */}
      <section className="bg-primary text-primary-foreground py-24 px-6 text-center">
        <h1 className="text-5xl font-bold mb-4">Vizy</h1>
        <p className="text-xl opacity-90 max-w-xl mx-auto mb-8">
          Acompanhe votações, discursos e financiamentos dos seus deputados
          — de forma simples e transparente.
        </p>
        <div className="flex gap-4 justify-center flex-wrap">
          <Link
            href="/deputados"
            className="bg-white text-primary font-semibold px-6 py-3 rounded-lg hover:bg-primary-foreground/90 transition"
          >
            Ver deputados
          </Link>
          <Link
            href="/cadastro"
            className="border border-white/60 text-white font-semibold px-6 py-3 rounded-lg hover:bg-white/10 transition"
          >
            Criar conta
          </Link>
        </div>
      </section>

      {/* Live stats bar */}
      {stats && (
        <section className="border-b bg-muted/50">
          <div className="max-w-5xl mx-auto px-6 py-5 grid grid-cols-3 divide-x text-center">
            <div className="px-4">
              <p className="text-2xl font-bold text-foreground">{stats.politicians.toLocaleString("pt-BR")}</p>
              <p className="text-xs text-muted-foreground mt-0.5">deputados em exercício</p>
            </div>
            <div className="px-4">
              <p className="text-2xl font-bold text-foreground">{stats.votes.toLocaleString("pt-BR")}</p>
              <p className="text-xs text-muted-foreground mt-0.5">votações nominais registradas</p>
            </div>
            <div className="px-4">
              <p className="text-2xl font-bold text-foreground">{stats.speeches.toLocaleString("pt-BR")}</p>
              <p className="text-xs text-muted-foreground mt-0.5">discursos indexados</p>
            </div>
          </div>
        </section>
      )}

      {/* Features */}
      <section className="py-20 px-6 max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
        {[
          {
            title: "Votações nominais",
            body: "Saiba como cada parlamentar votou em todas as votações nominais da Câmara, com orientação do partido e histórico completo.",
          },
          {
            title: "Resumos por IA",
            body: "Projetos de lei e discursos resumidos em linguagem simples, sem juridiquês, graças ao Claude da Anthropic.",
          },
          {
            title: "Financiamento eleitoral",
            body: "Veja quem financiou a campanha do seu representante nas eleições de 2018 e 2022 com dados do TSE.",
          },
        ].map((f) => (
          <div key={f.title} className="p-6 border rounded-xl hover:shadow-sm transition-shadow">
            <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
            <p className="text-muted-foreground text-sm">{f.body}</p>
          </div>
        ))}
      </section>

      {/* CTA */}
      <section className="py-16 px-6 text-center border-t bg-muted/30">
        <h2 className="text-2xl font-bold mb-3">Comece a acompanhar agora</h2>
        <p className="text-muted-foreground mb-6 max-w-md mx-auto text-sm">
          Crie uma conta gratuita e receba um resumo semanal das atividades dos parlamentares que você escolher acompanhar.
        </p>
        <Link
          href="/cadastro"
          className="inline-block bg-primary text-primary-foreground font-semibold px-8 py-3 rounded-lg hover:bg-primary/90 transition"
        >
          Criar conta grátis
        </Link>
      </section>
    </main>
  );
}
