# FoodLens design reference

This folder holds the approved FoodLens UI design. Use it to make the app look and behave like the prototype.

**Precedence:** this folder decides how screens **look**. `CLAUDE.md` and `docs/DECISIONS.md` (D137 onwards) decide **scope, rules and wording**. The prototype was designed during the earlier registration-lookup phase, so its copy and some flows are out of date. Where they disagree, CLAUDE.md and DECISIONS.md win. Never copy prototype wording without checking it against CLAUDE.md rule 1.

## What's in here

| Path | What it is | How to use it |
| --- | --- | --- |
| `screens/*.png` | 103 screenshots, one per prototype board, full page | The visual source of truth. Open the matching screenshot before building or restyling a screen. |
| `prototype/*.dc.html` | The prototype source for each board | Read it for exact spacing, colours, radii, SVG icons and component structure. It is template HTML (`{{holes}}`, `<sc-if>`, `<sc-for>`, a `renderVals()` script), not runnable app code. Port the markup to React and Tailwind; don't import these files. |
| `prototype/canvas.json` | Board list with titles and sizes | Board titles name the screen and state, e.g. `Result · not found`. |
| `assets/` | Hero videos and posters, scan-ready animation, scan photo | Copy what you use into `frontend/public/`. |

Wrapper boards (for example `SupOrderAccepted`) just show another board in a set state. The screenshot of the wrapper shows that state.

Screenshots were rendered with Poppins, Open Sans and IBM Plex Mono. In the app, load them with `next/font/google`.

## Design tokens (Tailwind v4)

Add these to `frontend/app/globals.css`. They replace the default Geist and black-and-white theme.

```css
@theme {
  --font-heading: var(--font-poppins), system-ui, sans-serif;
  --font-sans: var(--font-open-sans), system-ui, sans-serif;
  --font-mono: var(--font-plex-mono), ui-monospace, monospace;

  /* brand */
  --color-brand: #1B7A45;        /* primary buttons, active nav */
  --color-brand-dark: #145C34;   /* links, text on green tints */
  --color-brand-tint: #E3F4EA;
  --color-ink: #16143D;          /* headings, sidebars, scan screen */
  --color-ink-2: #1F1D5C;        /* hero and feature panels, text on yellow */
  --color-sun: #F6B93B;          /* demo banner, accents, step numbers */
  --color-cream: #FAF8F3;        /* business workspace background */
  --color-paper: #F5F5F3;        /* consumer background */
  --color-sky: #24689C;          /* retailer / buyer accent */

  /* text and lines */
  --color-text: #2A2F3A;
  --color-text-muted: #3A3F4B;
  --color-text-subtle: #5F6472;
  --color-line-input: #C9CCD4;
  --color-line: #E3E5EA;
  --color-divider: #ECEDF1;

  /* state pills: background / text */
  --color-ok-bg: #E3F4EA;      --color-ok: #145C34;
  --color-warn-bg: #FDF1DC;    --color-warn: #8A4100;
  --color-neutral-bg: #EEEFF2; --color-neutral: #3A3F4B;
  --color-bad-bg: #FDECEA;     --color-bad: #8C1D16;  --color-bad-line: #B42318;
  --color-pending-bg: #FDF5E2; --color-pending: #7A4F00;
  --color-info-bg: #ECEBF7;    --color-info: #433F8A;
  --color-new-bg: #E3EFF8;     --color-new: #1F5F8F;
  --color-alert-bg: #FDEFE4;   --color-alert: #8F430B;

  --shadow-card: 0 1px 12px rgba(20, 22, 40, 0.07);
  --shadow-menu: 0 10px 30px rgba(20, 22, 40, 0.18);
}
```

**Shape:**
- Radii are 6–8px in admin, 10–12px in the business workspace, 16–20px on consumer screens, and full for pills and consumer primary buttons.
- Touch targets are at least 44px. Consumer primary buttons are 54–56px tall.

**Breakpoints:**
- Consumer screens are designed at 390px wide and capped at 440–1040px on larger screens.
- Workspace and admin layouts change at three widths:
  - At 1199px, summary cards go to 3 columns.
  - At 1023px, the sidebar becomes a menu button and two-column rows stack.
  - At 640px, header chips hide.

**Colour meaning:** green, amber and red mean states. Don't use them for decoration. Every pill also carries words.

## Check results: design to current statuses

The Result boards show the layout to reuse:
1. A coloured status card with an icon, an uppercase label and a headline.
2. A "what the record shows" card.
3. A compare-with-your-pack checklist.
4. A company notice card.
5. Actions.

The registration states are gone. Map the current `checkResultValues` like this:

