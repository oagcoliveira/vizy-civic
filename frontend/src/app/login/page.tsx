"use client";

import { useState } from "react";
import Link from "next/link";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="bg-white p-8 rounded-xl shadow-sm w-full max-w-sm">
        <h1 className="text-2xl font-bold mb-6 text-center">Entrar no Vizy</h1>
        <form className="space-y-4">
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
            />
          </div>
          <button
            type="submit"
            className="w-full bg-brand-700 text-white py-2 rounded-lg font-semibold hover:bg-brand-900 transition"
          >
            Entrar
          </button>
        </form>
        <p className="text-center text-sm text-gray-500 mt-4">
          Ainda não tem conta?{" "}
          <Link href="/cadastro" className="text-brand-700 font-medium">
            Criar conta
          </Link>
        </p>
      </div>
    </main>
  );
}
