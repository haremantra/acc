# ACC Necessity Check (Step 0)

ACC's only leverage is **inter-session**: it produces a portable artifact that lets a
future thread skip replaying this one. Within the current session it *adds* tokens, not
removes them. So the gate before compressing is: *will this ACC actually be loaded
somewhere a HANDOFF.md wouldn't?*

Run this rubric mentally. **If ≥4 of the right-column conditions hold, abort** with
`ACC not needed — HANDOFF covers it` and tell the user why. Otherwise proceed to Step 1.

| Criterion | ACC adds value | HANDOFF sufficient |
|---|---|---|
| **Session size** | >100k tokens | <50k tokens |
| **Topic count** | 2+ topics interleaved | single-topic |
| **Domain spread** | repo + Claude infra + external tools | single repo only |
| **HANDOFF freshness** | stale, missing, or not refreshed this session | just refreshed at end of session |
| **Cross-tool state** | Gmail drafts, Drive IDs, MCP quirks, gh flows, hook configs | none — all state is in the repo |
| **Rejected-path density** | many dead ends worth recording | few or none |
| **Lifecycle stage** | early / migration / decision-fork | steady execution within plan |
| **Portability need** | paste into Slack / email / new thread | stays with the repo |
| **Tooling/infra decisions** | many (precommit contract, hook redesign, MCP capabilities) | none — all decisions are project-narrative |

**Marginal-value formula:** ACC value ≈ (tokens compressed) × (fraction of content not
in HANDOFF). When HANDOFF discipline is strong AND the session is single-topic, that
fraction → near-zero, and ACC becomes habit-not-leverage.

**Failure mode to flag explicitly — "ACC not needed, try HANDOFF":** a small,
single-topic, single-repo session where HANDOFF.md was the deliverable. Symptom: the ACC
output would be ~70%+ duplication of the just-refreshed HANDOFF body. Action: skip ACC;
rely on HANDOFF + memory + a one-line "see commit X" pointer.

If the user **explicitly** invoked `/acc`, you may still produce one — but lead with the
necessity finding so the user can decide whether to keep it. Don't silently produce a
low-value artifact.
