import type { Lang } from "@/lib/translations";

const POLICY_AREA_LABELS_EN: Record<string, string> = {
  "Economia e finanças públicas": "Economy and public finance",
  "Saúde": "Health",
  "Educação": "Education",
  "Segurança pública": "Public security",
  "Meio ambiente e clima": "Environment and climate",
  "Agropecuária": "Agriculture and livestock",
  "Infraestrutura e transportes": "Infrastructure and transport",
  "Habitação e urbanismo": "Housing and urban planning",
  "Previdência social": "Social security",
  "Trabalho e emprego": "Labour and employment",
  "Direitos humanos e minorias": "Human rights and minorities",
  "Política externa e defesa": "Foreign policy and defence",
  "Ciência, tecnologia e inovação": "Science, technology and innovation",
  "Cultura, esportes e lazer": "Culture, sports and leisure",
  "Comunicações e mídia": "Communications and media",
  "Energia": "Energy",
  "Tributação": "Taxation",
  "Sistema político e eleitoral": "Political and electoral system",
  "Judiciário e legislativo": "Judiciary and legislature",
  "Outros": "Other",
};

export function getPolicyAreaLabel(area: string, lang: Lang): string {
  if (lang !== "en") return area;
  return POLICY_AREA_LABELS_EN[area] ?? area;
}
