"""
MCPP Dashboard Generator
Fetches April 2026 sprint data from Jira and generates index.html

TO UPDATE PRIORITIES: Edit the PRIORITIES list below.
Each entry has: title, status, and optional note.
Status options: "In Progress", "Backlog", "Blocked", "Under Review", "Complete"
"""

import os
import json
import requests
from base64 import b64encode
from datetime import datetime, timezone

# ─────────────────────────────────────────────
# MANUALLY MAINTAINED PRIORITIES
# Edit this section whenever priorities change.
# ─────────────────────────────────────────────
PRIORITIES = [
    {
        "title": "Advertising Opt-Out",
        "status": "Done!",
        "note": ""
    },
    {
        "title": "RAFX C360FX Integration + Results Pages",
        "status": "Under Review",
        "note": ""
    },
    {
        "title": "Brand Impressions Report Updates",
        "status": "In Progress",
        "note": ""
    },
    {
        "title": "Ingest Nutshell Form IDs for Deduplication",
        "status": "Under Review",
        "note": ""
    },
    {
        "title": "DealerFX: Pipeline Assignment for Child Sites",
        "status": "Under Review",
        "note": ""
    },
    {
        "title": "React 19 Wrap-Up",
        "status": "Under Review",
        "note": ""
    },
    {
        "title": "Email in C360FX Timelines + EmailMarketingFX Attribution",
        "status": "In Progress",
        "note": ""
    },
]

# ─────────────────────────────────────────────
# JIRA CONFIG
# ─────────────────────────────────────────────
JIRA_BASE_URL = "https://webfx.atlassian.net"
JIRA_EMAIL = os.environ.get("JIRA_EMAIL", "").strip()
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "").strip()

if not JIRA_EMAIL or not JIRA_API_TOKEN:
    raise ValueError(f"Missing credentials! JIRA_EMAIL={'SET' if JIRA_EMAIL else 'EMPTY'}, JIRA_API_TOKEN={'SET' if JIRA_API_TOKEN else 'EMPTY'}")
JIRA_CLOUD_ID = "a7f46cbf-0128-46ba-9a34-eb72e893d05e"

AUTH = b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {AUTH}",
    "Accept": "application/json",
}

SPRINT_LABEL = "April2026"
JQL = f'project = MCPP AND labels = "{SPRINT_LABEL}" AND status != "Refinement" ORDER BY priority ASC'
FIELDS = "summary,status,priority,assignee,parent,timeoriginalestimate,issuetype,labels"


def fetch_jira_issues():
    """Fetch all MCPP sprint issues from Jira REST API."""
    issues = []
    start_at = 0
    max_results = 100

    # Debug: print auth info (masked) and JQL
    print(f"  JQL: {JQL}")
    print(f"  Auth email set: {bool(JIRA_EMAIL)}, token set: {bool(JIRA_API_TOKEN)}")

    while True:
        url = f"{JIRA_BASE_URL}/rest/api/3/search/jql"
        params = {
            "jql": JQL,
            "fields": FIELDS,
            "startAt": start_at,
            "maxResults": max_results,
        }
        resp = requests.get(url, headers=HEADERS, params=params)
        print(f"  HTTP {resp.status_code}")
        if not resp.ok:
            print(f"  Jira error: {resp.text}")
        resp.raise_for_status()
        data = resp.json()
        print(f"  Response keys: {list(data.keys())}")
        print(f"  Raw response preview: {str(data)[:500]}")

        batch = data.get("issues", [])
        issues.extend(batch)

        print(f"  Page fetched: {len(batch)} issues")
        if data.get("isLast", True) or len(batch) < max_results:
            break
        start_at += max_results

    return issues


