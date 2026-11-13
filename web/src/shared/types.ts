export interface Row { label: string; note: string; values: string[] }
export interface Console {
  generated_from: string; designs: string[]; ledger: Row[]; reasons: Record<string, Record<string, number>>; target: number;
}
