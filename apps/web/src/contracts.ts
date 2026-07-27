export type ApiSession = Readonly<{
  authenticated?: boolean;
  user_id?: string;
  email?: string;
  display_name?: string;
  auth_provider?: string;
  csrf_token?: string;
}>;

export type ApiCredentialStatus = Readonly<{
  status: "active" | "inactive";
  masked_label?: string;
}>;

export type ApiProject = Readonly<{
  project_id: string;
  name: string;
  selected_count?: number;
  data_loaded?: boolean;
}>;

export type ApiProjects = Readonly<{
  items: readonly ApiProject[];
}>;

export type ApiFieldOptions = Readonly<{
  exchange: readonly string[];
  instrument_type: readonly string[];
  country: readonly string[];
  currency: readonly string[];
}>;

export type ApiProgress = Readonly<{
  status?: "succeeded" | "running" | "failed";
  progress?: number;
  selected_count?: number;
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
