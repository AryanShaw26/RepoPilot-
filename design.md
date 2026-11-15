# RepoPilot — Design System & UI Specification

> **Style:** Skeuomorphism + Neumorphism ("Instrument Panel" concept)
> **Audience:** AI coding agent. Implement exactly as specified; tokens are authoritative. Pair with `prd.md` (features, endpoints) and `implementation_guide.md` (build order).

---

## 1. Design Concept: "The Instrument Panel"

RepoPilot is a *pilot* for your codebase. The whole interface is a **tactile cockpit console**:

- **Neumorphism** provides the base language: soft, extruded and inset surfaces carved out of one continuous material, with light from the top-left.
- **Skeuomorphism** provides the physical details that give meaning: rotary dials, toggle switches, LED indicator lamps, embossed placards, glass gauge lenses, screw heads, and a needle gauge.

**Rule of thumb:** *surfaces are neumorphic; controls and indicators are skeuomorphic.* Panels, cards and inputs are soft-molded. Anything that signals state (verified/hypothesis/progress/toggle) looks like a real hardware component.

**Meaning through hardware (not decoration):**

| Hardware element | Product meaning |
|---|---|
| Green LED lamp | **Verified from source** (a fact) |
| Amber LED lamp | **Hypothesis** (AI interpretation — verify first) |
| Red LED lamp | Weak evidence / error |
| Inset glass display | Code, evidence snippets (raw facts live in "windows") |
| Embossed metal placard | Section labels / module names |
| Needle gauge | Analysis progress and evidence strength |
| Toggle switch | Mode toggles (keyword / semantic / hybrid, show external deps) |

**The one memorable moment (spend boldness here, keep everything else quiet):** the **Analysis Cockpit** — while a repository is being analysed, a cluster of three physical gauges (progress needle, stage lamps, file counter drum) animates in response to real job state. Everything else stays calm and disciplined.

---

## 2. Design Tokens

### 2.1 Colour (Light theme — default)

| Token | Hex | Use |
|---|---|---|
| `--surface` | `#DFE4EA` | Base material of the whole UI (cool instrument grey-blue) |
| `--surface-raised` | `#E6EBF1` | Raised panels |
| `--surface-inset` | `#D5DBE3` | Pressed/inset wells, inputs |
| `--shadow-light` | `#FFFFFF` | Top-left highlight |
| `--shadow-dark` | `#B4BDC9` | Bottom-right shade |
| `--ink` | `#1F2933` | Primary text (contrast ≥ 12:1 on surface) |
| `--ink-muted` | `#4A5766` | Secondary text (≥ 6:1) |
| `--ink-faint` | `#6B7888` | Placeholders, disabled labels (≥ 4.5:1 — do not go lighter) |
| `--edge` | `#9AA5B4` | 1px functional outline for contrast (see §2.6) |
| `--brand` | `#1F5EFF` | Primary action, focus ring, links (cobalt, like avionics blue) |
| `--brand-deep` | `#1743B8` | Pressed brand |
| `--led-green` | `#1FA36A` | Verified fact |
| `--led-amber` | `#F2A100` | Hypothesis |
| `--led-red` | `#D93B3B` | Error / weak evidence |
| `--glass` | `#0F1720` | Inset "screen" background (code viewer, evidence windows) |
| `--glass-ink` | `#D7E2EE` | Text on glass |
| `--metal-hi` | `#F4F6F9` | Brushed-metal highlight |
| `--metal-lo` | `#B9C1CC` | Brushed-metal lowlight |

### 2.2 Colour (Dark theme — `[data-theme="dark"]`)

| Token | Hex |
|---|---|
| `--surface` | `#232A33` |
| `--surface-raised` | `#2A323C` |
| `--surface-inset` | `#1C2229` |
| `--shadow-light` | `#323B47` |
| `--shadow-dark` | `#141A20` |
| `--ink` | `#E8EEF5` |
| `--ink-muted` | `#B3BFCC` |
| `--ink-faint` | `#8896A6` |
| `--edge` | `#46515F` |
| `--brand` | `#5B8CFF` |
| `--glass` | `#0B1118` |

LED colours stay the same but glow intensity increases in dark mode. Respect `prefers-color-scheme` on first load; allow manual override (stored in `localStorage` as `rp-theme`).

