import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import { titleCase } from "../format";
import { COMPLEXITIES, Enquiry, Status } from "../types";

// Rows are forced to a single line each (see the Client cell below), which
// makes their rendered height predictable enough to compute how many fit.
const ROW_HEIGHT = 58;
const TABLE_HEADER_HEIGHT = 36;
const MIN_ROWS = 3;

const TABS: { key: Status | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "needs_review", label: "Needs review" },
  { key: "routed", label: "Routed" },
  { key: "failed", label: "Failed" },
  { key: "closed", label: "Closed" },
];

// Mirrors the runner-up margin check in backend/app/services/pipeline.py's
// _needs_review -- kept in sync manually since the threshold isn't exposed
// by the API.
const RUNNER_UP_MARGIN_THRESHOLD = 0.15;

function needsReviewReason(enquiry: Enquiry): string {
  const reasons: string[] = [];
  if (enquiry.flags.length > 0) {
    reasons.push(`flagged as ${enquiry.flags.map((f) => f.replace(/_/g, " ")).join(", ")}`);
  }
  if (
    enquiry.confidence !== null &&
    enquiry.runner_up_confidence !== null &&
    enquiry.confidence - enquiry.runner_up_confidence <= RUNNER_UP_MARGIN_THRESHOLD
  ) {
    reasons.push("a close runner-up match");
  }
  if (reasons.length === 0) {
    reasons.push("confidence below the auto-routing threshold");
  }
  return reasons.join(" and ");
}

