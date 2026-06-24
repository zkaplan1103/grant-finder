# Grant Navigator — Design Ground Truth

This is the single source of truth for how Grant Navigator looks and behaves.
All UI work must conform to it. It was derived from a three-track design
research pass (trust/verification UI, production-grade dashboard craft,
grant-tool category + portfolio bar) and a set of explicit product decisions.

---

## 1. What this product is

A **portfolio-grade** multi-agent web app. A nonprofit enters a profile; the app
returns **ranked grant matches**, each with a **drafted application** that has
passed a hallucination-checking **Verify** step before it is ever shown. It is
**not** a commercial SaaS — it exists to demonstrate engineering and design
judgment to a senior reviewer.

**The headline feature is the trust layer.** Anyone can wire agents that call
each other. The defensible, interview-worthy thing is: *does the safety check
actually catch fabricated claims, and is that visible in the UI?* Every design
decision serves making trust legible.

## 2. Audience

- **Primary (the one we design for):** a **senior engineer / design-literate
  reviewer** evaluating this as a portfolio piece. They judge on two axes — does
  the trust story land visually, and does it read production-grade (not
  vibe-coded).
- **In-fiction user:** a non-technical nonprofit caseworker. The flow must be
  easy and hard to get wrong, but polish is aimed at the reviewer.

## 3. Where it's going (design-for, build-later)

Phase 2 evolves into a **nonprofit ops dashboard** (run history, eval metrics,
traces). We do **not** build the dashboard now, but the results view must be
designed so it can drop into a dashboard shell without a redesign:

- Treat each search as a **"run"** (id, timestamp, params) conceptually.
- Results should be expressible as both **cards** (now) and a **table** (later).
- Leave room for a left **sidebar shell** and a top row of **KPI/metric cards**.

Don't build these yet — just don't make choices that would require ripping them out.

---

## 4. Aesthetic: Brutalist shell + technical data zones

The decided direction. Two visual registers with a clean seam:

- **Brutalist SHELL** — header, footer, wizard, buttons, page frame. This carries
  the distinctive identity: Space Grotesk, **2px black borders**, square corners
  (0 radius), the stamp-press button, uppercase mono labels.
- **Technical DATA ZONES** — the results list and every future data surface
  (tables, metrics, traces). Calmer and dashboard-ready: **1px gray hairlines**,
  soft **8px radius**, **semantic status color**. This is the "Linear/Vercel"
  register.

**The seam (Option A — chosen):** the shell stops at the page chrome. From the
results list onward, cards are **fully technical** (1px gray, 8px radius,
semantic color). Result cards do NOT carry the brutalist 2px-black frame.

Why this split: a trust-focused data tool needs semantic color to distinguish
verified/flagged/low-confidence *at a glance* (uniform visual weight destroys
trust). And 2px-black-everything scales into visual noise as the app grows into a
dashboard. The shell keeps the identity; the data zone stays legible at density.

---

## 5. Design system

### 5.1 Typography
- **Sans (human voice):** Space Grotesk — headings, body, UI copy.
- **Mono (system voice):** JetBrains Mono — labels, fit %, dollar amounts,
  dates, badges, the loading log, the verification trail. `tabular-nums` always.
- Rule: anything that is **data, metadata, or system instruction** is mono;
  anything that is **narrative or human content** is sans. Keep this split.
- Weight discipline: 400 reads, 500/600 emphasizes, 700 announces. No more.

### 5.2 Color
Grayscale base + **semantic color reserved strictly for status/severity**. If a
color can be removed without losing information, it doesn't belong.

| Token        | Light      | Role |
|--------------|------------|------|
| `--paper`    | `#f5f5f0`  | page background (warm) |
| `--bg`       | `#ffffff`  | data surfaces |
| `--ink`      | `#0a0a0a`  | text, shell borders, primary button |
| `--muted`    | `#525252`  | secondary text |
| `--hairline` | `#1a1a1a`  | **shell** borders (2px) |
| `--line`     | `#e5e5e1`  | **data-zone** hairlines (1px) |
| `--ok`       | `#15803d`  | verified |
| `--warn`     | `#b45309`  | needs review |
| `--err`      | `#b91c1c`  | unsupported claims / error |

Dark mode is a **designed** palette (independently tuned contrast/borders), not
an inversion. Persist the choice to localStorage. **Light is the default.**

### 5.3 Borders & radius
- Shell: **2px** `--hairline`, **0 radius**.
- Data zones: **1px** `--line`, **8px radius**.
- Elevation is border-first. Shadows are earned (interactive states only), never
  decorative. The stamp-press offset shadow lives ONLY on shell buttons.

### 5.4 Spacing
4px base grid: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64. Every margin/padding/gap
snaps to it. No magic numbers.

### 5.5 Components
- **Buttons (shell):** stamp-press — resting 4px hard offset shadow that
  collapses to 0 as the button translates in on `:active`; spring release.
  Square, uppercase, 2px border.
- **Inputs (shell):** square, 2px border, 3px focus outline. No glass, no blur.
- **Combobox:** free-text input + preset chips that **wrap to a block below the
  field** (never a side-scrolling row, never a popup that covers the field). One
  idiom for all preset fields.
- **Number fields:** plain text input, `inputMode=numeric`, **no spinner**,
  digits-only (no negatives), thousands separators on display (`300,000`).
- **Cards (data zone):** 1px `--line`, 8px radius, flat.

### 5.5.1 Two-axis labeling: SOURCE vs. VERIFICATION (trust-critical)
A result carries **two unrelated facts** that must never read as one status:

