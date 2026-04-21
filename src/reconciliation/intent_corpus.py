"""
Curated corpus of Murphy's *internal* request patterns.

Murphy is both the automation that generates requests and the production
that fulfils them.  This corpus enumerates the request shapes Murphy's
own modules — workflow generators, multi-agent coordinators, room LLM
brains, integration adapters, dashboards — actually produce, drawn from:

  * Reconciliation calibration scenarios (rounds 1–6)
  * README "Describe → Execute" examples
  * Workflow generator prompt patterns
  * Multi-agent coordinator request shapes
  * Integration adapter call signatures
  * Dashboard / monitoring trigger language

Curation rules (CLAUDE.md "Simplicity First"):
  * Realistic phrasing — every entry is something a human or upstream
    Murphy module would plausibly emit.
  * Balanced — every active :class:`DeliverableType` has ≥ 6 examples.
  * No synthetic templates — each line is a distinct phrasing, not a
    fill-in-the-blank.
  * Stable order — keep examples grouped by class so diffs stay small.

Design label: RECON-INTENT-002 / corpus
"""

from __future__ import annotations

from typing import List, Tuple

from .models import DeliverableType


# Format: (request_text, deliverable_type)
INTERNAL_REQUEST_CORPUS: List[Tuple[str, DeliverableType]] = [
    # ---------------- CODE ----------------
    ("Write a Python function to parse a CSV file and return a list of dicts", DeliverableType.CODE),
    ("Implement the rate limiter class with token bucket semantics", DeliverableType.CODE),
    ("Add a method to UserService that looks up users by email", DeliverableType.CODE),
    ("Refactor the retry logic into a decorator function", DeliverableType.CODE),
    ("Create a Go HTTP handler function that returns the build version", DeliverableType.CODE),
    ("Write a SQL query helper function that uses bind parameters", DeliverableType.CODE),
    ("Implement the YAML loader function using SafeLoader", DeliverableType.CODE),
    ("Add a wrapper function around subprocess.run that disables shell mode", DeliverableType.CODE),
    ("Build a dataclass for the deployment request payload", DeliverableType.CODE),
    ("Write a function that validates the API key against the secrets manager", DeliverableType.CODE),
    ("Implement a Python class for connection pooling", DeliverableType.CODE),
    ("Write a helper function to compute SHA-256 of a file", DeliverableType.CODE),
    ("Add a Python method that serializes the order to a dict", DeliverableType.CODE),
    ("Implement a Rust function for parsing the binary header", DeliverableType.CODE),
    ("Write a TypeScript class implementing the cache eviction policy", DeliverableType.CODE),

    # ---------------- CONFIG_FILE ----------------
    ("Write the staging environment config file with database and redis settings", DeliverableType.CONFIG_FILE),
    ("Create the production .env config file referencing vault for secrets", DeliverableType.CONFIG_FILE),
    ("Generate the YAML config file for the new payments service", DeliverableType.CONFIG_FILE),
    ("Add a feature flag config block for the experimental router", DeliverableType.CONFIG_FILE),
    ("Write the application.conf config file for the integration tier", DeliverableType.CONFIG_FILE),
    ("Set up the monitoring config file with prometheus scrape targets", DeliverableType.CONFIG_FILE),
    ("Create a settings config file mapping each environment to its hostnames", DeliverableType.CONFIG_FILE),
    ("Generate the docker-compose config file for the local dev stack", DeliverableType.CONFIG_FILE),
    ("Write the logging config file with structured JSON formatters", DeliverableType.CONFIG_FILE),
    ("Create the kafka topic config file with retention and partition counts", DeliverableType.CONFIG_FILE),
    ("Write the Helm values config file for the staging chart", DeliverableType.CONFIG_FILE),
    ("Set up the nginx config file with TLS and gzip enabled", DeliverableType.CONFIG_FILE),

    # ---------------- SHELL_SCRIPT ----------------
    ("Write a deploy shell script that pushes the container and tags the release", DeliverableType.SHELL_SCRIPT),
    ("Create a bash script that backs up the database and uploads to S3", DeliverableType.SHELL_SCRIPT),
    ("Write a health-check shell script that polls the API every 30 seconds", DeliverableType.SHELL_SCRIPT),
    ("Generate the bootstrap shell script for new developer machines", DeliverableType.SHELL_SCRIPT),
    ("Write a rollback shell script that reverts to the previous tag", DeliverableType.SHELL_SCRIPT),
    ("Create a cleanup shell script that removes temp files older than 30 days", DeliverableType.SHELL_SCRIPT),
    ("Write a wrapper bash script that runs the test suite with strict mode", DeliverableType.SHELL_SCRIPT),
    ("Write a bash script that tails the logs and grep for errors", DeliverableType.SHELL_SCRIPT),
    ("Create a shell script that rotates the log files weekly", DeliverableType.SHELL_SCRIPT),
    ("Write an installer shell script that pins the toolchain version", DeliverableType.SHELL_SCRIPT),
    ("Create a CI helper bash script that runs lint and tests in parallel", DeliverableType.SHELL_SCRIPT),
    ("Write a shell script that drains the worker queue before shutdown", DeliverableType.SHELL_SCRIPT),

    # ---------------- DOCUMENT ----------------
    ("Write the README document for the reconciliation subsystem", DeliverableType.DOCUMENT),
    ("Document the API endpoints with example requests and responses", DeliverableType.DOCUMENT),
    ("Draft a runbook document for the on-call rotation covering pager triage", DeliverableType.DOCUMENT),
    ("Write a migration guide document for upgrading from v1 to v2", DeliverableType.DOCUMENT),
    ("Create the architecture overview document explaining the major subsystems", DeliverableType.DOCUMENT),
    ("Write release notes document covering the new permutation calibration features", DeliverableType.DOCUMENT),
    ("Author the security policy document for the incident-response process", DeliverableType.DOCUMENT),
    ("Write the troubleshooting guide document for common deployment failures", DeliverableType.DOCUMENT),
    ("Document the data model with field-by-field descriptions", DeliverableType.DOCUMENT),
    ("Write a developer onboarding document covering the local dev setup", DeliverableType.DOCUMENT),
    ("Author the design doc for the new caching subsystem", DeliverableType.DOCUMENT),
    ("Write the user-facing FAQ document for the new dashboard", DeliverableType.DOCUMENT),
    ("Document the upgrade procedure with rollback steps", DeliverableType.DOCUMENT),

    # ---------------- PLAN ----------------
    ("Plan the rollout of the new authentication service across regions", DeliverableType.PLAN),
    ("Outline the migration plan for moving the payments database to Aurora", DeliverableType.PLAN),
    ("Build a step-by-step checklist for launching the new dashboard to beta customers", DeliverableType.PLAN),
    ("Plan the integration steps for the third-party SSO provider", DeliverableType.PLAN),
    ("Create a phased rollout plan for the new caching layer", DeliverableType.PLAN),
    ("Outline the steps to onboard a new tenant to the platform", DeliverableType.PLAN),
    ("Sketch a quarterly roadmap plan focused on observability", DeliverableType.PLAN),
    ("Build a step-by-step plan for the data migration cutover", DeliverableType.PLAN),
    ("Plan the deprecation steps for the legacy v1 API", DeliverableType.PLAN),
    ("Outline a recovery plan with steps for the database failover drill", DeliverableType.PLAN),
    ("Plan the steps to decompose the monolith into services", DeliverableType.PLAN),
    ("Build a remediation plan with prioritized steps for the audit findings", DeliverableType.PLAN),

    # ---------------- JSON_PAYLOAD ----------------
    ("Build the JSON response payload for the user profile endpoint", DeliverableType.JSON_PAYLOAD),
    ("Generate the JSON request body for the webhook notification", DeliverableType.JSON_PAYLOAD),
    ("Construct the JSON payload representing the order status update", DeliverableType.JSON_PAYLOAD),
    ("Produce the JSON envelope payload for the analytics event stream", DeliverableType.JSON_PAYLOAD),
    ("Build the JSON response envelope with status, data, and pagination keys", DeliverableType.JSON_PAYLOAD),
    ("Generate the JSON manifest payload describing each artifact in the release", DeliverableType.JSON_PAYLOAD),
    ("Construct the JSON request payload for the upstream pricing API", DeliverableType.JSON_PAYLOAD),
    ("Build a JSON payload for the GraphQL mutation response", DeliverableType.JSON_PAYLOAD),
    ("Produce the JSON payload that the audit log consumer expects", DeliverableType.JSON_PAYLOAD),
    ("Generate the JSON response payload listing all active feature flags", DeliverableType.JSON_PAYLOAD),
    ("Build the JSON payload for the SCIM user provisioning request", DeliverableType.JSON_PAYLOAD),
    ("Construct the JSON payload representing the cart at checkout", DeliverableType.JSON_PAYLOAD),

    # ---------------- MAILBOX_PROVISIONING ----------------
    ("Provision team mailboxes for the new sales hires", DeliverableType.MAILBOX_PROVISIONING),
    ("Create the alpha-team mailbox with forwarding rules", DeliverableType.MAILBOX_PROVISIONING),
    ("Set up email mailboxes for the engineering on-call rotation", DeliverableType.MAILBOX_PROVISIONING),
    ("Provision an integration mailbox for the partner exchange", DeliverableType.MAILBOX_PROVISIONING),
    ("Create shared mailboxes for each customer success squad", DeliverableType.MAILBOX_PROVISIONING),
    ("Provision new mailboxes for the contractors starting Monday", DeliverableType.MAILBOX_PROVISIONING),
    ("Create mailboxes for the entire marketing department", DeliverableType.MAILBOX_PROVISIONING),
    ("Provision mailboxes with the standard alias and forwarding setup", DeliverableType.MAILBOX_PROVISIONING),
    ("Set up mailboxes for the executive assistants with delegated access", DeliverableType.MAILBOX_PROVISIONING),
    ("Provision a noreply mailbox for the transactional email pipeline", DeliverableType.MAILBOX_PROVISIONING),
    ("Create a shared mailbox for the legal review queue", DeliverableType.MAILBOX_PROVISIONING),
    ("Provision department mailboxes for the new regional office", DeliverableType.MAILBOX_PROVISIONING),

    # ---------------- DEPLOYMENT_RESULT ----------------
    ("Deploy the payments service to production", DeliverableType.DEPLOYMENT_RESULT),
    ("Roll out the new auth service deployment to the staging environment", DeliverableType.DEPLOYMENT_RESULT),
    ("Push the latest container image to the canary production deployment", DeliverableType.DEPLOYMENT_RESULT),
    ("Deploy the dashboard frontend to production behind the feature flag", DeliverableType.DEPLOYMENT_RESULT),
    ("Roll out the database schema migration deployment to all shards", DeliverableType.DEPLOYMENT_RESULT),
    ("Deploy the webhook receiver to the integration cluster", DeliverableType.DEPLOYMENT_RESULT),
    ("Promote the release candidate deployment from staging to production", DeliverableType.DEPLOYMENT_RESULT),
    ("Deploy the patched container to all production regions", DeliverableType.DEPLOYMENT_RESULT),
    ("Roll out the v2 deployment of the recommender service", DeliverableType.DEPLOYMENT_RESULT),
    ("Deploy the new ingress controller across all production clusters", DeliverableType.DEPLOYMENT_RESULT),
    ("Deploy the hotfix to production immediately", DeliverableType.DEPLOYMENT_RESULT),
    ("Roll out the deployment of the experimental ranker to 5 percent", DeliverableType.DEPLOYMENT_RESULT),

    # ---------------- DASHBOARD ----------------
    ("Build a dashboard showing weekly active users by region", DeliverableType.DASHBOARD),
    ("Create a monitoring dashboard with latency and error-rate panels", DeliverableType.DASHBOARD),
    ("Construct a sales dashboard with pipeline and conversion metric panels", DeliverableType.DASHBOARD),
    ("Build the SRE dashboard with SLO burn-rate panels", DeliverableType.DASHBOARD),
    ("Create a finance dashboard with panels tracking monthly revenue and churn", DeliverableType.DASHBOARD),
    ("Build an executive dashboard summarizing platform health metrics", DeliverableType.DASHBOARD),
    ("Construct a dashboard with panels for queue depth and consumer lag", DeliverableType.DASHBOARD),
    ("Build a dashboard showing per-tenant API usage", DeliverableType.DASHBOARD),
    ("Create a customer-success dashboard with onboarding funnel panels", DeliverableType.DASHBOARD),
    ("Build a dashboard visualizing storage growth across clusters", DeliverableType.DASHBOARD),
    ("Construct a security dashboard with panels for failed login attempts", DeliverableType.DASHBOARD),
    ("Build a marketing dashboard with panels for campaign attribution", DeliverableType.DASHBOARD),

    # ---------------- WORKFLOW ----------------
    ("Build an automated workflow that pulls leads from CRM and enqueues outreach", DeliverableType.WORKFLOW),
    ("Create an automated workflow for monthly invoice generation", DeliverableType.WORKFLOW),
    ("Wire up an automated workflow that watches the bug tracker and pings on-call", DeliverableType.WORKFLOW),
    ("Build an automated workflow that runs nightly data quality checks", DeliverableType.WORKFLOW),
    ("Create an automated workflow that triages incoming support tickets", DeliverableType.WORKFLOW),
    ("Build the onboarding automated workflow for new customer accounts", DeliverableType.WORKFLOW),
    ("Wire up an automated workflow that snapshots metrics and posts to Slack", DeliverableType.WORKFLOW),
    ("Build an automated workflow that scrapes prices and updates the catalog", DeliverableType.WORKFLOW),
    ("Create an automated workflow that escalates stale PRs to reviewers", DeliverableType.WORKFLOW),
    ("Build an automated workflow that syncs HRIS data into the directory", DeliverableType.WORKFLOW),
    ("Wire up an automated workflow that monitors costs and alerts finance", DeliverableType.WORKFLOW),
    ("Build an automated workflow that processes the daily reconciliation batch", DeliverableType.WORKFLOW),

    # ---------------- GENERIC_TEXT ----------------
    ("Summarize the meeting notes from yesterday in a short paragraph", DeliverableType.GENERIC_TEXT),
    ("Write a friendly short reply to the customer email", DeliverableType.GENERIC_TEXT),
    ("Compose a short status update message for the team channel", DeliverableType.GENERIC_TEXT),
    ("Draft a one-line tagline for the new feature", DeliverableType.GENERIC_TEXT),
    ("Write a short bio paragraph for the team page", DeliverableType.GENERIC_TEXT),
    ("Compose a short refusal message explaining the request cannot be fulfilled", DeliverableType.GENERIC_TEXT),
    ("Write a short thank-you message for the partner team", DeliverableType.GENERIC_TEXT),
    ("Draft a short tweet announcing the release", DeliverableType.GENERIC_TEXT),
    ("Compose a short paragraph summary of the quarterly results", DeliverableType.GENERIC_TEXT),
    ("Write a short blurb describing the team mission", DeliverableType.GENERIC_TEXT),
    ("Draft a short message acknowledging the incident", DeliverableType.GENERIC_TEXT),
    ("Compose a short note thanking the on-call engineer", DeliverableType.GENERIC_TEXT),
]


def get_corpus() -> List[Tuple[str, DeliverableType]]:
    """Return a copy of the curated corpus.

    Returned as a fresh list so callers can extend it without mutating
    the module-level constant.
    """
    return list(INTERNAL_REQUEST_CORPUS)


__all__ = ["INTERNAL_REQUEST_CORPUS", "get_corpus"]
