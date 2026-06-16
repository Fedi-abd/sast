/* Formatting + enum mapping; mirrors the prototype's helpers. */

export const sourceLabel = (type) =>
  type === "git" ? "GIT_REPO" : type === "upload" ? "UPLOAD" : "LOCAL_PATH";

export function relativeTime(iso) {
  if (!iso) return "-";
  const secs = Math.round((Date.now() - new Date(iso)) / 1000);
  if (secs < 60) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} hr${hrs > 1 ? "s" : ""} ago`;
  const days = Math.round(hrs / 24);
  return `${days} day${days > 1 ? "s" : ""} ago`;
}

export function formatDuration(seconds) {
  if (seconds == null) return "-";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function fmtDateTime(iso) {
  if (!iso) return "-";
  return iso.replace("T", " ").replace("Z", "").slice(0, 16);
}

export function scanStatusMeta(status) {
  switch (status) {
    case "SUCCESS": return { kind: "ok",  label: "SUCCESS" };
    case "RUNNING": return { kind: "run", label: "RUNNING" };
    case "FAILED":  return { kind: "err", label: "FAILED" };
    default:        return { kind: "run", label: status || "-" };
  }
}

export function owaspParse(category) {
  if (!category || category === "UNMAPPED") return { code: "-", label: "Unmapped" };
  const m = category.match(/^([A-Z]\d+):\d+-(.+)$/);
  if (m) return { code: m[1], label: m[2] };
  return { code: "-", label: category };
}

export function confidencePct(score) {
  if (score == null) return "-";
  return `${Math.round(score * 100)}%`;
}

export const severityLabel = (sev) =>
  sev === "HIGH" ? "high" : sev === "MEDIUM" ? "med" : "low";

export const sourceTarget = (p) =>
  p.source_type === "git" ? p.git_url :
  p.source_type === "upload" ? (p.source_filename || p.source_archive) :
  p.repo_path;
