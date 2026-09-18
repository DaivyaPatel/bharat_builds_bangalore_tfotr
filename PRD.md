# DriftLens — Product Requirements Document

**Version:** 1.0
**Status:** Locked for the hackathon build. Changes to Section 5 (Contracts) require all three of us to agree, because everything parallel depends on them.
**Supersedes:** `config-drift-implementation-plan.md` (that document describes the snapshot-agent architecture, which is cancelled).

---

## 1. Summary

DriftLens is an agentless diagnostic tool that detects **runtime configuration drift** between deployed AWS environments, attributes each divergence to the API call and human principal that caused it, and scores it by severity.

It answers two questions that nothing in the existing tool landscape answers together:

1. *"Staging and prod are supposed to be identical — where have they actually diverged?"*
2. *"Prod broke at 14:00. What changed in its effective config since the last known-good deploy, and who changed it?"*

---

## 2. Problem

Docker solves artifact drift: same image, same dependencies, same OS libraries everywhere. Terraform and AWS Config solve infrastructure drift: declared resources versus actual resources. Neither solves what gets **injected into the running workload per environment** — Lambda environment variables, ECS task definition environment blocks, SSM Parameter Store values, AppConfig feature flag states, secret versions.

That layer is where "works in staging, breaks in prod" actually lives, and it is invisible to every category of tool above. The specific failure mode we target:

> During an incident, someone changes a value directly in prod to stop the bleeding. The fix is never backported. Staging now tests a code path production has not executed in six days. Nobody knows until the next release breaks in a way nobody can reproduce locally.

### Why existing tools do not cover this

| Tool | What it does | Why it misses our case |
|---|---|---|
| Terraform / AWS Config / Firefly | IaC-declared state vs. actual cloud resource state | Infrastructure-level. A parameter value changed by hand outside IaC is not modelled. |
| `env-check` | Validates `.env` files against a per-environment schema | Its own README states it does not do automatic cross-environment diffing. |
| `pycheckem` | Snapshots and diffs Python runtime environments | Python-only, file/process-local, no AWS config sources, no attribution. |
| `kryptorious-draftguard` | Compares dev/staging/prod config **files** | File-based. Misses anything set at the control plane or resolved at runtime. |
| `tako drift` | Diffs config against running services | Config-vs-runtime for one environment, not environment A vs. environment B. |
| Convox / Upsun | Prevent drift by generating all environments from one source | Prevention by migration. Useless for an existing, already-drifted stack you will not migrate. |

**Our wedge:** a diagnostic tool for teams with existing AWS infrastructure who will not change platforms, that reads the real resolved values from the control plane and tells you not just *what* diverged but *who caused it and when*.

---

## 3. Users and jobs to be done

| User | Job |
|---|---|
| Backend / platform engineer | "Before I cut this release, show me every way prod differs from staging that isn't supposed to differ." |
| On-call engineer, mid-incident | "Something changed. Show me prod's config timeline for the last 24 hours." |
| Tech lead, post-incident | "Which of our environments still has the hotfix that was never backported?" |

---

## 4. Scope

### In scope (must exist by submission)

- **F1 — Agentless collection.** Snapshot the effective configuration of one or more AWS environments using control-plane APIs only. Zero code injected into any workload.
- **F2 — Snapshot history.** Every snapshot persisted immutably and addressable by time, so any two points in time can be compared.
- **F3 — Semantic diff.** Type-aware comparison between two snapshots, classified into exactly three severity buckets.
- **F4 — CloudTrail attribution.** For every divergence, identify the API call, the principal, and the timestamp that most likely produced it. **This is the headline feature. If this is not in the video, the project has failed.**
- **F5 — Time-travel diff.** Compare one environment against its own earlier self, not just against a sibling environment.
- **F6 — Dashboard.** Web UI: environment pair view with drift rows sorted by severity, detail panel showing attribution, and a per-environment timeline.

### Stretch (cut without discussion if behind)

- **S1** — Bedrock-generated plain-English blast-radius explanation per drift record
- **S2** — AppConfig feature flag collection
- **S3** — Cognito authentication
- **S4** — EventBridge → SNS alerting on new critical drift

### Explicitly out of scope (state this in the blog; it reads as judgement, not weakness)

- Multi-cloud. AWS only, deliberately.
- Auto-remediation. We diagnose; we never write config.
- Arbitrary config file formats.
- Real-time streaming. Scheduled and on-demand snapshots only.
- Secret **values**. We handle secret metadata only. See `SECURITY.md`.

---

## 5. Contracts — freeze these first

