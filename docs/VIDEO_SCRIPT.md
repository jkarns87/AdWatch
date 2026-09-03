# AdWatch — 3-minute demo video script (screenshare + voice-over)

439 words of narration = 2:56 at 150 wpm. Timecodes include click pauses and one read-aloud, so real runtime ≈ 3:15.
Record on **your own account** (real SerpApi data), not `demo@adwatch.dev`.

## Questions to settle before recording

1. Onboarding: can you stop at the review screen without creating a duplicate watchlist? If not, use a throwaway company or cancel at review. The script never confirms.
2. How long does "Claude reads the site" take? Row 2b covers 12s; recovery line below if longer.
3. Keywords tab: does it show the paid block **and** Trends? If not, cut the Trends sentence in 3b.
4. Changes tab: does it show a total? "Seventy-five so far" is the workspace figure; recovery line if different.
5. Real watchlist counts: 6a is written per-competitor / per-keyword so it's right at any count.
6. Collect now duration on production: 6b covers 18s; filler line below if longer.

## Script

### Section 1 — The problem, over the dashboard · 52 words · 0:00–0:21

| [timecode] On screen | Narration |
|---|---|
| **[0:00]** `/` Dashboard already loaded. Cursor still on the four stat cards. | This is AdWatch. Every paid-search team does the same weekly ritual. Open competitors' Google Ads Transparency pages. Search your keywords in incognito. Check Google Trends. Paste it into a deck. |
| **[0:12]** Slow scroll to **Recent alerts**; two or three HIGH cards in frame. | That is a snapshot. It never says what changed. AdWatch is the monitor and the analyst. These alerts are this week's output. |

### Section 2 — Onboarding · 41 words · 0:22–0:41

| [timecode] On screen | Narration |
|---|---|
| **[0:22]** `/onboarding`. Type company name + website. | Setup starts with a company name and a website. Nothing else. |
| **[0:29]** Submit. Review screen with proposed category, keywords, competitors, brand assets. Cursor down the proposal. **Do not confirm.** | Claude reads the site. It proposes the category, the keywords, the likely competitors, and your own brand assets. You review and confirm. A watchlist takes a minute, not an afternoon. |

### Section 3 — The watchlist · 47 words · 0:43–1:03

| [timecode] On screen | Narration |
|---|---|
| **[0:43]** `/watchlists/[id]` Specialty Coffee — Bay Area → **Competitors** tab. Hover a creative so first/last-shown dates are in frame. | My real watchlist, specialty coffee. Competitors tab. Every creative each tracked competitor runs right now, with first and last shown dates. |
| **[0:53]** **Keywords** tab. Cursor over the paid-block table, then the trend line. | Keywords tab. The paid block per keyword. Who is bidding, what position, top or bottom. Google Trends interest and rising queries. All public data, through SerpApi. |

### Section 4 — The diff · 53 words · 1:04–1:25

| [timecode] On screen | Narration |
|---|---|
| **[1:04]** **Changes** tab. Hold at the top of the list. | Here is the hard part. Every run is diffed against the last. The diff engine emits typed events, each with a severity. |
| **[1:13]** Scroll slowly. Pause on a HIGH row, then on a `new advertiser` row. | A creative launched or dropped. A new advertiser on one of our keywords. A position shift. A demand spike. A breakout query. Seventy-five so far. Facts about what changed, not screenshots. |

### Section 5 — The Claude brief · 37 words + read-aloud · 1:26–1:49

| [timecode] On screen | Narration |
|---|---|
| **[1:26]** **Insights** tab. Cursor on the top card: severity, run number, confidence, then **Why it matters**. | Claude reads only the structured diff. It cannot invent numbers. Per cluster it writes what happened, why it matters, and two or three actions, each with effort and urgency. Now, this week, or monitor. |
| **[1:41]** Cursor on the first action box, then click **evidence** and leave it open. | Here is one. **[Read the first action box aloud, word for word, including its urgency and effort tags.]** |

### Section 6 — Live collect, the SerpApi proof · 83 words · 1:50–2:23

| [timecode] On screen | Narration |
|---|---|
| **[1:50]** Click **Collect now**. Keep the header (last run, searches used) in frame. | The live run. Collect now hits SerpApi in real time. One Transparency Center call per competitor. One Search and two Trends calls per keyword. Then the diff, then the analyst. |
| **[2:02]** Run in progress. Don't move the mouse. | SerpApi is the sensor. Three engines feed the product. Without structured, real-time access to that public data there is no diff. Without the diff there is nothing for the AI to analyze. The AI experience is only as good as the freshness of the signal. |
| **[2:20]** Run finishes. Cursor to the header's run number and searches-used. | Done. New run, and the searches it spent. |

