import { useMutation } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { api } from "../api/client";
import { titleCase } from "../format";
import { COMPANY_SIZES, INDUSTRIES, URGENCIES } from "../types";

const initialForm = {
  contact_name: "",
  contact_email: "",
  company_name: "",
  industry: "technology",
  industry_other: "",
  company_size: "size_1_50",
  urgency: "within_month",
  description: "",
};

export default function SubmitPage() {
  const [form, setForm] = useState(initialForm);
  const [reference, setReference] = useState<number | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api.createEnquiry({
        ...form,
        industry_other: form.industry === "other" ? form.industry_other : null,
      }),
    onSuccess: (enquiry) => {
      setReference(enquiry.id);
      setForm(initialForm);
    },
  });

  function update<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setReference(null);
    mutation.mutate();
  }

  const descriptionTooShort = form.description.length > 0 && form.description.length < 40;

  return (
    <div style={{ maxWidth: 640, margin: "0 auto" }}>
      <h1>Tell us what you need</h1>
      <p className="subtitle">
        A brief description is enough to get you routed to the right team.
      </p>

      <form className="card" onSubmit={handleSubmit}>
        <div className="form-grid">
          <div>
            <label htmlFor="contact_name">Your name</label>
            <input
              id="contact_name"
              required
              value={form.contact_name}
              onChange={(e) => update("contact_name", e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="contact_email">Email</label>
            <input
              id="contact_email"
              type="email"
              required
              value={form.contact_email}
              onChange={(e) => update("contact_email", e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="company_name">Company</label>
            <input
              id="company_name"
              required
              value={form.company_name}
              onChange={(e) => update("company_name", e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="industry">Industry</label>
            <select
              id="industry"
              value={form.industry}
              onChange={(e) => update("industry", e.target.value)}
            >
              {INDUSTRIES.map((i) => (
                <option key={i} value={i}>
                  {titleCase(i)}
                </option>
              ))}
            </select>
          </div>
          {form.industry === "other" && (
            <div className="full">
              <label htmlFor="industry_other">Tell us your industry</label>
              <input
                id="industry_other"
                required
                value={form.industry_other}
                onChange={(e) => update("industry_other", e.target.value)}
              />
            </div>
          )}
          <div>
            <label htmlFor="company_size">Company size</label>
            <select
              id="company_size"
              value={form.company_size}
              onChange={(e) => update("company_size", e.target.value)}
            >
              {COMPANY_SIZES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="urgency">Urgency</label>
            <select
              id="urgency"
              value={form.urgency}
              onChange={(e) => update("urgency", e.target.value)}
            >
              {URGENCIES.map((u) => (
                <option key={u.value} value={u.value}>
                  {u.label}
                </option>
              ))}
            </select>
          </div>
          <div className="full">
            <label htmlFor="description">What do you need help with?</label>
            <textarea
              id="description"
              required
              minLength={40}
              value={form.description}
              onChange={(e) => update("description", e.target.value)}
            />
            <div className="hint">
              {form.description.length}/40 characters minimum
              {descriptionTooShort && <span className="field-error"> — add a bit more detail</span>}
            </div>
          </div>
        </div>

        <div style={{ marginTop: 20 }}>
          <button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Submitting..." : "Submit enquiry"}
          </button>
        </div>

        {reference !== null && (
          <div className="success-banner">
            Thanks — your enquiry has been received. Reference #{reference}.
          </div>
        )}
        {mutation.isError && (
          <div className="error-banner">{(mutation.error as Error).message}</div>
        )}
      </form>
    </div>
  );
}
