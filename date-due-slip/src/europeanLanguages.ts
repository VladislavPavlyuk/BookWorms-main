/** European languages for Advanced Search — English first, then A–Z by English name. */
export type EuroLang = { code: string; label: string };

export const EUROPEAN_LANGUAGES: EuroLang[] = [
  { code: "eng", label: "English" },
  { code: "alb", label: "Albanian" },
  { code: "baq", label: "Basque" },
  { code: "bel", label: "Belarusian" },
  { code: "bos", label: "Bosnian" },
  { code: "bre", label: "Breton" },
  { code: "bul", label: "Bulgarian" },
  { code: "cat", label: "Catalan" },
  { code: "cor", label: "Cornish" },
  { code: "cos", label: "Corsican" },
  { code: "cze", label: "Czech" },
  { code: "dan", label: "Danish" },
  { code: "dut", label: "Dutch" },
  { code: "est", label: "Estonian" },
  { code: "fao", label: "Faroese" },
  { code: "fin", label: "Finnish" },
  { code: "fre", label: "French" },
  { code: "fry", label: "Frisian" },
  { code: "glg", label: "Galician" },
  { code: "geo", label: "Georgian" },
  { code: "ger", label: "German" },
  { code: "gre", label: "Greek" },
  { code: "hun", label: "Hungarian" },
  { code: "ice", label: "Icelandic" },
  { code: "gle", label: "Irish" },
  { code: "ita", label: "Italian" },
  { code: "lav", label: "Latvian" },
  { code: "lit", label: "Lithuanian" },
  { code: "ltz", label: "Luxembourgish" },
  { code: "mac", label: "Macedonian" },
  { code: "mlt", label: "Maltese" },
  { code: "nor", label: "Norwegian" },
  { code: "oci", label: "Occitan" },
  { code: "pol", label: "Polish" },
  { code: "por", label: "Portuguese" },
  { code: "rum", label: "Romanian" },
  { code: "roh", label: "Romansh" },
  { code: "rus", label: "Russian" },
  { code: "gla", label: "Scottish Gaelic" },
  { code: "srp", label: "Serbian" },
  { code: "slo", label: "Slovak" },
  { code: "slv", label: "Slovenian" },
  { code: "spa", label: "Spanish" },
  { code: "swe", label: "Swedish" },
  { code: "ukr", label: "Ukrainian" },
  { code: "wel", label: "Welsh" },
];

export function languageLabel(code?: string | null): string {
  const c = (code || "").trim().toLowerCase();
  if (!c) return "Усі мови";
  return EUROPEAN_LANGUAGES.find((l) => l.code === c)?.label || code || "Усі мови";
}
