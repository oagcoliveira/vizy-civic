"use client";

import { useState } from "react";
import Link from "next/link";
import { useLanguage } from "@/contexts/LanguageContext";

export default function CadastroPage() {
  const { t } = useLanguage();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="bg-white p-8 rounded-xl shadow-sm w-full max-w-sm">
        <h1 className="text-2xl font-bold mb-6 text-center">{t("signup.title")}</h1>
        <form className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">{t("signup.name")}</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">{t("signup.email")}</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">{t("signup.password")}</label>
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
            {t("signup.submit")}
          </button>
        </form>
        <p className="text-center text-sm text-gray-500 mt-4">
          {t("signup.has_account")}{" "}
          <Link href="/login" className="text-brand-700 font-medium">
            {t("signup.login_link")}
          </Link>
        </p>
      </div>
    </main>
  );
}
