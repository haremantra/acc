# Worked Example — Good vs Bad ACC

Calibration for the quality bar: **<800 words, one line per item, facts not narrative**,
no recap of tooling or "how" — only what was decided, what exists, what's blocked.

---

## Good ACC (tight, load-bearing)

```
# Context Compression — 2026-05-20
**Focus:** auth middleware rewrite
**Token estimate before:** ~110k
**Token estimate after:** ~0.6k

## Decisions
- D: Replace session-cookie auth with JWT — legal flagged cookie token storage as non-compliant
- D: Keep /login route signature unchanged — avoids breaking the mobile client

## Current State
- src/auth/jwt.ts: created, 14 tests passing
- src/auth/session.ts: deleted
- branch auth-rewrite: 3 commits ahead of main, uncommitted changes in middleware.ts

## Open Questions
- Q: refresh-token rotation strategy undecided — blocks middleware.ts completion

## Rejected Approaches
- X: opaque tokens + Redis lookup — rejected, adds an infra dep the team won't own

## Next Actions
1. Decide refresh-token rotation — then finish src/auth/middleware.ts
2. Migrate mobile client to read JWT — clients/mobile/auth.ts
```

**Why it passes:** every line is a fact a future session can act on. No "we explored",
no tool narration. File paths + test counts + branch state make re-discovery unnecessary.

---

## Bad ACC (padded, narrative, duplicates HANDOFF)

```
# Context Compression — 2026-05-20
**Focus:** worked on auth stuff today

## Decisions
- We had a really productive session exploring the authentication system. After looking
  at lots of options and discussing trade-offs at length, we eventually came around to
  the idea that maybe JWT could be a good fit, though we considered many things. I read
  through src/auth/ and ran the tests several times to understand the behavior...

## Current State
- Made good progress. See HANDOFF.md for everything.
```

**Why it fails:** narrative, not facts; no actionable specifics (which files? which
decision? what's blocked?); "see HANDOFF.md for everything" means the ACC carries zero
marginal information — pure duplication. A future session learns nothing it couldn't get
from HANDOFF. This is the **habit-not-leverage** failure the Step-0 necessity check
exists to prevent.