These are written and committed as JSON fixture files on Day 1 before any AWS work begins. Every lane codes against the fixtures, so nobody is blocked waiting for anybody else's component.

### 5.1 `EnvironmentSnapshot` (v1)

```json
{
  "schema_version": "1.0",
  "snapshot_id": "01J8XK2M4N7P9QRSTVWXYZ",
  "environment": "production",
  "account_id": "111122223333",
  "region": "ap-south-1",
  "captured_at": "2026-09-19T08:14:02Z",
  "collector_version": "0.1.0",
  "resources": [
    {
      "resource_type": "lambda",
      "logical_name": "checkout",
      "resource_arn": "arn:aws:lambda:ap-south-1:111122223333:function:prod-checkout",
      "config": {
        "env_vars": {
          "FEATURE_NEW_CHECKOUT": { "value": "false", "redacted": false },
          "DB_PASSWORD": { "value": null, "redacted": true, "value_sha256": "9f86d0…" }
        },
        "runtime": "python3.12",
        "memory_mb": 512,
        "timeout_s": 30,
        "layers": ["arn:aws:lambda:…:layer:common:14"],
        "last_modified": "2026-09-12T02:14:55Z"
      }
    }
  ],
  "parameters": {
    "/app/api_timeout": {
      "value": "30", "type": "String", "version": 4,
      "last_modified": "2026-09-01T11:02:00Z", "redacted": false
    }
  },
  "secrets": {
    "prod/db": { "version_id": "a1b2c3", "last_changed": "2026-08-30T09:00:00Z" }
  },
  "flags": {
    "new_checkout_enabled": { "value": true, "source": "appconfig" }
  }
}
```

**Rules:** any value classified as sensitive has `value: null`, `redacted: true`, and a salted SHA-256 so it can still be compared across environments without ever storing the plaintext. Redaction happens in the collector, before anything is written anywhere.

### 5.2 `DriftRecord` (v1)

```json
{
  "drift_id": "01J8XK…",
  "pair": "staging::production",
  "key": "lambda:checkout/env_vars/FEATURE_NEW_CHECKOUT",
  "kind": "value_mismatch",
  "value_a": "true",
  "value_b": "false",
  "severity": "critical",
  "rule_id": "R-FLAG-DIVERGED",
  "reason": "Boolean feature flag resolves differently between environments.",
  "first_seen_diverged": "2026-09-12T02:14:55Z",
  "last_confirmed": "2026-09-19T08:14:02Z",
  "attribution": { "…see 5.3…" },
  "explanation": null
}
```

`kind` is one of: `value_mismatch`, `type_mismatch`, `missing_in_a`, `missing_in_b`.
`severity` is one of exactly: `critical`, `suspicious`, `expected`. No fourth bucket. Ever.

### 5.3 `Attribution` (v1)

```json
{
  "confidence": "high",
  "event_name": "ssm:PutParameter",
  "event_time": "2026-09-12T02:14:55Z",
  "principal_arn": "arn:aws:iam::111122223333:user/rahul",
  "principal_type": "IAMUser",
  "source_ip": "203.0.113.4",
  "cloudtrail_event_id": "e1f2…",
  "narrative": "Set in production by rahul via ssm:PutParameter at 07:44 IST on 12 Sep. No corresponding change in staging."
}
```

`confidence`: `high` when a single CloudTrail write event targets the exact resource within the divergence window; `medium` when several candidate events exist; `none` when nothing is found (predates the trail, or was changed via IaC deploy rather than a direct call).

### 5.4 HTTP API

| Method | Path | Returns |
|---|---|---|
| `GET` | `/environments` | Registered environments, last snapshot time |
| `POST` | `/snapshots` | Body `{ "environment": "production" }` → kicks the state machine, returns `execution_arn` |
| `GET` | `/snapshots?environment=&limit=` | Snapshot index for the timeline |
| `POST` | `/compare` | Body `{ "a": {"env":"staging"}, "b": {"env":"production"} }` → `comparison_id` |
| `POST` | `/compare` (time-travel) | Body `{ "a": {"env":"production","at":"2026-09-11T00:00:00Z"}, "b": {"env":"production"} }` |
| `GET` | `/comparisons/{id}` | `{ "summary": {counts by severity}, "drifts": [DriftRecord] }` |

All responses: `application/json`, envelope `{ "data": …, "error": null }`.

---

## 6. Architecture

