"use client";

import { useState } from "react";

export default function BuscaPage() {
  const [query, setQuery] = useState("");

  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <h1 className="text-3xl font-bold mb-6">Busca</h1>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Busque por parlamentar, projeto de lei ou discurso..."
        className="w-full border rounded-lg px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-brand-500"
      />
      {query.length >= 2 && (
        <p className="text-gray-400 mt-4 text-sm">Buscando por "{query}"...</p>
      )}
    </main>
  );
}
