"use client";

import Link from "next/link";
import { useLanguage } from "@/contexts/LanguageContext";
import { useAuth } from "@/contexts/AuthContext";

export function Navbar() {
  const { t, lang, setLang } = useLanguage();
  const { user, logout } = useAuth();

  return (
    <header className="border-b bg-white sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link href="/" className="text-xl font-bold text-primary">
            Vizy
          </Link>
          <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-muted-foreground">
            <Link href="/deputados" className="hover:text-foreground transition-colors">{t("nav.deputies")}</Link>
            <Link href="/partidos" className="hover:text-foreground transition-colors">{t("nav.parties")}</Link>
            <Link href="/votacoes" className="hover:text-foreground transition-colors">{t("nav.votes")}</Link>
            <Link href="/proposicoes" className="hover:text-foreground transition-colors">{t("nav.bills")}</Link>
            <Link href="/doacoes" className="hover:text-foreground transition-colors">{t("nav.donations")}</Link>
            <Link href="/busca" className="hover:text-foreground transition-colors">{t("nav.search")}</Link>
            <Link href="/digest" className="hover:text-foreground transition-colors font-semibold text-primary">{t("nav.digest")}</Link>
          </nav>
        </div>
        <div className="flex items-center gap-3">
          {/* Language toggle */}
          <div className="flex items-center text-xs font-medium border rounded-md overflow-hidden">
            <button
              onClick={() => setLang("pt")}
              className={`px-2 py-1 transition-colors ${lang === "pt" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
            >
              PT
            </button>
            <button
              onClick={() => setLang("en")}
              className={`px-2 py-1 transition-colors ${lang === "en" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
            >
              EN
            </button>
          </div>
          {user ? (
            <>
              <Link href="/feed" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                {t("nav.feed")}
              </Link>
              <span className="text-sm text-muted-foreground">{user.name.split(" ")[0]}</span>
              <button
                onClick={logout}
                className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              >
                {t("nav.logout")}
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                {t("nav.login")}
              </Link>
              <Link href="/cadastro" className="text-sm font-medium bg-primary text-primary-foreground px-4 py-1.5 rounded-md hover:bg-primary/90 transition-colors">
                {t("nav.signup")}
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
