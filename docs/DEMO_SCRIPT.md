# FoodLens demo script (7 minutes)

A live walkthrough for one presenter: a manufacturer generates codes, a shop till sells a pack, a consumer checks it before and after the sale, a copied code is flagged, and the manufacturer investigates.

Timings are planning estimates. Rehearse once with a clock.

**Say this and only this about what a check shows:** a check shows what has been recorded for a code. A copied QR carries the same code, and FoodLens spots copies by whether the code was sold, where it is checked, how often, and where the stock was sent, not by the QR alone. No QR system catches every copied code. An alert is a signal to review, not a verdict about the pack in anyone's hand.

## Before the audience arrives

1. Set the demo settings once ([README: Run the demo](../README.md#run-the-demo)).
2. Run the reset within 5 hours of the demo, because the seeded "just sold" pack keeps that result for only 5.5 hours:
   ```bash
   node scripts/reset-demo.mjs
   node scripts/dev.mjs
   ```
3. Open these, each signed in where noted:

| Screen | Device | Sign in as | Page |
|---|---|---|---|
| Manufacturer | Laptop, normal window | `seller@demo.foodlens.invalid` | `/company/products` |
| Shop till | Laptop, private window | `shop@demo.foodlens.invalid` | `/demo/pos` |
| Consumer | Phone, or a narrow window | No account | `/check` |

The password for both accounts is `SEED_DEMO_PASSWORD` in `backend/.env`.

**Using a real phone:** a phone camera needs HTTPS, so use the quick tunnel in [README: Test on a phone](../README.md#test-on-a-phone). Stop the tunnel afterwards.

**The pack for this run:** `7DEM ABCD EFGH JKMN PQRS TV10 01`. Keep it ready to paste. It can be sold only once, so a second run needs a reset or another never-sold pack (`...TV10 02`, or `...TV10 06` to `...TV10 10`).

## The walkthrough

### 0:00 The problem (30 seconds)

> "Anyone can copy a QR code. So FoodLens gives every single pack its own code, records what happens to that pack, and lets anyone check it for free with no account. All the companies and products here are fictional, and this is not a regulator service: that's the banner on every screen."

### 0:30 The manufacturer generates codes (75 seconds)

On the manufacturer screen:

1. Under **Sample Groundnut Oil**, batch **DEMO-LOT-201**, open **Codes, labels and allocations**.
2. Enter **12** packs and **6** packs per carton, then press **Generate and download labels**.
3. Open `labels.pdf` from the downloaded zip and show a QR with the code printed under it.

   > "Each code is random. FoodLens keeps only a fingerprint of it, so this file can't be downloaded again."
4. Press **Release all unreleased packs**.
5. Go back to **Products and batches** and open batch **DEMO-LOT-110** of Sample Palm Oil. Scroll to **Allocations**.

   > "This batch was planned for Lagos and Kano, with a few packs for Abuja. Allocations are a plan, and they give FoodLens one more signal."

### 1:45 The consumer checks before buying (45 seconds)

On the phone:

1. At **Demo: check as if from**, choose **Lagos, Lagos**.
2. Choose **Type code**, enter the pack's code, and press **Check this code**.

The result reads **In circulation, not yet sold**.

> "The shopper sees who issued this code, what has been recorded for it, and a tip: scan again after you pay."

### 2:30 The shop till sells it (45 seconds)

On the till screen:

1. Enter the same code and press **Look up**.
2. Press **Confirm payment**.

> "A till records a sale only after payment, through a signed request. FoodLens stores no amount and no card details. No payment happens in this demo."

### 3:15 The consumer checks after buying (30 seconds)

On the phone, press **Check another pack**, enter the code again, and check. **Lagos** stays chosen.

The result reads **Just sold by Demo Corner Shop (fictional), Lagos**. No alert was raised, because a buyer rescanning in the same city is exactly what should happen.

### 3:45 A copied code turns up in Kano (60 seconds)

> "Now suppose someone copied this QR onto another pack in Kano. It carries the same code, so the QR alone can't tell them apart. The records can."

On the phone:

1. Press **Check another pack**.
2. Change the city to **Kano, Kano**.
3. Enter the same code and check.

The result reads **This code may have been copied**. Show the two lists:

- **Possible patterns:** "Checked in places too far apart for the time between checks."
- **Recorded facts:** the pack's history, including the sale in Lagos.

> "This is a warning, not proof about the pack in your hand. Recorded facts and possible patterns are kept apart on purpose."

### 4:45 The manufacturer investigates (90 seconds)

On the manufacturer screen:

1. Open **Alerts** and reload the page. Open the top **Seen too far apart, too quickly** alert.
2. Read the evidence: Lagos and Kano, about 835 km apart, minutes between sightings.
3. Show the **Pack timeline** under it.
4. Press **Mark investigating**.
5. Add a note, for example: "Asked Demo Corner Shop to confirm the till sale."
6. Press **Resolve as suspected copy**.

> "A person makes this decision, and FoodLens records who made it and when. Every rule is a plain, explainable check. There is no score and no AI verdict."

Point at two seeded alerts:

- **More seen than allocated:** Abuja, 5 packs seen against 3 allocated. This one stays on the dashboard and is never shown to buyers.
- **Voided code in use:** a code cancelled before release was checked in Ibadan.

### 6:15 What FoodLens is, and is not (45 seconds)

> "Consumer checks are the core asset: every one adds a place and a time to the record. FoodLens does not say what is inside a pack. It is not a laboratory test or a regulator decision, and no QR system catches every copied code. What it gives a manufacturer is an early, explainable signal, pack by pack."

## Avoid during the demo

- **Don't check the pack in Lagos again after the Kano check.** That is a second jump between the cities, so it raises another alert.
- **Don't leave the city on "Use my real area" in the check steps.** On a laptop with no location data the check has no area, so no travel alert can fire. Through the tunnel it uses your real city, which may not be Lagos.
- **Don't use a pack from the test carton (codes ending `T001` to `T003`) as an ordinary pack.** It is deliberately unreleased and shows a warning.

## If something goes wrong

| What happens | What to do |
|---|---|
| The code was already sold | Use another never-sold pack, or run the reset. |
| The till page says it is not set up, or isn't found | `POS_SECRET_KEY` and `DEMO_POS_ENABLED=true` are missing from `backend/.env`, or `NEXT_PUBLIC_DEMO_POS_ENABLED=true` from `frontend/.env.local`. Set them, run the reset, and restart. |
| There is no city picker on the check page | Set `SIMULATE_LOCATION_ENABLED=true` in `backend/.env` and restart the API. |
| The live step fails | Show the seeded case instead: `...TV10 04` was sold in Lagos and checked in Kano 3 hours later, and its alert is already on the dashboard. |
| "Just sold" shows as "Already recorded as sold" on a seeded pack | More than 5.5 hours have passed since the reset. Run it again. A pack sold live is not affected. |

## Other cases to show if asked

The full list of codes is in the [README](../README.md#demo-codes).

| Question | Code ending | Result |
|---|---|---|
| What if a shop refunds a pack and resells it? | `1005` | Just sold, with no alert. The first sale stays in the record. |
| What does an unknown code show? | `X001` | Not recognised. It is also part of a burst of 20 unknown codes from Port Harcourt, which only admins see. |
| What about an expired batch? | `E001` | A recognised result with an amber expiry warning. |
| What if a carton QR is scanned? | `C001` | "This is a carton code; check the individual pack." |
