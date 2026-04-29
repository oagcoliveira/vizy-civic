import type { Lang } from "@/lib/translations";

const POLICY_AREA_LABELS_EN: Record<string, string> = {
  // Current canonical taxonomy used by AI enrichment
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

  // Legacy/live labels already stored in the database
  "Administração Pública": "Public administration",
  "Agricultura e Agropecuária": "Agriculture and livestock",
  "Assistência Social": "Social assistance",
  "Ciência e Tecnologia": "Science and technology",
  "Comunicação e Mídia": "Communications and media",
  "Cultura e Esporte": "Culture and sport",
  "Direitos Humanos": "Human rights",
  "Economia e Finanças": "Economy and finance",
  "Meio Ambiente": "Environment",
  "Política": "Politics",
  "Saúde Pública": "Public health",
  "Segurança Pública": "Public security",
  "Trabalho": "Labour",
};

const NORMALIZED_POLICY_AREA_LABELS_EN: Record<string, string> = Object.fromEntries(
  Object.entries(POLICY_AREA_LABELS_EN).map(([key, value]) => [normalizePolicyArea(key), value])
);

function normalizePolicyArea(area: string): string {
  return area
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

export function getPolicyAreaLabel(area: string, lang: Lang): string {
  if (lang !== "en") return area;

  const trimmedArea = area.trim();
  return (
    POLICY_AREA_LABELS_EN[trimmedArea] ??
    NORMALIZED_POLICY_AREA_LABELS_EN[normalizePolicyArea(trimmedArea)] ??
    trimmedArea
  );
}
