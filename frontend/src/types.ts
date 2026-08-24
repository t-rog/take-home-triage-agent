export type Industry =
  | "financial_services"
  | "healthcare"
  | "manufacturing"
  | "retail"
  | "public_sector"
  | "technology"
  | "professional_services"
  | "other";

export type CompanySize = "size_1_50" | "size_51_250" | "size_251_1000" | "size_1000_plus";

export type Urgency = "exploring" | "within_month" | "immediate";

export type ServiceLine =
  | "data_analytics"
  | "risk_compliance"
  | "operations"
  | "technology_transformation"
  | "people_change"
  | "finance_advisory";

export type Complexity = "simple" | "moderate" | "complex";

export type Status = "routed" | "needs_review" | "failed" | "closed";

export type Flag = "insufficient_information" | "out_of_scope" | "spam" | "multiple_service_lines";

export interface Team {
  id: number;
  name: string;
  service_line: ServiceLine | null;
  lead_name: string;
  lead_email: string;
  is_default: boolean;
}

export interface Enquiry {
  id: number;
  submitted_at: string;
  contact_name: string;
  contact_email: string;
  company_name: string;
  industry: Industry;
  industry_other: string | null;
  company_size: CompanySize;
  urgency: Urgency;
  description: string;
  service_line: ServiceLine | null;
  complexity: Complexity | null;
  confidence: number | null;
  rationale: string | null;
  runner_up_service_line: ServiceLine | null;
  runner_up_confidence: number | null;
  key_signals: string[];
  flags: Flag[];
  status: Status;
  team: Team | null;
  matched_rule: string | null;
  routed_at: string | null;
  error_message: string | null;
  reviewed: boolean;
  reviewed_by: string | null;
  was_corrected: boolean;
  created_at: string;
  updated_at: string;
}

export interface EnquiryListResponse {
  enquiries: Enquiry[];
  counts_by_status: Partial<Record<Status, number>>;
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ServiceLineOption {
  value: ServiceLine;
  description: string;
}

export const INDUSTRIES: Industry[] = [
  "financial_services",
  "healthcare",
  "manufacturing",
  "retail",
  "public_sector",
  "technology",
  "professional_services",
  "other",
];

export const COMPANY_SIZES: { value: CompanySize; label: string }[] = [
  { value: "size_1_50", label: "1-50" },
  { value: "size_51_250", label: "51-250" },
  { value: "size_251_1000", label: "251-1000" },
  { value: "size_1000_plus", label: "1000+" },
];

export const URGENCIES: { value: Urgency; label: string }[] = [
  { value: "exploring", label: "Exploring" },
  { value: "within_month", label: "Within a month" },
  { value: "immediate", label: "Immediate" },
];

export const COMPLEXITIES: Complexity[] = ["simple", "moderate", "complex"];