```
EventBridge Scheduler ──▶ Step Functions state machine
                              │
                              ├─ Map state (per environment, parallel)
                              │     └─ Collector Lambda  ──▶ redaction ──▶ S3 (versioned, SSE-KMS)
                              │                                            snapshots/{env}/{ts}.json
                              ├─ Diff Lambda  ── reads two snapshots from S3
                              │     └─ severity rules ──▶ DriftRecords
                              ├─ Attribution Lambda ── Athena over CloudTrail S3
                              │     └─ joins each drift to its causing API call
                              ├─ [stretch] Bedrock Lambda ── explanation per critical drift
                              └─ Persist Lambda ──▶ DynamoDB (drift table) + EventBridge event

API Gateway ──▶ API Lambda ──▶ DynamoDB / S3
React SPA on Amplify Hosting ──▶ API Gateway
```

### Why each service is load-bearing

| Service | Why it is not decorative |
|---|---|
| Step Functions | Collect → diff → attribute → persist is a genuine multi-stage pipeline with per-stage retries and a parallel Map over environments. A single Lambda would time out and could not retry stages independently. |
| S3, versioned | Time-travel (F5) is literally a diff between two object versions. DynamoDB is the wrong store for immutable multi-MB documents. |
| DynamoDB | Point lookups on `pair + key` to maintain `first_seen_diverged` across runs. This is the state that makes drift a time series instead of a snapshot. |
| Athena over CloudTrail | CloudTrail in S3 is partitioned JSON; Athena is the only sane way to query it by resource and time window. |
| EventBridge Scheduler | Drift that is only detected when someone clicks a button is not detection. |
| Bedrock | Reasons over the **joined** record — value, principal, timing, blast radius — not "summarize this diff". Stretch, and honestly labelled as such. |

---

## 7. Success criteria

**Definition of done (submission blocker if missing):**

- [ ] Snapshot two real AWS environments, agentless, one IAM role, no code changes to any workload
- [ ] Diff produces correctly bucketed severities on a fixture suite with passing unit tests
- [ ] At least one drift record in the demo carries a `high`-confidence CloudTrail attribution with a real principal ARN
- [ ] Time-travel comparison returns results
- [ ] Dashboard renders the comparison and the detail panel with attribution
- [ ] `SECURITY.md` in the repo, architecture diagram in the README, AWS services named on screen in the video
- [ ] Demo video under 3:00, AWS visible in it
- [ ] AI coding tools used are listed in the writeup (rule requirement)

**Cut order if behind:** S2 AppConfig → S3 Cognito → S4 alerting → S1 Bedrock. **CloudTrail attribution is never cut.** Without it we are a diff tool, which is the exact weakness this design exists to fix.

---

## 8. Demo narrative (3:00)

| Time | Beat |
|---|---|
| 0:00–0:20 | The story: a value changed in prod during an incident, never backported. Staging has been testing a path prod does not run. |
| 0:20–0:40 | The gap: Docker solves artifacts, Terraform solves infrastructure, **nothing** watches resolved runtime config. |
| 0:40–1:20 | Dashboard: trigger comparison on two real environments. Critical row surfaces. Note on screen — no agent installed, one read-only IAM role. |
| 1:20–2:00 | **The money shot.** Open the detail panel: *"Set in production by `rahul` via `ssm:PutParameter` at 02:14 UTC on 12 Sep. No corresponding change in staging."* Then show an expected-to-differ key (region) correctly classified as benign, proving the classifier is not just noisy string diffing. |
| 2:00–2:20 | Time-travel: prod against its own state before the incident. |
| 2:20–2:45 | Architecture: Step Functions execution graph on screen, name S3, DynamoDB, Athena/CloudTrail, EventBridge, Bedrock aloud. |
| 2:45–3:00 | What we learned, and the honest limitations. |

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| CloudTrail has no events because the account is new | **Highest-priority risk.** Enable the trail on Day 0 (account setup is allowed pre-clock) so there is real history by Day 3. Make real config changes on Day 1 and 2 as part of normal work — those become genuine attributable events. |
| Athena queries are slow or the partition layout fights us | Fall back to `CloudTrail:LookupEvents` API (90-day window, no Athena). Lower ceiling, same demo value. Ticket is pre-written. |
| Diff engine misclassifies on camera | Pure-Python module, unit-tested against fixtures on Day 1, before any AWS wiring. |
| Lane A blocks Lanes B and C | Fixtures are committed on Day 1 morning. B and C never wait on live AWS data. |
| Bedrock output is non-deterministic in the recording | It is a stretch feature and it is additive. If it says something odd, cut that second of the video. |
| UI polish eats Day 4 | Hard stop on UI at end of Day 3. |
