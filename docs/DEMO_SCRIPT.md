# Demo script — 3 minutes, stage-safe

Same script for the video (add 30s of build-story voiceover at the end for Xano) and the Top-5 stage demo.

**Setup before walking on:** deployed dashboard open on the watchlist page; Slack/Discord channel with the webhook visible on a second window; `collect` run 5 minutes earlier so SerpApi's cache is warm; local `docker compose` running as fallback; phone hotspot ready. Never type a brand name into anything on stage — the watchlist is pre-configured.

---

**[0:00–0:25] The problem.**
"Every paid-search team does this once a week: open a competitor's Google Ads Transparency page, search your own keywords in incognito, check Google Trends, screenshot it all into a deck. It's slow, it's a snapshot, and it never tells you what *changed*. AdWatch is the monitor plus the analyst."

**[0:25–0:55] The watchlist.** *(scroll the overview)*
"One watchlist for the meal-kit category: three competitors, five keywords. Every card here is live public data pulled through SerpApi — these are the creatives each competitor is running right now, with first- and last-shown dates. This table is the paid block on our keywords — who's bidding, what position, top or bottom. And that's category demand over the last twelve weeks."

**[0:55–1:35] The change feed.** *(click Changes)*
"Here's the part nobody has. Every run is diffed against the last. Overnight: competitor two launched four new video creatives; a brand we don't track appeared in position one on our highest-value keyword; and 'meal kit for two' broke out as a rising query. Each of those is a typed event with severity — not a screenshot."

**[1:35–2:20] The analyst.** *(click the top Insight)*
"The AI analyst reads the structured diff — only the diff, it can't invent numbers — and writes this: what happened, why it matters, and three actions with effort and urgency. 'Launch a two-person plan landing page this week; the query is breaking out and no tracked competitor owns it yet.' That's a Monday-morning brief, generated at 6 AM."

**[2:20–2:45] Live.** *(click Collect now)*
"Let's run it live." *(wait ≤ 30s — narrate: 'three ad-transparency calls, five search calls, ten trends calls, diffed, analyzed')* "New run, [N] changes, one new insight — and it just hit our team channel." *(show the webhook message)*

**[2:45–3:00] Close.**
"Sensor: SerpApi. Control plane: Xano. Data plane: containers on any cloud. Built in 22 hours by three people. AdWatch — know what your competitors did before your standup."

---

## If something breaks

- **Collect times out on stage:** "Conference Wi-Fi — here's the run from ten minutes ago" → open the latest run's changes. Move on. Never retry live more than once.
- **Deployed URL dead:** switch to local Docker on the laptop; same seed data.
- **Webhook doesn't show:** skip it; the insight card is the payoff.
- **Judge asks "how is this different from an incumbent suite?":** "They give you a report; we give you a *change event with a recommended action*, in your chat, for a fraction of the seat price — and it's built on public data, so there's nothing to connect."
- **"What about your own campaign data?":** "Next step — import your own campaign reports to overlay spend against competitor moves. Own-account APIs need vendor approval, which is why v1 is public-data-first."
