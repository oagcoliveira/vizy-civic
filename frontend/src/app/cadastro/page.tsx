"use client";

import { useState } from "react";
import Link from "next/link";

export default function CadastroPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="bg-white p-8 rounded-xl shadow-sm w-full max-w-sm">
        <h1 className="text-2xl font-bold mb-6 text-center">Criar conta no Vizy</h1>
        <form className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Nome</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">E-mail</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Senha</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
              required
              minLength={8}
            />
          </div>
          <button
            type="submit"
            className="w-full bg-brand-700 text-white py-2 rounded-lg font-semibold hover:bg-brand-900 transition"
          >
            Criar conta
          </button>
        </form>
        <p className="text-center text-sm text-gray-500 mt-4">
          Já tem conta?{" "}
          <Link href="/login" className="text-brand-700 font-medium">
            Entrar
          </Link>
        </p>
      </div>
    </main>
  );
}