function relativeTime(iso: string): string {
  const minutes = (Date.now() - new Date(iso).getTime()) / 60_000;
  if (minutes < 1) return "just now";
  if (minutes < 60) {
    const m = Math.round(minutes);
    return `${m} min${m === 1 ? "" : "s"} ago`;
  }
  const hrs = minutes / 60;
  if (hrs < 24) return `${Math.round(hrs)} hrs ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function ConfidenceBar({ value }: { value: number | null }) {
  if (value === null) return <span>-</span>;
  const pct = Math.round(value * 100);
  return (
    <span className="confidence-bar">
      <span className="confidence-bar-track">
        <span className="confidence-bar-fill" style={{ width: `${pct}%` }} />
      </span>
      <span>{pct}%</span>
    </span>
  );
}

function StatusPill({ status }: { status: Status }) {
  const labels: Record<Status, string> = {
    routed: "Routed",
    needs_review: "Needs review",
    failed: "Failed",
    closed: "Closed",
  };
  return <span className={`pill pill-${status}`}>{labels[status]}</span>;
}

export default function QueuePage() {
  const [tab, setTab] = useState<Status | "all">("all");
  const [query, setQuery] = useState("");
  const [lineFilter, setLineFilter] = useState("");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [rowsPerPage, setRowsPerPage] = useState(8);
  const tableAreaRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  function resetToFirstPage() {
    setPage(1);
  }

  // The row count is derived from actual available space, not a fixed guess,
  // so the list never needs its own scrollbar -- overflow becomes another page.
  useEffect(() => {
    const el = tableAreaRef.current;
    if (!el) return;
    const measure = () => {
      const available = el.clientHeight - TABLE_HEADER_HEIGHT;
      const rows = Math.max(MIN_ROWS, Math.floor(available / ROW_HEIGHT));
      setRowsPerPage((prev) => {
        if (prev !== rows) setPage(1);
        return rows;
      });
    };
    // Debounced: a resize can fire the observer more than once for what is
    // ultimately one settled layout, and each firing would otherwise trigger
    // its own state update and refetch.
    let debounce: ReturnType<typeof setTimeout>;
    const scheduleMeasure = () => {
      clearTimeout(debounce);
      debounce = setTimeout(measure, 80);
    };
    measure();
    const observer = new ResizeObserver(scheduleMeasure);
    observer.observe(el);
    return () => {
      clearTimeout(debounce);
      observer.disconnect();
    };
  }, []);

  const params: Record<string, string> = { page: String(page), page_size: String(rowsPerPage) };
  if (tab !== "all") params.status = tab;
  if (query.trim()) params.q = query.trim();
  if (lineFilter) params.service_line = lineFilter;

  const enquiriesQuery = useQuery({
    queryKey: ["enquiries", params],
    queryFn: () => api.listEnquiries(params),
  });

  const teamsQuery = useQuery({ queryKey: ["teams"], queryFn: api.listTeams });
  const serviceLinesQuery = useQuery({ queryKey: ["service-lines"], queryFn: api.listServiceLines });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["enquiries"] });

  const reviewMutation = useMutation({
    mutationFn: (vars: { id: number; payload: Parameters<typeof api.review>[1] }) =>
      api.review(vars.id, vars.payload),
    onSuccess: invalidate,
  });

  const retryMutation = useMutation({
    mutationFn: (id: number) => api.retry(id),
    onSuccess: invalidate,
  });

  const data = enquiriesQuery.data;
  const counts = data?.counts_by_status;
  const totalAll = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0;
  const selected = data?.enquiries.find((e) => e.id === selectedId) ?? null;

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: "1 1 auto", minHeight: 0 }}>
      <div style={{ flexShrink: 0 }}>
        <h1>Enquiry queue</h1>
        <p className="subtitle">Every enquiry, its classification, and where it's headed.</p>
      </div>

      <div className="tile-grid" style={{ flexShrink: 0 }}>
        <button
          type="button"
          className="tile"
          style={{ textAlign: "left", cursor: "pointer", color: "inherit" }}
          onClick={() => {
            setTab("needs_review");
            resetToFirstPage();
          }}
        >
          <div className="tile-value">{counts?.needs_review ?? 0}</div>
          <div className="tile-label">Needs review</div>
        </button>
        <button
          type="button"
          className="tile"
          style={{ textAlign: "left", cursor: "pointer", color: "inherit" }}
          onClick={() => {
            setTab("failed");
            resetToFirstPage();
          }}
        >
          <div className="tile-value">{counts?.failed ?? 0}</div>
          <div className="tile-label">Failed</div>
        </button>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap", flexShrink: 0 }}>
        <div className="tabs" style={{ marginBottom: 0 }}>
          {TABS.map((t) => {
            const count = t.key === "all" ? totalAll : counts?.[t.key] ?? 0;
            return (
              <button
                key={t.key}
                className={`tab ${tab === t.key ? "active" : ""}`}
                onClick={() => {
                  setTab(t.key);
                  resetToFirstPage();
                }}
                type="button"
              >
                {t.label} ({count})
              </button>
            );
          })}
        </div>
        <div style={{ display: "flex", gap: 10, marginLeft: "auto" }}>
          <input
            placeholder="Search client or text..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              resetToFirstPage();
            }}
            style={{ width: 200 }}
          />
          <select
            value={lineFilter}
            onChange={(e) => {
              setLineFilter(e.target.value);
              resetToFirstPage();
            }}
            style={{ width: 200 }}
          >
            <option value="">All service lines</option>
            {(serviceLinesQuery.data ?? []).map((sl) => (
              <option key={sl.value} value={sl.value}>
                {titleCase(sl.value)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ display: "flex", gap: 24, alignItems: "stretch", flexWrap: "wrap", flex: "1 1 auto", minHeight: 0 }}>
        <div
          style={{
            flex: "3 1 560px",
            minWidth: 0,
            height: "100%",
            minHeight: 0,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div ref={tableAreaRef} style={{ flex: "1 1 auto", minHeight: 0, overflowX: "auto", overflowY: "hidden" }}>
            {enquiriesQuery.isLoading && <p>Loading...</p>}

            {data && data.enquiries.length === 0 && (
              <div className="card empty-state">
                {tab === "needs_review"
                  ? "Every enquiry this week routed on its own."
                  : "No enquiries match this view."}
              </div>
            )}

            {data && data.enquiries.length > 0 && (
              <table style={{ tableLayout: "fixed", width: "100%", minWidth: 990 }}>
                <colgroup>
                  <col style={{ width: 56 }} />
                  <col style={{ width: 90 }} />
                  <col style={{ width: 230 }} />
                  <col style={{ width: 150 }} />
                  <col style={{ width: 100 }} />
                  <col style={{ width: 110 }} />
                  <col style={{ width: 160 }} />
                  <col style={{ width: 94 }} />
                </colgroup>
                <thead>
                  <tr>
                    <th>Ref</th>
                    <th>Received</th>
                    <th>Client</th>
                    <th>Service line</th>
                    <th>Complexity</th>
                    <th>Confidence</th>
                    <th>Assigned to</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.enquiries.map((e) => (
                    <tr
                      key={e.id}
                      className={
                        (e.id === selectedId ? "row-sel " : "") +
                        (e.status === "needs_review" ? "row-needs-review" : e.status === "failed" ? "row-failed" : "")
                      }
                      onClick={() => setSelectedId(e.id === selectedId ? null : e.id)}
                      style={{ cursor: "pointer" }}
                    >
                      <td style={{ whiteSpace: "nowrap", fontWeight: 600 }}>#{e.id}</td>
                      <td style={{ whiteSpace: "nowrap", opacity: 0.7 }}>{relativeTime(e.submitted_at)}</td>
                      <td style={{ maxWidth: 240 }}>
                        <div style={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {e.company_name}
                        </div>
                        <div
                          style={{
                            color: "#5c625c",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                            fontSize: 12,
                          }}
                        >
                          {e.description}
                        </div>
                      </td>
                      <td>{e.service_line ? <span className="badge">{titleCase(e.service_line)}</span> : "-"}</td>
                      <td>{e.complexity ? titleCase(e.complexity) : "-"}</td>
                      <td>
                        <ConfidenceBar value={e.confidence} />
                      </td>
                      <td>
                        {e.team ? (
                          <>
                            <div
                              className={e.status === "needs_review" ? "provisional" : ""}
                              style={{
                                fontWeight: 600,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {e.team.name}
                              {e.status === "needs_review" ? " (proposed)" : ""}
                            </div>
                            <div
                              style={{
                                color: "#5c625c",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                                fontSize: 12,
                              }}
                            >
                              {e.team.lead_name}
                            </div>
                          </>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td>
                        <StatusPill status={e.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {data && data.enquiries.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 12, flexShrink: 0 }}>
              <span style={{ fontSize: 12, opacity: 0.6 }}>
                {(data.page - 1) * data.page_size + 1}-{(data.page - 1) * data.page_size + data.enquiries.length} of{" "}
                {data.total}
              </span>
              <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
                <button
                  className="secondary"
                  type="button"
                  disabled={data.page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  ← Previous
                </button>
                <button
                  className="secondary"
                  type="button"
                  disabled={data.page >= data.total_pages}
                  onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </div>

        <div
          className="card"
          style={{
            flex: "1 1 420px",
            minWidth: 360,
            maxWidth: 480,
            height: "100%",
            minHeight: 0,
            padding: 0,
            overflowY: "auto",
          }}
        >
          {!selected && (
            <div style={{ padding: "36px 22px", textAlign: "center" }}>
              <div className="subtitle" style={{ marginBottom: 8 }}>
                Enquiry detail
              </div>
              <p style={{ fontSize: 13, opacity: 0.6 }}>
                Select an enquiry to see what the triage agent decided and correct it if needed.
              </p>
            </div>
          )}
          {selected && (
            <DetailPanel
              enquiry={selected}
              teams={teamsQuery.data ?? []}
              serviceLines={(serviceLinesQuery.data ?? []).map((s) => s.value)}
              onClose={() => setSelectedId(null)}
              onReview={(payload) => reviewMutation.mutate({ id: selected.id, payload })}
              onRetry={() => retryMutation.mutate(selected.id)}
              reviewPending={reviewMutation.isPending}
              retryPending={retryMutation.isPending}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function DetailPanel({
  enquiry,
  teams,
  serviceLines,
  onClose,
  onReview,
  onRetry,
  reviewPending,
  retryPending,
}: {
  enquiry: Enquiry;
  teams: { id: number; name: string }[];
  serviceLines: string[];
  onClose: () => void;
  onReview: (payload: Parameters<typeof api.review>[1]) => void;
  onRetry: () => void;
  reviewPending: boolean;
  retryPending: boolean;
}) {
  const [reviewer, setReviewer] = useState("");
  const [correctedServiceLine, setCorrectedServiceLine] = useState(enquiry.service_line ?? "");
  const [correctedComplexity, setCorrectedComplexity] = useState(enquiry.complexity ?? "");
  const [correctedTeamId, setCorrectedTeamId] = useState<number | "">(enquiry.team?.id ?? "");

  return (
    <div style={{ padding: "18px 22px 24px" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <span style={{ fontSize: 17, fontWeight: 700 }}>#{enquiry.id}</span>
        <StatusPill status={enquiry.status} />
        <button type="button" className="secondary" style={{ marginLeft: "auto", fontSize: 12, padding: "4px 10px" }} onClick={onClose}>
          Close
        </button>
      </div>
      <h2 style={{ fontSize: 18, margin: "10px 0 2px" }}>{enquiry.company_name}</h2>
      <div style={{ fontSize: 12, opacity: 0.6 }}>
        {enquiry.contact_name} &lt;{enquiry.contact_email}&gt; · received {relativeTime(enquiry.submitted_at)}
      </div>

      <div style={{ marginTop: 10, fontSize: 13 }}>
        {enquiry.team ? (
          <>
            Assigned to <strong>{enquiry.team.name}</strong>
            {enquiry.status === "needs_review" && <span className="provisional"> (proposed)</span>} —{" "}
            {enquiry.team.lead_name} ({enquiry.team.lead_email})
            {enquiry.routed_at && (
              <span style={{ opacity: 0.6 }}>
                {" "}
                · {enquiry.status === "needs_review" ? "proposed" : "assigned"} {relativeTime(enquiry.routed_at)}
              </span>
            )}
          </>
        ) : (
          <span style={{ opacity: 0.6 }}>Not yet assigned to a team.</span>
        )}
      </div>

      {enquiry.status === "needs_review" && (
        <div className="rationale-box" style={{ marginTop: 14 }}>
          <strong>Needs human attention.</strong> Confidence ({Math.round((enquiry.confidence ?? 0) * 100)}%) —{" "}
          {needsReviewReason(enquiry)}.
        </div>
      )}

      <div style={{ margin: "16px 0 8px", fontSize: 11, textTransform: "uppercase", opacity: 0.55 }}>Client submitted</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 14px", fontSize: 12.5 }}>
        <div>
          <div style={{ opacity: 0.5, fontSize: 10, textTransform: "uppercase" }}>Industry</div>
          <div>{enquiry.industry === "other" ? enquiry.industry_other : titleCase(enquiry.industry)}</div>
        </div>
        <div>
          <div style={{ opacity: 0.5, fontSize: 10, textTransform: "uppercase" }}>Company size</div>
          <div>{enquiry.company_size.replace("size_", "").replace(/_/g, "-")}</div>
        </div>
        <div>
          <div style={{ opacity: 0.5, fontSize: 10, textTransform: "uppercase" }}>Urgency</div>
          <div>{titleCase(enquiry.urgency)}</div>
        </div>
        <div>
          <div style={{ opacity: 0.5, fontSize: 10, textTransform: "uppercase" }}>Contact</div>
          <div>{enquiry.contact_email}</div>
        </div>
      </div>
      <blockquote
        style={{
          margin: "14px 0 0",
          padding: "10px 12px",
          borderLeft: "2px solid #b87a2e",
          fontSize: 13,
          lineHeight: 1.6,
          opacity: 0.9,
        }}
      >
        {enquiry.description}
      </blockquote>

      {(enquiry.rationale || enquiry.key_signals.length > 0 || enquiry.matched_rule) && (
        <>
          <div style={{ margin: "18px 0 8px", fontSize: 11, textTransform: "uppercase", opacity: 0.55 }}>
            Agent signals
          </div>
          {enquiry.rationale && (
            <div className="rationale-box">
              <strong>Rationale:</strong> {enquiry.rationale}
            </div>
          )}
          {enquiry.key_signals.length > 0 && (
            <div>
              {enquiry.key_signals.map((s, i) => (
                <span key={i} className="chip">
                  {s}
                </span>
              ))}
            </div>
          )}
          {enquiry.runner_up_service_line && (
            <p style={{ fontSize: 12.5, opacity: 0.75 }}>
              Runner-up: {titleCase(enquiry.runner_up_service_line)} (
              {Math.round((enquiry.runner_up_confidence ?? 0) * 100)}%)
            </p>
          )}
          {enquiry.matched_rule && (
            <p style={{ fontSize: 12, opacity: 0.6 }}>
              Matched rule: <strong>{enquiry.matched_rule}</strong>
            </p>
          )}
        </>
      )}

      {enquiry.reviewed && (
        <p style={{ fontSize: 12, opacity: 0.6 }}>
          {enquiry.status === "closed" ? "Closed" : enquiry.was_corrected ? "Corrected" : "Approved"}
          {enquiry.reviewed_by ? ` by ${enquiry.reviewed_by}` : ""}.
        </p>
      )}

      {enquiry.status === "needs_review" && (
        <div>
          <div style={{ margin: "18px 0 8px", fontSize: 11, textTransform: "uppercase", opacity: 0.55 }}>Review</div>
          <label>Reviewer</label>
          <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} />
          <label style={{ marginTop: 10 }}>Service line</label>
          <select value={correctedServiceLine} onChange={(e) => setCorrectedServiceLine(e.target.value as never)}>
            <option value="">-</option>
            {serviceLines.map((sl) => (
              <option key={sl} value={sl}>
                {titleCase(sl)}
              </option>
            ))}
          </select>
          <label style={{ marginTop: 10 }}>Complexity</label>
          <select value={correctedComplexity} onChange={(e) => setCorrectedComplexity(e.target.value as never)}>
            <option value="">-</option>
            {COMPLEXITIES.map((c) => (
              <option key={c} value={c}>
                {titleCase(c)}
              </option>
            ))}
          </select>
          <label style={{ marginTop: 10 }}>Team</label>
          <select
            value={correctedTeamId}
            onChange={(e) => setCorrectedTeamId(e.target.value ? Number(e.target.value) : "")}
          >
            <option value="">-</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>

          <div className="review-controls">
            <button type="button" disabled={reviewPending || !reviewer} onClick={() => onReview({ reviewer, action: "approve" })}>
              Approve
            </button>
            <button
              type="button"
              className="secondary"
              disabled={reviewPending || !reviewer}
              onClick={() =>
                onReview({
                  reviewer,
                  action: "correct",
                  corrected_service_line: correctedServiceLine || undefined,
                  corrected_complexity: correctedComplexity || undefined,
                  corrected_team_id: correctedTeamId ? Number(correctedTeamId) : undefined,
                })
              }
            >
              Correct
            </button>
            <button
              type="button"
              className="danger"
              disabled={reviewPending || !reviewer}
              onClick={() => onReview({ reviewer, action: "close" })}
            >
              Not a fit
            </button>
          </div>
        </div>
      )}

      {enquiry.status === "failed" && (
        <div style={{ marginTop: 18 }}>
          <div style={{ fontSize: 11, textTransform: "uppercase", opacity: 0.55, marginBottom: 8 }}>Failure</div>
          <p className="error-banner">{enquiry.error_message}</p>
          <button type="button" className="danger" disabled={retryPending} onClick={onRetry}>
            {retryPending ? "Retrying..." : "Retry"}
          </button>
        </div>
      )}
    </div>
  );
}