### 2.3 Typography

| Role | Font | Weights | Notes |
|---|---|---|---|
| Display / placards | **Barlow Semi Condensed** | 600, 700 | Cockpit-placard feel; used for page titles and module names |
| UI & body | **Figtree** | 400, 500, 600 | Friendly, legible at small sizes |
| Code / evidence | **JetBrains Mono** | 400, 500 | Ligatures off |

Fallback stacks: `'Barlow Semi Condensed', 'Arial Narrow', sans-serif` · `'Figtree', system-ui, sans-serif` · `'JetBrains Mono', ui-monospace, Menlo, monospace`. Load via Google Fonts with `display=swap` (preconnect). Avoid ALL-CAPS tracked labels: use sentence case in Barlow 600 for placards instead.

**Type scale (1.2 ratio, rem):** `xs 0.75 · sm 0.875 · base 1 · md 1.125 · lg 1.35 · xl 1.62 · 2xl 1.95 · 3xl 2.5 · 4xl 3.25`.
Line-height: body 1.55, headings 1.15, code 1.6. Max text line length: 70ch.

### 2.4 Spacing, Radius, Elevation

- Spacing scale (px): `4, 8, 12, 16, 24, 32, 48, 64, 96`.
- Radius: `--r-sm 8px` (inputs, chips) · `--r-md 14px` (cards) · `--r-lg 22px` (large panels) · `--r-pill 999px` (toggles, badges) · `--r-round 50%` (knobs, lamps). **Use different radii by hierarchy** — not one radius everywhere.

**Neumorphic shadows (light source top-left):**

```css
:root {
  --elev-1: 4px 4px 10px var(--shadow-dark), -4px -4px 10px var(--shadow-light);          /* small raised */
  --elev-2: 8px 8px 18px var(--shadow-dark), -8px -8px 18px var(--shadow-light);          /* panels */
  --elev-3: 14px 14px 30px var(--shadow-dark), -14px -14px 30px var(--shadow-light);      /* hero / modals */
  --inset-1: inset 3px 3px 7px var(--shadow-dark), inset -3px -3px 7px var(--shadow-light); /* wells, inputs */
  --inset-2: inset 6px 6px 12px var(--shadow-dark), inset -6px -6px 12px var(--shadow-light);/* pressed buttons */
}
```

### 2.5 Skeuomorphic Material Recipes

```css
/* Brushed metal placard (module titles, nav plate) */
.metal {
  background:
    repeating-linear-gradient(90deg, rgba(255,255,255,.18) 0 1px, rgba(0,0,0,.03) 1px 2px),
    linear-gradient(180deg, var(--metal-hi), var(--metal-lo));
  border: 1px solid var(--edge);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.8), inset 0 -1px 0 rgba(0,0,0,.12), var(--elev-1);
}

/* Glass display (code windows) */
.glass {
  background: linear-gradient(180deg, rgba(255,255,255,.05), transparent 30%), var(--glass);
  color: var(--glass-ink);
  border-radius: var(--r-md);
  box-shadow: inset 0 2px 10px rgba(0,0,0,.6), inset 0 0 0 1px rgba(255,255,255,.06), 0 1px 0 var(--shadow-light);
}

/* LED lamp (green / amber / red) */
.led {
  width: 12px; height: 12px; border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #fff9 0 12%, var(--led) 40%, color-mix(in srgb, var(--led) 60%, #000) 100%);
  box-shadow: 0 0 0 2px var(--surface-inset), 0 0 8px 2px color-mix(in srgb, var(--led) 55%, transparent);
}
.led.off { filter: grayscale(1) brightness(.7); box-shadow: 0 0 0 2px var(--surface-inset); }

/* Screw head (decorative, only on large panels, aria-hidden) */
.screw {
  width: 10px; height: 10px; border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, var(--metal-hi), var(--metal-lo));
  box-shadow: inset 0 0 0 1px rgba(0,0,0,.15);
  position: relative;
}
.screw::after { content:""; position:absolute; inset:4px -1px; height:2px; background: rgba(0,0,0,.35); transform: rotate(35deg); }
```

### 2.6 Accessibility Guardrails for Neumorphism (MANDATORY)

Neumorphism's classic failure is low contrast. Therefore:

