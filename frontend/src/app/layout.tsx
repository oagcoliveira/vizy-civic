import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Navbar } from "@/components/Navbar";
import { AuthProvider } from "@/contexts/AuthContext";
import { LanguageProvider } from "@/contexts/LanguageContext";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Vizy — Acompanhe o Congresso",
  description:
    "Acompanhe votações, discursos e financiamentos dos seus deputados e senadores de forma simples e transparente.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className={inter.className}>
        <AuthProvider>
          <LanguageProvider>
            <Navbar />
            <div className="min-h-screen bg-background">{children}</div>
          </LanguageProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
