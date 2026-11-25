export const num = (n: number) => n.toLocaleString("en-IN");
export const pct = (n: number, d = 1) => `${n.toFixed(d).replace(/\.0$/, "")}%`;
export const SENT_COLORS: Record<string, string> = { Positive: "var(--pos)", Neutral: "var(--neu)", Mixed: "var(--mix)", Negative: "var(--neg)", Uncertain: "var(--unc)", Unclear: "var(--unc)" };

export function shortDate(d: string | null) {
  if (!d) return "undated";
  const dt = new Date(d + "T00:00:00");
  return isNaN(+dt) ? d : dt.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export const SOURCE_SHORT: Record<string, string> = { "Google Play Store": "Google Play", "ConsumerComplaints.in": "ConsumerComplaints", PissedConsumer: "PissedConsumer", Reddit: "Reddit" };

/** Short readable label for a long theme name. */
export const THEME_SHORT: Record<string, string> = {
  T1: "Unreliable fulfilment",
  T2: "Price, fees and policy",
  T3: "Support, refunds and resolution",
  T4: "Service quality, conduct and trust",
  T5: "Coverage, services and app",
};

export function plural(n: number, one: string, many = one + "s") {
  return `${num(n)} ${n === 1 ? one : many}`;
}
