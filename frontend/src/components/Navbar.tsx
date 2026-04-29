"use client";

import Link from "next/link";
import { useState } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import { useAuth } from "@/contexts/AuthContext";

const PUBLIC_NAV_LINKS = [
  { href: "/deputados", key: "nav.deputies" },
  { href: "/proposicoes", key: "nav.bills" },
  { href: "/votacoes", key: "nav.votes" },
  { href: "/doacoes", key: "nav.donations" },
  { href: "/partidos", key: "nav.parties" },
  { href: "/busca", key: "nav.search" },
  { href: "/digest", key: "nav.digest" },
  { href: "/feed", key: "nav.feed", authOnly: true },
] as const;

export function Navbar() {
  const { t, lang, setLang } = useLanguage();
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="border-b bg-white sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Left: logo + desktop nav */}
        <div className="flex items-center gap-8">
          <Link href="/" className="text-xl font-bold text-primary">
            Vizy
          </Link>
          <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-muted-foreground">
            {PUBLIC_NAV_LINKS.filter(l => !('authOnly' in l) || user).map(({ href, key }) => (
              <Link
                key={href}
                href={href}
                className="hover:text-foreground transition-colors"
              >
                {t(key)}
              </Link>
            ))}
          </nav>
        </div>

        {/* Right: language toggle + auth + mobile hamburger */}
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

          {/* Auth links — hidden on mobile to keep header clean */}
          <div className="hidden md:flex items-center gap-3">
            {user ? (
              <>
                {user.email === "oagcoliveira@gmail.com" && (
                  <Link href="/admin" className="text-xs font-medium text-muted-foreground hover:text-foreground transition-colors border border-dashed rounded px-2 py-0.5">
                    Admin
                  </Link>
                )}
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

          {/* Hamburger — visible only on mobile */}
          <button
            className="md:hidden flex flex-col justify-center items-center w-8 h-8 gap-1.5"
            onClick={() => setMobileOpen((prev) => !prev)}
            aria-label="Toggle menu"
          >
            <span
              className={`block w-5 h-0.5 bg-foreground transition-transform duration-200 ${mobileOpen ? "translate-y-2 rotate-45" : ""}`}
            />
            <span
              className={`block w-5 h-0.5 bg-foreground transition-opacity duration-200 ${mobileOpen ? "opacity-0" : ""}`}
            />
            <span
              className={`block w-5 h-0.5 bg-foreground transition-transform duration-200 ${mobileOpen ? "-translate-y-2 -rotate-45" : ""}`}
            />
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="md:hidden border-t bg-white px-4 py-4 flex flex-col gap-4">
          <nav className="flex flex-col gap-3 text-sm font-medium text-muted-foreground">
            {PUBLIC_NAV_LINKS.filter(l => !('authOnly' in l) || user).map(({ href, key }) => (
              <Link
                key={href}
                href={href}
                className="hover:text-foreground transition-colors"
                onClick={() => setMobileOpen(false)}
              >
                {t(key)}
              </Link>
            ))}
          </nav>

          <div className="border-t pt-3 flex flex-col gap-3 text-sm font-medium text-muted-foreground">
            {user ? (
              <>
                {user.email === "oagcoliveira@gmail.com" && (
                  <Link href="/admin" className="text-xs hover:text-foreground transition-colors border border-dashed rounded px-2 py-0.5 w-fit" onClick={() => setMobileOpen(false)}>
                    Admin
                  </Link>
                )}
                <span className="text-muted-foreground">{user.name.split(" ")[0]}</span>
                <button
                  onClick={() => { logout(); setMobileOpen(false); }}
                  className="text-left hover:text-foreground transition-colors"
                >
                  {t("nav.logout")}
                </button>
              </>
            ) : (
              <>
                <Link href="/login" className="hover:text-foreground transition-colors" onClick={() => setMobileOpen(false)}>
                  {t("nav.login")}
                </Link>
                <Link
                  href="/cadastro"
                  className="bg-primary text-primary-foreground px-4 py-1.5 rounded-md hover:bg-primary/90 transition-colors w-fit"
                  onClick={() => setMobileOpen(false)}
                >
                  {t("nav.signup")}
                </Link>
              </>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
