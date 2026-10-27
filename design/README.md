# FoodLens design reference

This folder holds the approved FoodLens UI design. Use it to make the app look and behave like the prototype.

**Precedence:** this folder decides how screens **look**. `CLAUDE.md` and `docs/DECISIONS.md` (D137 onwards) decide **scope, rules and wording**. The prototype was designed during the earlier registration-lookup phase, so its copy and some flows are out of date. Where they disagree, CLAUDE.md and DECISIONS.md win. Never copy prototype wording without checking it against CLAUDE.md rule 1.

## What's in here

| Path | What it is | How to use it |
| --- | --- | --- |
| `screens/*.png` | 103 screenshots, one per prototype board, full page | The visual source of truth. Open the matching screenshot before building or restyling a screen. |
| `prototype/*.dc.html` | The prototype source for each board | Read it for exact spacing, colours, radii, SVG icons and component structure. It is template HTML (`{{holes}}`, `<sc-if>`, `<sc-for>`, a `renderVals()` script), not runnable app code. Port the markup to React and Tailwind; don't import these files. |
| `prototype/canvas.json` | Board list with titles and sizes | Board titles name the screen and state, e.g. `Result · not found`. |
| `assets/` | Hero videos and posters, scan-ready animation, scan photo | Copy what you use into `frontend/public/`. Sizes are listed below. |

Wrapper boards (for example `SupOrderAccepted`) just show another board in a set state. The screenshot of the wrapper shows that state.

Screenshots were rendered with Poppins, Open Sans and IBM Plex Mono. In the app, load them with `next/font/google`.

### Asset sizes (checked 26 Oct 2026)

No file is over 10 MB.

| File | Size |
| --- | --- |
| `foodlens-hero-16x9.mp4` | 2.74 MB |
| `foodlens-scan-ready.webp` | 2.09 MB |
| `foodlens-hero-9x16.mp4` | 0.99 MB |
| `foodlens-scan-photo.jpg` | 164 KB |
| `foodlens-hero-16x9-poster.jpg` | 131 KB |
| `foodlens-hero-9x16-poster.jpg` | 46 KB |

## Approved wording wins

All consumer-facing text currently in the code (`check.py`, `/check`, the scanner, `/p`, the result page, report concern and the home page) was approved by the founder on 26 Oct 2026. Restyling changes markup and classes only, never that text. The prototype's sample text is never used where approved wording exists.

### Design text never to copy

The prototype was written for the registration lookup. This text breaks CLAUDE.md rules and must not reach the app, even when the board's layout is reused:

| Text in the design | Boards | Why not |
| --- | --- | --- |
| "Na original o!" | `Main` | Rule 1: "original". Use the tagline **"Check am before you buy!"** instead (founder, 26 Oct 2026). |
| "Whether the pack in your hand is the original" | `Guide` | Rule 1: "original". |
| "NOT A SAFETY TEST" chip | `Main` | Safety wording. Use the chip **"NOT A LAB TEST"** instead (founder, 26 Oct 2026). |
| "It is not a safety test" | `Main` | Safety wording; not approved. Ask the founder before using any form of it. |
| "Demo data — not an official NAFDAC or SON service" | every consumer board | Rule 2: the banner text is **DEMO DATA — NOT AN OFFICIAL REGULATOR SERVICE**. |
| "This number matches an active registration", "Active registration", "This registration has expired", "This number is registered to a different product", "We couldn't find this number in the register", "What the register shows", "Agency: NAFDAC (simulated record)", "Your pack vs the register" | `Result`, `ResultExpired`, `ResultMismatch`, `ResultNotFound`, `ResultTablet`, `ResultMismatchDesktop` | Rule 3: `registration_number` is never checked against a register. |
| "We need the NAFDAC number to check", "Fit the NAFDAC number inside the box", "NAFDAC Reg. No." pack art | `ResultInsufficient`, `Result`, `Scan`, `Confirm*` | Rule 3; checks read the FoodLens QR or code. |
| "Type the registration number", "NAFDAC or SON registration number", batch field | `Confirm`, `ConfirmTyped` | Rule 3; the typed fallback is the pack's code. |
| "Food registration checker", "checks the registration number … against a register", "matches an active record" | `Main`, `Mobile` | Rule 3. |
| "It has not yet been verified" | `Report` | "Verified" wording; keep the current `ReportConcern` text. |
| "Now NAFDAC approved and 100% safe", "NAFDAC approved and safe for your family" | `Supplier`, `AdminQueue` | Sample of a blocked announcement. Use only as test input for the blocked state, never as content. |
| "Approved · demo-reviewed profile" and other "Approved" labels | `Accounts`, `Admin*` | Allowed only with the qualifier that it is a FoodLens demo review, not NAFDAC or SON approval (rule 5). |
| "active registration" in the supplier directory | `Wholesaler`, `Supplier` | Rule 3. Orders are hidden anyway. |

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

The registration states are gone. `ResultExpired`, `ResultMismatch`, `ResultNotFound`, `ResultInsufficient` and `ConfirmTyped` come from the registration design: reuse their **layout only**, none of their text. Map the current `checkResultValues` like this (agreed with the founder on 26 Oct 2026):

| `result` | Design tone | Board for layout | Notes |
| --- | --- | --- | --- |
| `RECOGNISED_NOT_SOLD` | ok (green) | `Result` | Check icon. The details card shows the recorded product, batch and facts, not "What the register shows". |
| `RECOGNISED_JUST_SOLD` | ok (green) | `Result` | As above. The "I've bought this" button sits below the status card. |
| `RECOGNISED_PREVIOUSLY_SOLD` | warn (amber) | `ResultExpired` | Clock icon. The advice goes in the grey note box. |
| `BATCH_OR_PRODUCT_WARNING` (recall) | alert (orange, `--color-alert*`) | No board. `ResultExpired` layout in alert colours | The recall notice is a solid alert-coloured card directly under the status card, not the dashed company-message card. |
| `SUSPICIOUS_ACTIVITY` | bad (red, solid status card) | `ResultMismatch` | "Possible patterns" takes the compare panel's place, with the red border. |
| `INVALID_IDENTITY` (scanned) | bad (red) | `ResultMismatch` | No product card. A "What you can do" list. |
| `INVALID_IDENTITY` (typed, D138) | neutral (grey) | `ResultNotFound` | "What you entered" shows only the last 4 characters. Look-alike tips follow the normalisation (O/0, I/L/1). |
| `CARTON_CODE` | info (indigo) | `ResultInsufficient` | An instruction, not a failure. The illustration shows where the pack's own QR sits; the main button scans a pack. |
| rate limited | neutral | `ResultLimit` | Countdown. |
| typed-code entry | — | `ConfirmTyped` | One code field; no batch field. |

The headlines, labels and help text come from the current `check.py` and `CheckResultView`, which the founder approved, not from the prototype.

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
