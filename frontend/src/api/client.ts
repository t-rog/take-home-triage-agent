import type { Enquiry, EnquiryListResponse, ServiceLineOption, Team } from "../types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message = body?.error?.message ?? `Request failed with status ${res.status}`;
    throw new Error(message);
  }
  return res.json();
}

export interface EnquiryFormPayload {
  contact_name: string;
  contact_email: string;
  company_name: string;
  industry: string;
  industry_other?: string | null;
  company_size: string;
  urgency: string;
  description: string;
}

export const api = {
  createEnquiry: (payload: EnquiryFormPayload) =>
    request<Enquiry>("/enquiries", { method: "POST", body: JSON.stringify(payload) }),

  listEnquiries: (params?: Record<string, string>) => {
    const qs = params ? `?${new URLSearchParams(params).toString()}` : "";
    return request<EnquiryListResponse>(`/enquiries${qs}`);
  },

  review: (
    id: number,
    payload: {
      reviewer: string;
      action: "approve" | "correct" | "close";
      corrected_service_line?: string;
      corrected_complexity?: string;
      corrected_team_id?: number;
    },
  ) => request<Enquiry>(`/enquiries/${id}/review`, { method: "POST", body: JSON.stringify(payload) }),

  retry: (id: number) => request<Enquiry>(`/enquiries/${id}/retry`, { method: "POST" }),

  listTeams: () => request<Team[]>("/teams"),

  listServiceLines: () => request<ServiceLineOption[]>("/service-lines"),
};
