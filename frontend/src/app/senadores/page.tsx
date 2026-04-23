"use client";

import { useLanguage } from "@/contexts/LanguageContext";

export default function SenadoresPage() {
  const { t } = useLanguage();
  return (
    <main className="max-w-5xl mx-auto px-6 py-12">
      <h1 className="text-3xl font-bold mb-6">{t("senators.title")}</h1>
      <p className="text-gray-500">{t("senators.loading")}</p>
    </main>
  );
}