1. All text must meet **WCAG AA** against its actual background (use tokens above; never lighten `--ink-faint`).
2. Interactive elements must have a **1px `--edge` outline** at ≥ 3:1 vs. surrounding surface *in addition to* shadows (shadows alone don't count as a boundary).
3. State must **never** rely on colour alone: LEDs always pair with a text label (e.g., "Verified", "Hypothesis").
4. Focus ring: `outline: 3px solid var(--brand); outline-offset: 3px;` on `:focus-visible` for every interactive element.
5. `prefers-reduced-motion: reduce` → disable needle sweeps, pulsing LEDs, and parallax; show static end states.
6. Minimum target size 44×44 px on touch devices.

---

## 3. Component Specifications

### 3.1 Buttons

| Variant | Appearance | Use |
|---|---|---|
| **Primary (Key)** | Raised pill, `--brand` fill with subtle top gloss, `--elev-1`, white text. Pressed: `--inset-2` and 1px translateY. | "Analyse repository", "Generate plan" |
| **Secondary (Soft)** | `--surface-raised`, `--elev-1`, `--edge` outline, ink text. Pressed: `--inset-1`. | Most actions |
| **Icon key** | 44×44 round, raised, icon centered | Toolbar |
| **Danger** | Secondary with red LED dot + red text | Delete repository |

Transition: `120ms ease-out` on box-shadow/transform only. Disabled: 50% opacity, no shadow, `cursor: not-allowed`.

### 3.2 Inputs

Inset wells (`--inset-1`, radius `--r-sm`, `--edge` outline). The **repository URL field** is the hero input: large (56 px tall), a GitHub-mark icon embedded at left in a raised round, a validation LED at right (grey = empty, amber = checking, green = valid GitHub URL, red = invalid) with a text hint below.

### 3.3 Toggle Switch (Skeuomorphic)

Pill track (inset) with a raised circular knob; ON slides knob right and lights a small green LED on the track. Use for: "Include external packages", "Exclude tests", "Show hypothesis details". Keyboard: Space toggles; `role="switch"` with `aria-checked`.

### 3.4 Segmented Rotary Selector (search mode)

A 4-position selector (Keyword · Symbol · Semantic · Hybrid) rendered as a horizontal segmented control where the active segment is **inset (pressed)** and others are raised; a small indicator LED above the active one. Semantic is disabled with tooltip when `semantic_available=false`.

### 3.5 Cards / Panels

- Panel: `--surface-raised`, radius `--r-md` (cards) or `--r-lg` (page-level panels), `--elev-2`.
- Panel header: brushed-metal **placard** strip (module name in Barlow 600, 1.35rem) with two `.screw` at the ends on page-level panels only.
- Do **not** wrap every piece of content in a card. Use whitespace and inset wells for grouping; use raised cards only for independently actionable items (repository card, result card, plan step).

### 3.6 Badges (Core Trust UI)

| Badge | Visual | Text | Where |
|---|---|---|---|
| **Verified** | Green LED + inset pill | "Verified from source" | Facts: paths, symbols, imports, snippets, reverse-dependencies |
| **Hypothesis** | Amber LED (slow 3 s pulse, disabled in reduced-motion) + inset pill | "Hypothesis — verify before implementing" (compact: "Hypothesis") | Every LLM-authored statement |
| **Weak evidence** | Red LED + inset pill | "Weak evidence" | `evidence_strength = weak` |
| **Confidence** | 3-segment bar (1–3 lit amber segments) | "low / medium / high" | Hypotheses |

Badges must appear **adjacent to the statement they describe**, never only in a footer.

### 3.7 Gauges

- **Progress needle gauge** (Analysis Cockpit): semicircular dial 0–100, brushed bezel, glass lens highlight, needle animates to `progress` with a spring (`cubic-bezier(.34,1.56,.64,1)`, 600 ms). Implement as SVG.
- **Stage lamps:** row of 5 lamps labelled Fetching · Parsing · Indexing · Embedding · Ready. Past = green lit, current = amber blinking, future = off, failed = red.
- **File counter drum:** mechanical odometer-style digits (CSS vertical translate per digit) showing files processed.
- **Evidence strength meter:** small 3-LED bar (weak 1 red / moderate 2 amber / strong 3 green) beside a text label.

### 3.8 Tabs / Navigation

- **Top bar:** brushed-metal strip across the page (height 64 px) with logo (a small compass/needle mark + "RepoPilot" in Barlow 700), current repo chip (owner/name with a status LED), theme switch, and a Help key.
- **Module nav (in a repo):** left rail (desktop) of six raised **rocker keys**: Overview, Explorer, Dependencies, Issues, Plan, Tests. Active key is inset with a green indicator LED; others raised. Mobile: bottom bar with 5 keys + overflow.

### 3.9 Code Viewer & Evidence Windows ("Glass")

- Background `--glass`, text `--glass-ink`, JetBrains Mono 13–14 px, line numbers in `#6E7F92`.
- Highlighted evidence lines: left 3px bar in `--brand` and background `rgba(91,140,255,.14)`.
- Header strip (metal) shows file path, language, line range, "Copy path" key.
- Syntax theme: custom or `github-dark-dimmed`-like; **ensure ≥ 4.5:1** for all tokens.

### 3.10 File Tree

Inset well. Rows 32 px high; folders show a small raised chevron key; selected row is a *pressed* (inset) strip with brand left edge. Language dot (colour by language) before file name; test files get a small "T" glyph chip.

### 3.11 Dependency Graph (React Flow)

- Canvas: inset well with a faint engineered grid (1px lines at 6% ink opacity).
- **File node:** small raised rounded rectangle (radius 10) with file name (mono 12 px), language dot; **folder node:** deeper raised plate with a stack-lines glyph and child count.
- Edges: 1.5 px, `--ink-faint`, rounded smoothstep; highlighted path edges in `--brand` with 2.5 px.
- Node sizing by in-degree (min 120 px, max 180 px width). Entry points get a small green LED; nodes in cycles get a red LED.
- Controls (zoom/fit/layout) as a raised key cluster bottom-right. Mini-map as inset glass at bottom-left.
- Always show caption in a metal strip: *"Statically extracted imports — dynamic imports and reflection may be missing."*

### 3.12 Toasts & Dialogs

Toast: raised pill from bottom-centre, LED matching severity. Dialog: `--elev-3` panel, backdrop `rgba(15,23,32,.45)` with 4 px blur; focus trapped; Esc closes.

### 3.13 Empty / Loading / Error States

- **Loading skeletons:** inset wells with a very slow (2 s) light sweep (static in reduced-motion).
- **Empty:** a small illustrated hardware icon (e.g., unplugged cable) + one sentence + one primary action. Copy is plain and specific (see §6).
- **Error:** red LED + plain explanation + "Try again" secondary key; show error `code` in a small mono chip.

---

## 4. Layout & Pages

Global: max content width 1280 px; 12-column grid, 24 px gutters (16 px on mobile); left-aligned text everywhere (no justified text); page padding 32 px desktop / 16 px mobile.

### 4.1 Landing (`/`)

```
┌───────────────────────────────────────────────────────────────────────────┐
│ [metal top bar]  ◎ RepoPilot                              [theme] [Help]  │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│   Understand any codebase.            ┌──────────────────────────────┐    │
│   Find where to start.                │  (raised hero console)       │    │
│   Contribute with confidence.         │  ┌ glass: sample evidence ┐  │    │
│                                       │  │ 52 │ def refresh(...)  │  │    │
│   [ github.com/owner/repo       ●]    │  └────────────────────────┘  │    │
│   [ Analyse repository ]              │  ● Verified  ● Hypothesis    │    │
│                                       └──────────────────────────────┘    │
│                                                                           │
│   Three raised keys: Understand · Investigate · Contribute (short copy)   │
│   Trust strip (inset): Read-only · No code executed · Secrets excluded    │
└───────────────────────────────────────────────────────────────────────────┘
```

- The hero console is a static, hand-written sample that **shows the Verified vs Hypothesis distinction** (the product's core idea) rather than a generic illustration.
- Recent repositories (from session) appear below as raised repo cards.

### 4.2 Analysing (`/repo/:id/analysing`) — The Analysis Cockpit

```
┌──────────── Analysing  owner/repo ─────────────┐
│   (  needle gauge  )   (  stage lamps  )       │
│        63 %            ● Fetching              │
│                        ● Parsing               │
│   [ 0 0 1 2 4 ]  files ◉ Indexing  (current)   │
│                        ○ Embedding             │
│   message: "Extracting symbols from src/…"     │
│   [ Cancel ]                                   │
└────────────────────────────────────────────────┘
```

On `ready`, the needle snaps to 100, all lamps light, a soft "click" micro-animation plays (no audio), then auto-navigate to Overview after 800 ms.

### 4.3 Overview (`/repo/:id`)

- Header placard: repo name, description, stars, license, commit SHA (mono chip), branch.
- Row of inset **stat wells**: files, languages, symbols, tests.
- Language breakdown: horizontal segmented bar (inset track) with legend.
- Frameworks + Entry points: two panels, each item with Verified badge and evidence path.
- Architecture summary panel: Hypothesis badge + text + "Based on N files" evidence links.
- Folder tree preview (top 2 levels).

### 4.4 Explorer (`/repo/:id/explorer`)

```
┌─ search [____________] [Keyword|Symbol|Semantic|Hybrid] ───────────────┐
├────────────┬───────────────────────────────────────┬───────────────────┤
│ File tree  │ Glass code viewer                     │ Outline           │
│ (inset)    │  header: path · lang · lines          │ (symbols list)    │
│            │  highlighted lines via ?line=         │ ─────────────     │
│            │                                       │ Explain [key]     │
│            │                                       │ Imports / Used by │
└────────────┴───────────────────────────────────────┴───────────────────┘
```

Search results replace the centre panel as a list of result cards (path, line range, snippet in a small glass window, source chips: keyword/symbol/semantic).
Mobile: tabs (Files | Code | Outline).

### 4.5 Dependencies (`/repo/:id/dependencies`)

Toolbar (metal strip): level toggle (File/Folder), "Include external" switch, search-node input, layout key. Graph canvas fills remaining height. Right drawer (inset) opens on node click: file details, imports, imported-by, "Open in Explorer" key.

### 4.6 Issues (`/repo/:id/issues`)

- Left: composer panel — tabs "Paste text" / "GitHub issue URL", inset textarea, **Investigate** primary key.
- Right/below: history list of past investigations.

### 4.7 Investigation Detail (`/investigation/:id`)

1. Top: issue summary + evidence strength meter (3-LED + label).
2. **Ranked evidence list:** each result card = rank number (embossed), file path, symbol, score, source chips, `why_relevant` text with Hypothesis badge, and a glass evidence window with highlighted lines + "Open in Explorer".
3. **Hypotheses panel:** each hypothesis with amber badge, confidence segments, and evidence reference chips (click scrolls to evidence).
4. Footer: constant disclaimer in a metal strip + **Generate contribution plan** primary key.

### 4.8 Plan (`/plan/:id`)

Vertical **checklist-style steps** (a flight checklist metaphor): each step is a raised row with a numbered embossed circle, title, description, file chips, and its badge (fact/hypothesis). Sections: Summary · Steps · Impacted files (Verified) · Risks (Hypothesis) · Tests (existing = Verified, recommended = Hypothesis) · Validation checklist (real checkboxes the user can tick; state is local only). Actions: Copy Markdown, Download `.md`.

### 4.9 Tests (`/repo/:id/tests`)

Test framework chips, stat wells (test files, source files with mapped tests %), table of source → tests mapping (with method and confidence), no claim of execution. A permanent notice: *"RepoPilot finds and suggests tests. It does not run them."*

---

## 5. Motion

| Moment | Behaviour | Duration |
|---|---|---|
| Button press | Raised → inset, 1px shift | 120 ms |
| Toggle | Knob slides, LED fades on | 180 ms |
| Page navigation | Cross-fade only (no slide-up on every section) | 150 ms |
| Analysis gauge | Needle spring to real progress; lamps change on stage | 600 ms |
| Hypothesis LED | Slow pulse (opacity .75↔1) | 3 s loop |
| Skeleton sweep | Light band across inset wells | 2 s loop |

No scroll-triggered entrance animations. No parallax. All motion disabled or reduced under `prefers-reduced-motion`.

---

## 6. Voice & Copy

- Plain, specific, calm. Sentence case. No hype, no exclamation marks, no emoji.
- Label what is certain vs. inferred: "Found in `src/auth.py:52`" (fact) vs. "Possible cause" (hypothesis).
- Error copy names the problem and the next step: *"This repository is private. RepoPilot can analyse public repositories only."*
- Empty states: *"No investigations yet. Paste an issue to find the code that matters."*
- Never write "tests passed/ran" anywhere in the UI.

---

## 7. Responsive Behaviour

| Breakpoint | Behaviour |
|---|---|
| ≥ 1280 | Full three-column Explorer, side rail nav |
| 1024–1279 | Outline collapses into a drawer |
| 768–1023 | Rail nav becomes icon-only; two-column layouts stack |
| < 768 | Bottom nav bar; Explorer in tabs; graph in full-screen mode with pinch-zoom; reduce shadow offsets by ~40% (`--elev-*` scaled) for performance and clarity |

---

## 8. Implementation Notes

### 8.1 Files to create (frontend)

```
src/styles/tokens.css       # all CSS variables (light/dark), shadows, radii
src/styles/neumorph.css     # .raised .inset .metal .glass .led .screw utilities + keyframes
src/styles/globals.css      # resets, base typography, focus ring, reduced-motion rules
tailwind.config.ts          # extend theme: colors→CSS vars, boxShadow→elev/inset, fontFamily, borderRadius
```

### 8.2 Tailwind config essentials

```ts
// tailwind.config.ts (excerpt)
export default {
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        surface: 'var(--surface)', raised: 'var(--surface-raised)', well: 'var(--surface-inset)',
        ink: 'var(--ink)', muted: 'var(--ink-muted)', faint: 'var(--ink-faint)',
        edge: 'var(--edge)', brand: 'var(--brand)',
        led: { green: 'var(--led-green)', amber: 'var(--led-amber)', red: 'var(--led-red)' },
        glass: 'var(--glass)',
      },
      boxShadow: {
        e1: 'var(--elev-1)', e2: 'var(--elev-2)', e3: 'var(--elev-3)',
        i1: 'var(--inset-1)', i2: 'var(--inset-2)',
      },
      borderRadius: { sm: '8px', md: '14px', lg: '22px' },
      fontFamily: {
        display: ['"Barlow Semi Condensed"', '"Arial Narrow"', 'sans-serif'],
        sans: ['Figtree', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'Menlo', 'monospace'],
      },
    },
  },
}
```

### 8.3 Reusable React components to build (in `components/ui/`)

`Button`, `IconKey`, `TextInput` (with validation LED), `TextArea`, `Switch`, `Segmented`, `Panel`, `Placard`, `Badge` (variants: verified | hypothesis | weak | confidence), `Led`, `NeedleGauge`, `StageLamps`, `CounterDrum`, `EvidenceMeter`, `CodeWindow`, `FileTree`, `StatWell`, `Toast`, `Dialog`, `Skeleton`, `EmptyState`, `ErrorState`, `Tooltip`, `Tabs`.

Each must: forward refs, support `className`, have visible focus, support dark theme through tokens only (no hard-coded colours in components).

### 8.4 Performance

- `box-shadow` is expensive when stacked: avoid more than ~60 raised elements visible simultaneously in lists — virtualise long lists (file tree, search results) with `@tanstack/react-virtual`.
- Use `will-change: transform` only on animated needles/knobs.
- Graph nodes use a **lighter shadow** (single `--elev-1`) and no metal texture.

### 8.5 Quality Checklist

- [ ] Light and dark themes both pass AA on all text.
- [ ] Every interactive element has `--edge` outline + focus ring.
- [ ] Verified / Hypothesis badges appear next to each relevant statement.
- [ ] No state conveyed by colour alone.
- [ ] Reduced-motion verified.
- [ ] Mobile layouts verified at 360 px.
- [ ] No hard-coded hex values in components (tokens only).

### 8.6 Restraint (Do / Don't)

**Do:** keep surfaces quiet; let LEDs, the needle gauge, and glass windows carry meaning; vary radii by hierarchy; leave generous space.
**Don't:** stack decorative screws everywhere; wrap all content in identical cards; add gradient washes as decoration; use tracked ALL-CAPS eyebrow labels above every heading; make everything extruded (use inset wells to create contrast of depth).