def parse_issues(raw_issues):
    """Normalize Jira issue fields into a flat list of dicts."""
    parsed = []
    for issue in raw_issues:
        f = issue["fields"]
        parent = f.get("parent") or {}
        parent_fields = parent.get("fields", {})
        parent_issuetype = parent_fields.get("issuetype", {}).get("name", "")
        parent_summary = parent_fields.get("summary", "")

        parsed.append({
            "key": issue["key"],
            "summary": f.get("summary", ""),
            "status": f.get("status", {}).get("name", ""),
            "priority": f.get("priority", {}).get("name", ""),
            "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
            "issuetype": f.get("issuetype", {}).get("name", ""),
            "parent_key": parent.get("key", ""),
            "parent_summary": parent_summary,
            "parent_issuetype": parent_issuetype,
            "original_estimate_hrs": round(f["timeoriginalestimate"] / 3600, 1) if f.get("timeoriginalestimate") else None,
            "labels": f.get("labels", []),
        })
    return parsed


def group_by_epic(issues):
    """Group issues by their epic parent."""
    epics = {}
    no_epic = []

    for issue in issues:
        if issue["parent_issuetype"] == "Epic":
            epic_name = issue["parent_summary"]
            epic_key = issue["parent_key"]
            if epic_key not in epics:
                epics[epic_key] = {"name": epic_name, "key": epic_key, "issues": []}
            epics[epic_key]["issues"].append(issue)
        else:
            no_epic.append(issue)

    result = list(epics.values())
    if no_epic:
        result.append({"name": "No Epic", "key": "", "issues": no_epic})
    return result


def status_color(status):
    colors = {
        "Done": "#22c55e",
        "In Progress": "#3b82f6",
        "To Do": "#94a3b8",
        "Backlog": "#94a3b8",
        "Under Review": "#f59e0b",
        "Blocked": "#ef4444",
        "In Review": "#8b5cf6",
    }
    return colors.get(status, "#94a3b8")


def priority_color(priority):
    colors = {
        "Highest": "#ef4444",
        "High": "#f97316",
        "Medium": "#f59e0b",
        "Low": "#22c55e",
        "Lowest": "#94a3b8",
    }
    return colors.get(priority, "#94a3b8")


def priority_status_color(status):
    colors = {
        "In Progress": "#3b82f6",
        "Backlog": "#94a3b8",
        "Blocked": "#ef4444",
        "Under Review": "#f59e0b",
        "Complete": "#22c55e",
    }
    return colors.get(status, "#94a3b8")


def compute_stats(issues):
    total = len(issues)
    done = sum(1 for i in issues if i["status"] == "Done")
    in_progress = sum(1 for i in issues if i["status"] == "In Progress")
    todo = total - done - in_progress
    pct = round((done / total) * 100) if total else 0
    return {"total": total, "done": done, "in_progress": in_progress, "todo": todo, "pct": pct}


def build_priorities_html():
    rows = ""
    for idx, p in enumerate(PRIORITIES, 1):
        color = priority_status_color(p["status"])
        note_html = f'<div class="priority-note">{p["note"]}</div>' if p.get("note") else ""
        rows += f"""
        <div class="priority-row">
          <div class="priority-num">{idx}</div>
          <div class="priority-content">
            <div class="priority-title">{p["title"]}</div>
            {note_html}
          </div>
          <div class="priority-badge" style="background:{color}20;color:{color};border:1px solid {color}40">{p["status"]}</div>
        </div>"""
    return rows


def build_epics_html(epics, jira_base):
    # Kept for compatibility but rendering is now done in JS
    return ""


