export interface Row { label: string; note: string; values: string[] }
export interface Table { designs: string[]; ours: number; rows: Row[] }
export interface MonitorWindow {
  window: string; world: string; reader: string; searches: number; novel_share: number; confidence_psi: number | null;
  fallback_calls_per_search: number; usd_per_search: number; review_per_search: number; alerts: string[]; retrain: boolean;
}
export interface Check { check: string; value: number; limit: string; passed: boolean }
export interface Release {
  version: string; production: boolean; corpora: string[]; sentences: number; accuracy: number; macro_f1: number;
  ece: number; min_confidence: number; int8_kb: number; float32_kb: number; parity: number; passed: boolean; checks: Check[];
}
export interface Console {
  generated_from: string; designs: string[]; ours: number; ledger: Row[];
  reasons: Record<string, Record<string, number>>; target: number;
  drift: Table; monitor: MonitorWindow[]; releases: Release[];
}
