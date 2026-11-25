import { postForm, postJson } from "../api/client";
import type { UploadAnalysis, UploadAnalysisReview } from "../api/types";

/** A visitor's own file, analysed in short steps. Nothing is stored on the server; the result lives only in this browser tab (sessionStorage). */
type Row = Record<string, unknown>;
export interface TempValidation {
  filename: string;
  summary: { rows_in_file: number; accepted: number; rejected: number; malformed: number; duplicates_in_file: number; already_in_approved_dataset: number; rows_with_warnings: number };
  validation: { column_mapping: Record<string, string>; issues: { line: number; severity: string; code: string; message: string }[] };
  rows: Row[];
  rows_not_analysed_due_to_limit: number;
  analysis_row_limit: number;
  rows_per_request: number;
}
export interface TempResult { analysis: UploadAnalysis; reviews: UploadAnalysisReview[] }
interface Usage { requests: number; successful_requests: number; failed_requests: number; input_tokens: number; output_tokens: number; neurons: number; seconds: number }
export type Progress = (phase: string, done: number, total: number, message: string) => void;

const KEY = (id: string) => `discovery-temp:${id}`;
export const isTemp = (id: string) => id.startsWith("tmp-");

export async function validateFile(file: File): Promise<TempValidation> {
  const form = new FormData();
  form.append("file", file);
  return (await postForm<TempValidation>("/temp/uploads/validate", form)).data;
}

/** Reads the comments a few at a time (two requests at once), then groups them and writes the insights. Returns the id of the stored-in-tab result. */
export async function analyseTemp(v: TempValidation, progress: Progress): Promise<string> {
  const id = `tmp-${Math.random().toString(36).slice(2, 10)}`;
  const size = Math.max(1, v.rows_per_request);
  const chunks: Row[][] = [];
  for (let i = 0; i < v.rows.length; i += size) chunks.push(v.rows.slice(i, i + size));
  const records: Row[][] = chunks.map(() => []);
  const usage: Usage[] = [];
  let done = 0, next = 0;
  progress("extraction", 0, chunks.length, `Reading ${v.rows.length} comments`);
  async function worker() {
    while (next < chunks.length) {
      const i = next++;
      const r = (await postJson<{ records: Row[]; usage: Usage }>("/temp/uploads/extract", { rows: chunks[i], session: id })).data;
      records[i] = r.records; usage.push(r.usage); done++;
      progress("extraction", done, chunks.length, `${Math.min(done * size, v.rows.length)} of ${v.rows.length} comments read`);
    }
  }
  await Promise.all([worker(), worker()]);
  progress("themes", 0, 1, "Grouping the comments into themes and writing insights");
  const out = (await postJson<{ analysis: UploadAnalysis; reviews: UploadAnalysisReview[] }>("/temp/uploads/summarise", {
    rows: v.rows, records: records.flat(), session: id, filename: v.filename, rows_in_file: v.summary.rows_in_file, usage_parts: usage,
  })).data;
  out.analysis.upload_id = id;
  // the whole analysis lives only in this tab; if the browser refuses to keep it, the page still shows it once
  try { sessionStorage.setItem(KEY(id), JSON.stringify(out)); } catch { memory.set(id, out); }
  memory.set(id, out);
  progress("done", 1, 1, "Done");
  return id;
}

const memory = new Map<string, TempResult>();
export function loadTemp(id: string): TempResult | null {
  const m = memory.get(id);
  if (m) return m;
  try { const raw = sessionStorage.getItem(KEY(id)); return raw ? (JSON.parse(raw) as TempResult) : null; } catch { return null; }
}
