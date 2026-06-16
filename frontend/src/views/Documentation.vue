<script setup>
import Icon from '../components/Icon.vue';
import Pill from '../components/Pill.vue';
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title rise-in">Documentation</h1>
        <div class="page-sub"><span class="mono">how the platform works · source types · scanners · exports</span></div>
      </div>
    </div>

    <div class="panel rise-in" style="margin-bottom: 20px">
      <div class="panel-head"><span class="panel-title">// quickstart</span></div>
      <div class="panel-body">
        <ol class="steps">
          <li><strong>Register a project.</strong> Open <em>Projects → New project</em> and point the platform at your code (see source types below).</li>
          <li><strong>Run a scan.</strong> On the project page, pick a scanner (or run both). Scans run in the background; the page refreshes on its own while they work.</li>
          <li><strong>Read the findings.</strong> Each result carries a severity and, where it can be determined, an OWASP Top 10 (2017) category. Filter by either.</li>
          <li><strong>Export.</strong> Download a PDF report or the raw data once a scan finishes.</li>
        </ol>
      </div>
    </div>

    <div class="two-col" style="grid-template-columns: 1fr 1fr; margin-bottom: 20px">
      <div class="panel">
        <div class="panel-head"><span class="panel-title">// source_types</span></div>
        <div class="panel-body">
          <dl class="dlist">
            <dt>Git URL</dt>
            <dd>An HTTPS repository on <span class="mono">github.com</span> or <span class="mono">gitlab.com</span>. An optional branch defaults to <span class="mono">main</span>. The repository is cloned at scan time.</dd>
            <dt>ZIP upload</dt>
            <dd>An archive of your source, extracted on the server before scanning. Subject to a per-account size cap and rejected if it tries to escape its folder or expand abnormally.</dd>
            <dt>Local path</dt>
            <dd>An absolute path already present on the scan host. Hidden by default; an administrator enables it for development use.</dd>
          </dl>
        </div>
      </div>

      <div class="panel">
        <div class="panel-head"><span class="panel-title">// scanners</span></div>
        <div class="panel-body">
          <dl class="dlist">
            <dt><Pill kind="accent">Semgrep</Pill></dt>
            <dd>Fast, pattern-based static analysis. Good for a quick first pass.</dd>
            <dt><Pill kind="accent">SonarQube</Pill></dt>
            <dd>Deeper security and code-quality analysis. Security findings cover both vulnerabilities and security hotspots.</dd>
            <dt>Run both</dt>
            <dd>Launches the two scanners in parallel and merges their results into one normalized list.</dd>
          </dl>
        </div>
      </div>
    </div>

    <div class="panel" style="margin-bottom: 20px">
      <div class="panel-head"><span class="panel-title">// findings</span></div>
      <div class="panel-body">
        <p class="doc-p">
          Every result is normalized into a common shape regardless of which tool produced it, then graded by severity and mapped to a risk category.
        </p>
        <dl class="dlist">
          <dt>Severity</dt>
          <dd>
            <Pill kind="high">HIGH</Pill> <Pill kind="med">MEDIUM</Pill> <Pill kind="low">LOW</Pill>.
            Toggle any combination to filter the table.
          </dd>
          <dt>OWASP Top 10 (2017)</dt>
          <dd>Findings are mapped through their CWE identifier; a curated rule table covers common SonarQube rules that ship without a CWE. Anything that can't be placed is shown as <span class="mono">UNMAPPED</span> rather than hidden, so coverage gaps stay visible.</dd>
        </dl>
      </div>
    </div>

    <div class="two-col" style="grid-template-columns: 1fr 1fr; margin-bottom: 20px">
      <div class="panel">
        <div class="panel-head"><span class="panel-title">// credits</span></div>
        <div class="panel-body">
          <p class="doc-p">A scan spends credits, so usage stays metered like a quota.</p>
          <dl class="dlist">
            <dt>Single scan</dt><dd>1 credit (Semgrep or SonarQube).</dd>
            <dt>Run both</dt><dd>2 credits.</dd>
            <dt>Staff</dt><dd>Unmetered. Staff accounts are never charged.</dd>
          </dl>
          <p class="doc-p dim">An administrator tops up balances and sets per-account limits.</p>
        </div>
      </div>

      <div class="panel">
        <div class="panel-head"><span class="panel-title">// exports</span></div>
        <div class="panel-body">
          <dl class="dlist">
            <dt>PDF report</dt><dd>A formatted report for a single scan, suitable for archiving or sharing.</dd>
            <dt>JSON</dt><dd>The complete findings of a scan, as raw data.</dd>
            <dt>CSV</dt><dd>The findings currently loaded in the cross-project view, for spreadsheets.</dd>
          </dl>
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head"><span class="panel-title">// for_developers</span></div>
      <div class="panel-body">
        <p class="doc-p">
          This interface is a thin client over a REST API served by the backend under <span class="mono">/api/</span>, authenticated by the same session as the rest of the site. Projects, scans, findings, exports and the administration endpoints are all reachable there.
        </p>
        <div class="doc-note">
          <Icon name="terminal" :size="14" />
          <span>The templated debug UI under <span class="mono">/debug/</span> mirrors the core flows and is kept as a fallback.</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.steps {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: var(--fs-sm);
  line-height: 1.6;
}
.steps li::marker {
  color: var(--accent);
  font-family: var(--font-mono);
}
.doc-p {
  font-size: var(--fs-sm);
  line-height: 1.7;
  margin: 0 0 14px;
}
.doc-p.dim {
  color: var(--fg-2);
  margin-bottom: 0;
}
.dlist dt {
  margin-top: 12px;
}
.dlist dt:first-child {
  margin-top: 0;
}
.doc-note {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  padding: 10px 12px;
  border: 1px dashed var(--line);
  border-radius: var(--r-2);
  background: var(--bg-inset);
  font-size: var(--fs-xs);
  color: var(--fg-2);
}
</style>