| Axis | Question it answers | Values | Treatment |
|------|--------------------|--------|-----------|
| **Source** | *Where did this grant come from?* | grants.gov / curated | A **labeled SOURCE chip** — neutral (gray, `--line` border), prefixed `SOURCE`. Provenance, not quality. |
| **Verification** | *Did the drafted application pass hallucination-checking?* | verified / needs review / draft | A **VERIFICATION badge** — semantic color + icon (see §6 three-tier). Quality of the draft, not the grant. |

**Rules:**
- The two are **visually and spatially separated** — never a row of look-alike
  pills. Different shape/label so a glance can't conflate them. The SOURCE chip
  is provenance metadata; the VERIFICATION badge is the trust signal.
- Each is **labeled** (the word `SOURCE` on the chip; the verification badge's
  own text — "Verified" / "Needs Review" / "Draft" — is self-labeling). A bare
  "curated" next to a bare "verified" is the exact bug this rules out.
- Semantic color belongs to **verification only**. Source is always neutral —
  "curated" is not better or worse than "grants.gov," so it gets no color.

### 5.6 Motion
- Step transitions: directional (forward slides from right, back from left),
  150–250ms, spring easing.
- Respect `prefers-reduced-motion` (disable transforms/animations). Non-negotiable.

---

## 6. Trust UI (the headline — locked spec)

These are mandatory, not optional polish:

0. **Source ≠ verification (see §5.5.1).** Where a grant came from (source) and
   whether its draft passed checking (verification) are unrelated axes and must
   never read as one status. Labeled neutral SOURCE chip, separated from the
   semantic VERIFICATION badge.

1. **Three-tier status treatment.** `verified` / `needs_human` / `draft` each get
   a **distinct card treatment**, not just a badge color, so verification state
   reads at a glance:
   - **Verified:** green check badge, full-weight card, quiet. Verification trail
     available on disclosure.
   - **Needs Review:** amber triangle badge, amber left-border accent, flagged
     claims (claim + reason) shown in a red-gutter list without needing to expand.
   - **Draft:** gray badge, slightly muted card (signals "not yet checked").

2. **Low-confidence card treatment.** When `low_confidence` is true, **mute the
   whole card** (reduced opacity) and qualify the score inline ("(low
   confidence)"). High- and low-confidence results must never look equally
   authoritative.

3. **Score + reasoning coupling (Stripe Radar model).** The fit % is always
   paired with its `reasoning`; `caveats` render as a secondary muted
   "risk-factor" list beneath. Never show a naked percentage.

4. **Visible verification trail.** Make "Verified" inspectable proof, not a label.
   The trail is **"issues found vs. resolved across N passes,"** derived purely
   from `unresolved_claims` + `revision` on the `Draft` (no backend field — see
   §9). Phrasing: when the loop caught and fixed something, "Found 2 unsupported
   claims, resolved both across 3 passes" — strongest exactly here. When a draft
   passes clean on the first try (0 issues), render a confident
   **passed-verification** state ("Verified in 1 pass"), never empty/missing data.
   Always-visible for `needs_human`; quiet disclosure for `verified`.

### Trust anti-patterns — never do these
- Uniform visual weight across confidence levels.
- Naked percentage with no reasoning.
- Generic "AI may make mistakes" disclaimers (banner blindness). Banners must be
  specific and actionable (the existing sparse-profile / grants.gov banners are
  the model).
- "Verified" badge without a real verify step behind it.

## 7. Open UI work (tracked, not yet built)
- **<50% weak-matches toggle.** Backend already hides matches below 0.5 fit by
  default (`min_display_score`). UI needs a "show weaker matches" toggle.
- **Skeleton loading** that previews the results layout (in addition to the
  existing phased terminal log), so loading → loaded swaps in place.

## 8. Portfolio bar — keep / kill
**Keep (already clearing senior bar):** discriminated-union view state, SSE
streaming progress, the verify pipeline, graceful grants.gov degradation,
error/empty states, reduced-motion, the dual-font system, typed end-to-end.

**Kill (AI-slop tells):** emojis in UI or model output (prompts now forbid them),
default Vite title/favicon, fake data that doesn't hold up, sub-800ms loading
flashes (enforce a min display time per phase so the pipeline is visible).
Add a **"Try a sample profile"** button that pre-fills a realistic org and
exercises all three status tiers — eliminates the reviewer's "what do I type" failure.

## 9. Backend follow-ups this design implies
- **CLOSED — won't-need (2026-06-23):** earlier this section asked for a new
  "claims checked" count field on the Verify result / Draft model. Decision: do
  **not** add it. The verification trail is counted as **"issues found vs.
  resolved across N passes,"** which is fully derivable from data already on the
  `Draft` model (`unresolved_claims` + `revision`). No backend change is needed.
  - Rationale: "we checked 47 claims" is a hollow number that doesn't show
    checking *worked*; "found 2 unsupported claims, resolved both across 3
    passes" shows the loop doing its job, and is the stronger trust story. A
    total-claims-examined count would also require Verify to count/report every
    claim it assessed (a prompt + model change) and produce a number that can't
    be ground-truthed — the exact verification-theater risk §6 warns against.
  - **Design implication:** a clean first-pass draft shows "0 issues found,"
    which is correct but visually empty. Render the zero-issue case as a
    **verified / passed-verification state** (confident, green, "verified in 1
    pass"), NOT as missing data. The trail is most dramatic when it should be —
    when the loop actually caught and fixed something.

---

## 10. How to use this file
Any UI change conforms to §4–§6. When a choice isn't covered here, prefer the
**technical/Linear register** for data zones and the **brutalist register** for
shell, keep semantic color to status only, and never weaken a trust signal.
Update this file when a design decision changes — it is the ground truth.