| `result` | Design tone | Prototype board to copy |
| --- | --- | --- |
| `RECOGNISED_NOT_SOLD`, `RECOGNISED_JUST_SOLD` | ok (green) | `Result` |
| `RECOGNISED_PREVIOUSLY_SOLD` | warn (amber) | `ResultExpired` |
| `BATCH_OR_PRODUCT_WARNING` (recall) | alert (orange) | `ResultExpired` with alert colours |
| `SUSPICIOUS_ACTIVITY`, `INVALID_IDENTITY` (scanned) | bad (red) | `ResultMismatch` |
| `INVALID_IDENTITY` (typed, D138) | neutral | `ResultNotFound` |
| `CARTON_CODE` | neutral | `ResultNotFound` |
| rate limited | neutral | `ResultLimit` |

The headlines, labels and help text come from the current `CheckResultView` and CLAUDE.md rule 1, not from the prototype.

## Screen map

| Prototype boards | App route / component | Notes |
| --- | --- | --- |
| `Main`, `Mobile` | `app/page.tsx` | Keep the hero video, poster and layout. Rewrite copy for QR codes ("Type the code" instead of "Type number instead"). Keep "Trending checks" only if backed by real aggregate data. |
| `Scan*` | `/check` → `ScanQr` | Same camera frame, dark screen and bottom sheet. QR decoding replaces OCR. |
| `Confirm*` | `/check` → `CheckPack` (typed code) | Use the "type it yourself" layout for the code fallback. |
| `Result*` | `/check`, `/p/[token]` → `CheckResultView` | See the mapping above. The banner text is CLAUDE.md's **DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE**. |
| `Report*` | `ReportConcern` | Same form, photo states and confirmation. Use the current concern categories. |
| `Guide*` | new guide pages | Keep the layout. Rewrite the content to cover where the QR and code are printed and what a check can't prove (a copied QR). Drop the NAFDAC-number guide. |
| `Accounts`, `AccLogin*`, `AccForgot*`, `AccStatus*` | `/register`, `/login`, `/company/register` | Split-screen auth layout; warm "Your company" panel; indigo "What happens next" panel; status timeline. |
| `Supplier`, `SupProducts`, `SupProduct`, `SupSubmissions`, `SupLocations`, `SupAnnouncements*` | `/company` → `CompanyDashboard`, `Catalogue`, `BatchCodes`, `ChangeNotices`, `Announcements` | Use the workspace shell, summary cards and tables. `SupProductNew` had a register lookup, which is dropped: `registration_number` is information only. |
| `SupOrders*`, `Ws*` | `/orders`, `/suppliers` | Hidden while `ORDERS_ENABLED=false`. Keep for later. |
| `Admin*`, `AdminQueue`, `AdminReports*` | `/admin` → `AdminReview` | Admin shell, queues, detail page with decision panel, review history. |
| `AdminLogin*` | staff sign-in | Only if staff sign in separately; otherwise reuse its look on `/login`. |

**Screens the design doesn't cover** need building in the same visual system. These are:
- the merchant page (`/merchant`);
- the simulated POS (`/demo/pos`);
- the unit timeline;
- alerts and evidence;
- allocations and inventory;
- manufacturer stats;
- recalls.

Build them from the workspace shell, summary cards, list tables, status pills, the timeline component and the decision panel.

## Shared components to build first

1. **Demo banner.** Yellow, on every consumer screen; a demo chip elsewhere.
2. **Status pill.** Uses the state colours above and always has words.
3. **Consumer header.** White with a back button. The scan screen is dark.
4. **Bottom action sheet** on scan screens.
5. **Workspace shell.** 256px indigo sidebar with the company block and nav counts. 68px white header with a role chip, demo chip and avatar menu. A drawer below 1023px.
6. **Admin shell.** 270px white sidebar, 72px header with search, a "Demo register" chip and the avatar menu.
7. **Avatar menu.** Name and role, then account links and Log out.
8. **Summary card.** The whole card is a link.
9. **Filter tabs with counts.**
10. **List row or table.** The reference is in mono, with a status pill and an Open or Review button.
11. **Empty, loading and error panels.**
    - Empty: a dashed border and a next step.
    - Loading: a skeleton that stops under reduced motion.
    - Error: a red border and Try again.
12. **Decision panel.** Radio cards, then a reason or message. Confirm shows an outcome card with "Next in queue" and "Change decision".
13. **Timeline and history.**
14. **Radio card.**
15. **Company notice card.** Headed "Message from the company — not reviewed by FoodLens".

## Accessibility

- Use real `<button>`, `<a>` and `<label>` elements.
- Every input has a visible label.
- Announce errors with `role="alert"`.
- Touch targets are at least 44px.
- Under `prefers-reduced-motion`:
  - animations stop;
  - the hero shows its poster instead of the video.

## Working with Claude Code

Restyle screens one area at a time, in the order of `docs/PLAN.md`. For each screen:
1. Open its screenshot in `design/screens/`.
2. Read the matching `design/prototype/*.dc.html` for exact values.
3. Build it with the tokens above.
4. Check the result against the screenshot.
5. Run the tests. Visual changes must not change behaviour or wording rules.
