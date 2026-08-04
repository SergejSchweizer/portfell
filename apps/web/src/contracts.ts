
export type ApiFieldOptions = Readonly<{
  exchange: readonly string[];
  instrument_type: readonly string[];
  country: readonly string[];
  currency: readonly string[];
}>;

export type ApiMetadataFetch = Readonly<{
  status: "succeeded";
  row_count: number;
  exchange_count: number;
  requested_exchange_count: number;
  skipped_exchange_count: number;
  skipped_exchanges: readonly string[];
}>;

export type ApiMetadataProject = Readonly<{
  project: Readonly<{ project_id: string; name: string }>;
  selection: Readonly<{ selection_id: string; name: string }>;
  selected_count: number;
}>;

export type ApiQuoteFetch = Readonly<{
  status: "succeeded";
  progress?: number;
  selected_listing_count?: number;
  quote_successes?: number;
  quote_errors?: number;
  silver_quote_rows?: number;
}>;

export type ApiProjects = Readonly<{
  items: readonly Readonly<{
    project_id: string;
    name: string;
    selected_count?: number;
  }>[];
}>;

export type ApiUnivariateSummaryRow = Readonly<{
  name: string;
  category: string;
  mean: string | number | null;
  median: string | number | null;
  three_std_range: string | number | null;
  filter_options: readonly { value: string; label?: string }[];
}>;

export type ApiUnivariateSummary = Readonly<{
  items: readonly ApiUnivariateSummaryRow[];
}>;