def generate_html(issues, epics, stats, generated_at):
    import json as _json
    jira_base = JIRA_BASE_URL
    priorities_html = build_priorities_html()
    pct = stats["pct"]

    # Serialize epics data for JS
    epics_json = _json.dumps([
        {
            "name": e["name"],
            "key": e.get("key", ""),
            "issues": [
                {
                    "key": i["key"],
                    "summary": i["summary"],
                    "status": i["status"],
                    "priority": i["priority"],
                    "assignee": i["assignee"],
                    "est": i["original_estimate_hrs"],
                }
                for i in e["issues"]
            ]
        }
        for e in epics
    ], ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>MCPP Dashboard \u00b7 April 2026</title>
<style>
  :root {{
    --bg: #0f1117;
    --surface: #1a1d27;
    --border: #2a2d3a;
    --text: #e2e8f0;
    --muted: #64748b;
    --accent: #6366f1;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; line-height: 1.6; }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  .header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 20px 32px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
  .header-left h1 {{ font-size: 20px; font-weight: 700; color: #fff; }}
  .header-left p {{ font-size: 12px; color: var(--muted); margin-top: 2px; }}
  .updated {{ font-size: 11px; color: var(--muted); }}

  .main {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px; }}

  /* Stats */
  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
  .stat-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; }}
  .stat-label {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }}
  .stat-value {{ font-size: 28px; font-weight: 700; color: #fff; }}

  /* Progress */
  .progress-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; margin-bottom: 28px; }}
  .progress-top {{ display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 13px; color: var(--muted); }}
  .progress-bar {{ background: var(--border); border-radius: 99px; height: 8px; }}
  .progress-fill {{ background: linear-gradient(90deg, #6366f1, #22c55e); border-radius: 99px; height: 8px; transition: width .4s; }}

  /* Section titles */
  .section-title {{ font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-bottom: 14px; }}

  /* Filters */
  .filters {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; margin-bottom: 20px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
  .filter-label {{ font-size: 12px; color: var(--muted); white-space: nowrap; }}
  select {{ background: #0f1117; color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 5px 10px; font-size: 12px; cursor: pointer; }}
  select:focus {{ outline: none; border-color: var(--accent); }}
  .toggle-btn {{ display: flex; align-items: center; gap: 8px; background: #0f1117; border: 1px solid var(--border); border-radius: 6px; padding: 5px 12px; font-size: 12px; color: var(--muted); cursor: pointer; white-space: nowrap; transition: border-color .2s; }}
  .toggle-btn:hover {{ border-color: var(--accent); color: var(--text); }}
  .toggle-btn.active {{ border-color: var(--accent); color: var(--accent); }}
  .toggle-dot {{ width: 8px; height: 8px; border-radius: 50%; background: var(--border); transition: background .2s; }}
  .toggle-btn.active .toggle-dot {{ background: var(--accent); }}
  .filter-count {{ margin-left: auto; font-size: 11px; color: var(--muted); }}

  /* Priorities */
  .priorities-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin-bottom: 28px; }}
  .priority-row {{ display: flex; align-items: flex-start; gap: 14px; padding: 12px 0; border-bottom: 1px solid var(--border); }}
  .priority-row:last-child {{ border-bottom: none; padding-bottom: 0; }}
  .priority-row:first-child {{ padding-top: 0; }}
  .priority-num {{ font-size: 12px; font-weight: 700; color: var(--muted); min-width: 20px; padding-top: 2px; }}
  .priority-content {{ flex: 1; }}
  .priority-title {{ font-size: 14px; color: var(--text); }}
  .priority-note {{ font-size: 12px; color: #ef4444; margin-top: 3px; }}
  .priority-badge {{ font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 99px; white-space: nowrap; }}

  /* Epics */
  .epic-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; margin-bottom: 16px; overflow: hidden; }}
  .epic-card.hidden {{ display: none; }}
  .epic-header {{ display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: #1e2130; }}
  .epic-title {{ font-size: 14px; font-weight: 600; color: #fff; }}
  .epic-key {{ font-size: 11px; color: var(--muted); }}
  .epic-issues {{ padding: 0 18px; }}
  .epic-empty {{ padding: 14px 0; font-size: 12px; color: var(--muted); text-align: center; display: none; }}

  .issue-row {{ display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border); flex-wrap: wrap; }}
  .issue-row:last-child {{ border-bottom: none; }}
  .issue-row.hidden {{ display: none; }}
  .issue-key {{ font-size: 12px; font-weight: 600; min-width: 90px; color: var(--accent); }}
  .issue-summary {{ flex: 1; font-size: 13px; color: var(--text); min-width: 200px; }}
  .issue-meta {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
  .badge {{ font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 99px; white-space: nowrap; }}
  .assignee {{ font-size: 11px; color: var(--muted); }}
  .est {{ font-size: 11px; color: var(--muted); background: var(--border); padding: 2px 7px; border-radius: 4px; }}
  .no-results {{ text-align: center; padding: 40px; color: var(--muted); font-size: 13px; display: none; }}

  @media (max-width: 640px) {{
    .stats {{ grid-template-columns: repeat(2, 1fr); }}
    .header {{ flex-direction: column; align-items: flex-start; }}
    .issue-summary {{ min-width: 100%; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>MCPP Sprint Dashboard</h1>
    <p>April 2026 \u00b7 PR Panthers</p>
  </div>
  <div class="updated">Auto-refreshed: {generated_at}</div>
</div>

<div class="main">

  <div class="stats">
    <div class="stat-card">
      <div class="stat-label">Total Issues</div>
      <div class="stat-value">{stats["total"]}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Done</div>
      <div class="stat-value" style="color:#22c55e">{stats["done"]}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">In Progress</div>
      <div class="stat-value" style="color:#3b82f6">{stats["in_progress"]}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">To Do / Backlog</div>
      <div class="stat-value" style="color:#94a3b8">{stats["todo"]}</div>
    </div>
  </div>

  <div class="progress-wrap">
    <div class="progress-top">
      <span>Sprint Completion</span>
      <span style="color:#fff;font-weight:600">{pct}%</span>
    </div>
    <div class="progress-bar">
      <div class="progress-fill" style="width:{pct}%"></div>
    </div>
  </div>

  <div class="section-title">Current Priorities</div>
  <div class="priorities-card">{priorities_html}</div>

  <div class="section-title">Sprint Issues by Epic</div>

  <div class="filters">
    <span class="filter-label">Filter:</span>
    <select id="statusFilter">
      <option value="">All Statuses</option>
    </select>
    <select id="assigneeFilter">
      <option value="">All Assignees</option>
    </select>
    <button class="toggle-btn" id="hideCompletedBtn" onclick="toggleCompleted()">
      <span class="toggle-dot"></span>
      Hide Completed
    </button>
    <span class="filter-count" id="filterCount"></span>
  </div>

  <div id="epicsContainer"></div>
  <div class="no-results" id="noResults">No issues match the current filters.</div>

</div>

<script>
const JIRA_BASE = "{jira_base}";
const EPICS = {epics_json};

const STATUS_COLORS = {{
  "Done": "#22c55e", "In Progress": "#3b82f6", "To Do": "#94a3b8",
  "Backlog": "#94a3b8", "Under Review": "#f59e0b", "Blocked": "#ef4444",
  "In Review": "#8b5cf6"
}};
const PRIORITY_COLORS = {{
  "Highest": "#ef4444", "High": "#f97316", "Medium": "#f59e0b",
  "Low": "#22c55e", "Lowest": "#94a3b8"
}};

let hideCompleted = false;

function sc(s) {{ return STATUS_COLORS[s] || "#94a3b8"; }}
function pc(p) {{ return PRIORITY_COLORS[p] || "#94a3b8"; }}

function populateFilters() {{
  const statuses = new Set();
  const assignees = new Set();
  EPICS.forEach(e => e.issues.forEach(i => {{
    statuses.add(i.status);
    assignees.add(i.assignee);
  }}));

  const sf = document.getElementById("statusFilter");
  const af = document.getElementById("assigneeFilter");

  [...statuses].sort().forEach(s => {{
    const o = document.createElement("option");
    o.value = s; o.textContent = s;
    sf.appendChild(o);
  }});
  [...assignees].sort().forEach(a => {{
    const o = document.createElement("option");
    o.value = a; o.textContent = a || "Unassigned";
    af.appendChild(o);
  }});
}}

function renderEpics() {{
  const statusVal = document.getElementById("statusFilter").value;
  const assigneeVal = document.getElementById("assigneeFilter").value;
  const container = document.getElementById("epicsContainer");
  container.innerHTML = "";
  let totalVisible = 0;

  EPICS.forEach(epic => {{
    const filteredIssues = epic.issues.filter(i => {{
      if (hideCompleted && i.status === "Done") return false;
      if (statusVal && i.status !== statusVal) return false;
      if (assigneeVal && i.assignee !== assigneeVal) return false;
      return true;
    }});

    const card = document.createElement("div");
    card.className = "epic-card";

    const epicKeyHtml = epic.key
      ? `<a href="${{JIRA_BASE}}/browse/${{epic.key}}" target="_blank" class="epic-key">${{epic.key}}</a>`
      : "";

    let issuesHtml = filteredIssues.map(i => {{
      const sColor = sc(i.status);
      const pColor = pc(i.priority);
      const estHtml = i.est ? `<span class="est">${{i.est}}h</span>` : "";
      const assigneeHtml = i.assignee && i.assignee !== "Unassigned"
        ? `<span class="assignee">${{i.assignee}}</span>`
        : `<span class="assignee" style="color:#4b5563">Unassigned</span>`;
      return `
        <div class="issue-row">
          <a class="issue-key" href="${{JIRA_BASE}}/browse/${{i.key}}" target="_blank">${{i.key}}</a>
          <div class="issue-summary">${{i.summary}}</div>
          <div class="issue-meta">
            <span class="badge" style="background:${{sColor}}20;color:${{sColor}};border:1px solid ${{sColor}}40">${{i.status}}</span>
            <span class="badge" style="background:${{pColor}}20;color:${{pColor}};border:1px solid ${{pColor}}40">${{i.priority}}</span>
            ${{assigneeHtml}}
            ${{estHtml}}
          </div>
        </div>`;
    }}).join("");

    if (filteredIssues.length === 0) {{
      issuesHtml = `<div class="epic-empty" style="display:block">No matching issues</div>`;
    }}

    card.innerHTML = `
      <div class="epic-header">
        <div class="epic-title">${{epic.name}}</div>
        ${{epicKeyHtml}}
      </div>
      <div class="epic-issues">${{issuesHtml}}</div>`;

    container.appendChild(card);
    totalVisible += filteredIssues.length;
  }});

  document.getElementById("filterCount").textContent =
    `${{totalVisible}} issue${{totalVisible !== 1 ? "s" : ""}} shown`;
  document.getElementById("noResults").style.display = totalVisible === 0 ? "block" : "none";
}}

function toggleCompleted() {{
  hideCompleted = !hideCompleted;
  const btn = document.getElementById("hideCompletedBtn");
  btn.classList.toggle("active", hideCompleted);
  renderEpics();
}}

document.getElementById("statusFilter").addEventListener("change", renderEpics);
document.getElementById("assigneeFilter").addEventListener("change", renderEpics);

populateFilters();
renderEpics();
</script>
</body>
</html>"""
    return html


def main():
    print("Fetching issues from Jira...")
    raw = fetch_jira_issues()
    print(f"  Found {len(raw)} issues")

    issues = parse_issues(raw)

    # Debug: show sample of what we parsed
    if issues:
        sample = issues[0]
        print(f"  Sample issue: key={sample['key']} status={sample['status']} parent_issuetype={sample['parent_issuetype']} parent_summary={sample['parent_summary']!r}")
    else:
        print("  WARNING: No issues parsed from raw data!")
        if raw:
            print(f"  Raw sample keys: {list(raw[0].keys())}")
            print(f"  Raw sample fields keys: {list(raw[0].get('fields', {}).keys())}")

    epics = group_by_epic(issues)
    stats = compute_stats(issues)

    generated_at = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    print(f"  Grouped into {len(epics)} epics")
    for e in epics[:3]:
        print(f"    Epic: {e['name']!r} ({len(e['issues'])} issues)")
    print(f"  Stats: {stats}")

    print("Generating index.html...")
    html = generate_html(issues, epics, stats, generated_at)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("Done! index.html written.")


if __name__ == "__main__":
    main()