### Section 7 — Cost discipline · 29 words · 2:24–2:36

| [timecode] On screen | Narration |
|---|---|
| **[2:24]** `/usage`. Cursor on searches-used-vs-budget, then between the two projected figures. Point, don't read numbers. | Every SerpApi call is one search. Every run records what it spent. The month, projected two ways. Everything every six hours, versus the plan cadence. About five-fold, same alerts. |

### Section 8 — Xano build story and close · 97 words · 2:37–3:17

| [timecode] On screen | Narration |
|---|---|
| **[2:37]** `/settings/integrations`. Destinations with per-destination minimum severity in frame. | The Xano story. We replaced the weekly manual check across an expensive incumbent suite and a spreadsheet. Retrospective, per seat, blind to change. |
| **[2:46]** Hold. | Claude did the planning, the diff engine, the analyst, the onboarding site analysis, and the XanoScript. Three people, about twenty-two hours. |
| **[2:54]** Cursor down the destination rows. | The whole control plane is Xano. Auth, workspaces, alert preferences, fan-out with a delivery log, password reset, schedulers. Twenty-six XanoScript files, pushed from the repo. Without that, a bespoke service and a token story. |
| **[3:09]** Back to `/` Dashboard. Stop moving. End on the stat cards. | FastAPI and Postgres underneath, Next.js on top, on Fly. AdWatch. Know what your competitors did before your standup. |

## Pre-flight checklist

- Signed in to **your own account**; workspace name visible in the nav.
- Theme chosen (Light / Dark / System) and left alone.
- Tabs pre-loaded in order: `/`, `/onboarding` (empty form), `/watchlists/[id]` (Specialty Coffee — Bay Area), `/usage`, `/settings/integrations`. SerpApi key card = VALID, Claude card = metered.
- Onboarding inputs decided; tested once; form reloaded empty. Question 1 settled.
- Current run number + searches used noted so the change after Collect now is obvious.
- SerpApi quota checked. One Collect now ~10 min before recording (warm cache, fast run), then hands off. An insight card exists for section 5.
- Slack/mail/notifications closed, Do Not Disturb on, one browser window, no bookmarks/extensions bar, zoom 100–110%, 1920×1080 or 1440×900.
- Mic check on the 6b line. Water. Script on a second screen.

## Recovery lines

| Section | If… | Say |
|---|---|---|
| 1 | Alerts list is short / only MEDIUM | "These alerts are the most recent runs' output. Severity is set by the diff engine, not by hand." |
| 2 | Proposal takes > 12s | "Claude is reading the site now. Category, keywords, competitors, brand assets, all from the public site." Then row 2b. |
| 2 | Proposal looks thin | "The proposal is a starting point. Everything here is editable before you confirm." |
| 3 | Slow tab / creative without dates | "Creatives come straight from the Transparency Center, dates included when Google exposes them." |
| 4 | Count isn't 75 | Replace "Seventy-five so far" with "Dozens across a dozen runs." |
| 4 | No HIGH near the top | "Severity is per event. High is a new advertiser on our keyword, a surge, or a demand spike." |
| 5 | Top card is low-confidence / fallback | Use the next card. "Confidence is reported per insight, and low confidence is shown, not hidden." |
| 6 | Run > 18s | After 6b: "Each engine is a separate HTTP call. The run records every one of them against the budget." Then 6c. |
| 6 | Run fails | "That run didn't complete. Here is the previous run from this morning." (Better: stop and re-record — this is the SerpApi proof.) |
| 6 | Zero new changes | "No new changes this run. That is correct behavior. The diff only fires on real deltas." |
| 7 | Figures differ from expected | Never read numbers. "The gap between the two projections is the plan cadence doing its job." |
| 8 | Integrations page empty | "Destinations are rows in the control plane, each with its own threshold. Add one, no code." |

## Cuts

- **3:00 flat:** drop row **3a** and the first sentence of **8d**. Section 3 opens on the Keywords tab.
- **2:00 cut:** drop rows **1a, 3a, 3b, 5b, 6c, 7, 8d** → 303 words, ≈2:10 with clicks; open on 1b over the dashboard. For a hard 2:00 also drop **4a**. Both sponsor beats survive (6a+6b SerpApi; 8a+8b+8c Xano).
