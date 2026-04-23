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
        "title": "RAFX C360FX Integration + Results Pages",
        "status": "In Progress",
        "note": ""
    },
    {
        "title": "Email in C360FX Timelines + EmailMarketingFX Attribution",
        "status": "In Progress",
        "note": ""
    },
    {
        "title": "Brand Impressions Report Updates",
        "status": "Backlog",
        "note": ""
    },
    {
        "title": "Advertising Opt-Out",
        "status": "Under Review",
        "note": ""
    },
    {
        "title": "Ingest Nutshell Form IDs for Deduplication",
        "status": "Backlog",
        "note": ""
    },
    {
        "title": "OmniChannel Inbox: CallTrackerFX SMS Replies",
        "status": "Blocked",
        "note": "Blocked: CallTrackerFX SMS Replies dependency"
    },
    {
        "title": "Data Storytelling: ProspectorFX, App Notifications & PersonalizeFX",
        "status": "Backlog",
        "note": ""
    },
]

# ─────────────────────────────────────────────
# JIRA CONFIG
# ─────────────────────────────────────────────
JIRA_BASE_URL = "https://webfx.atlassian.net"
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
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
    sections = ""
    for epic in epics:
        issues_html = ""
        for i in epic["issues"]:
            sc = status_color(i["status"])
            pc = priority_color(i["priority"])
            est = f'<span class="est">{i["original_estimate_hrs"]}h</span>' if i["original_estimate_hrs"] else ""
            assignee = i["assignee"] if i["assignee"] != "Unassigned" else '<span class="unassigned">Unassigned</span>'
            issues_html += f"""
            <div class="issue-row">
              <a class="issue-key" href="{jira_base}/browse/{i['key']}" target="_blank">{i['key']}</a>
              <div class="issue-summary">{i['summary']}</div>
              <div class="issue-meta">
                <span class="badge" style="background:{sc}20;color:{sc};border:1px solid {sc}40">{i['status']}</span>
                <span class="badge priority-badge-sm" style="background:{pc}20;color:{pc};border:1px solid {pc}40">{i['priority']}</span>
                <span class="assignee">{assignee}</span>
                {est}
              </div>
            </div>"""

        epic_link = f'<a href="{jira_base}/browse/{epic["key"]}" target="_blank" class="epic-key">{epic["key"]}</a>' if epic.get("key") else ""
        sections += f"""
        <div class="epic-card">
          <div class="epic-header">
            <div class="epic-title">{epic["name"]}</div>
            {epic_link}
          </div>
          <div class="epic-issues">{issues_html}</div>
        </div>"""
    return sections


def generate_html(issues, epics, stats, generated_at):
    jira_base = JIRA_BASE_URL
    priorities_html = build_priorities_html()
    epics_html = build_epics_html(epics, jira_base)
    pct = stats["pct"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>MCPP Dashboard · April 2026</title>
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

  .header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 20px 32px; display: flex; align-items: center; justify-content: space-between; }}
  .header-left h1 {{ font-size: 20px; font-weight: 700; color: #fff; }}
  .header-left p {{ font-size: 12px; color: var(--muted); margin-top: 2px; }}
  .updated {{ font-size: 11px; color: var(--muted); }}

  .main {{ max-width: 1100px; margin: 0 auto; padding: 28px 24px; }}

  /* Stats row */
  .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
  .stat-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; }}
  .stat-label {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }}
  .stat-value {{ font-size: 28px; font-weight: 700; color: #fff; }}
  .stat-sub {{ font-size: 11px; color: var(--muted); margin-top: 2px; }}

  /* Progress bar */
  .progress-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; margin-bottom: 28px; }}
  .progress-top {{ display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 13px; color: var(--muted); }}
  .progress-bar {{ background: var(--border); border-radius: 99px; height: 8px; }}
  .progress-fill {{ background: linear-gradient(90deg, #6366f1, #22c55e); border-radius: 99px; height: 8px; transition: width .4s; }}

  /* Section titles */
  .section-title {{ font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-bottom: 14px; }}

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
  .epic-header {{ display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--border); background: #1e2130; }}
  .epic-title {{ font-size: 14px; font-weight: 600; color: #fff; }}
  .epic-key {{ font-size: 11px; color: var(--muted); }}
  .epic-issues {{ padding: 0 18px; }}

  .issue-row {{ display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border); flex-wrap: wrap; }}
  .issue-row:last-child {{ border-bottom: none; }}
  .issue-key {{ font-size: 12px; font-weight: 600; min-width: 90px; color: var(--accent); }}
  .issue-summary {{ flex: 1; font-size: 13px; color: var(--text); min-width: 200px; }}
  .issue-meta {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
  .badge {{ font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 99px; white-space: nowrap; }}
  .assignee {{ font-size: 11px; color: var(--muted); }}
  .unassigned {{ color: #4b5563; }}
  .est {{ font-size: 11px; color: var(--muted); background: var(--border); padding: 2px 7px; border-radius: 4px; }}

  @media (max-width: 640px) {{
    .stats {{ grid-template-columns: repeat(2, 1fr); }}
    .header {{ flex-direction: column; align-items: flex-start; gap: 8px; }}
    .issue-summary {{ min-width: 100%; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>MCPP Sprint Dashboard</h1>
    <p>April 2026 · PR Panthers</p>
  </div>
  <div class="updated">Auto-refreshed: {generated_at}</div>
</div>

<div class="main">

  <!-- Stats -->
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

  <!-- Progress -->
  <div class="progress-wrap">
    <div class="progress-top">
      <span>Sprint Completion</span>
      <span style="color:#fff;font-weight:600">{pct}%</span>
    </div>
    <div class="progress-bar">
      <div class="progress-fill" style="width:{pct}%"></div>
    </div>
  </div>

  <!-- Priorities -->
  <div class="section-title">Current Priorities</div>
  <div class="priorities-card">
    {priorities_html}
  </div>

  <!-- Epics + Issues -->
  <div class="section-title">Sprint Issues by Epic</div>
  {epics_html}

</div>
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
