import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Navbar } from "@/components/Navbar";
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
        <Navbar />
        <div className="min-h-screen bg-background">{children}</div>
      </body>
    </html>
  );
}
