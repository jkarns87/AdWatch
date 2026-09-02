import Link from "next/link";

const CTA = process.env.NEXT_PUBLIC_AUTH_PROVIDER === "xano" ? "/login" : "/";

const STEPS = [
  { n: "01", t: "Watch", d: "Add competitor domains and the keywords you care about. AdWatch pulls every live creative from the Google Ads Transparency Center, the paid block on your keywords, and Google Trends demand — through SerpApi, on a schedule." },
  { n: "02", t: "Diff", d: "Every run is compared to the last. Creatives launched or dropped, new advertisers on your keyword, position shifts, demand spikes, breakout queries — typed events with severity, not screenshots." },
  { n: "03", t: "Explain", d: "An AI analyst reads only the structured diff and writes what happened, why it matters, and two or three concrete actions with effort and urgency. No invented numbers." },
  { n: "04", t: "Alert & report", d: "High-severity insights land in your team chat or inbox. One click generates a CFO-ready spend & risk brief or a marketing action brief as PDF, Word or Markdown." },
];

const FEATURES = [
  ["Creative surveillance", "Every text, image and video ad each competitor is running, with first- and last-shown dates and links to the source."],
  ["Keyword share of voice", "Who is bidding on your terms, in what position, top or bottom — tracked across runs so you see who is gaining."],
  ["Demand radar", "Interest over time and rising related queries for the category, so you catch a breakout before the auction gets expensive."],
  ["Change feed", "Nine typed change kinds with severity. First run is a silent baseline, so nothing screams on day one."],
  ["AI analyst", "Structured diff in, strict JSON out. Insights cluster by competitor or keyword and read like a Monday-morning brief."],
  ["Executive reports", "Audience-tailored one-click briefs for finance and marketing — PDF, DOCX, Markdown — with KPIs, actions, and charts."],
];

const PLANS = [
  { name: "Free", price: "$0", blurb: "1 watchlist · 2 competitors · 3 keywords · daily samples · in-app alerts · 250 searches/mo", cta: "Start free" },
  { name: "Team", price: "$79", blurb: "3 watchlists · 5 competitors · 10 keywords · SERP sampled twice a day · Slack/Teams/Discord/email · reports · 3,000 searches/mo", cta: "Start Team", hot: true },
  { name: "Agency", price: "$299", blurb: "10 watchlists · 10 competitors · 15 keywords · client workspaces · white-label reports · 15,000 searches/mo", cta: "Talk to us" },
];

export default function Landing() {
  return (
    <div className="pb-16">
      {/* hero */}
      <section className="pt-10 pb-12 text-center">
        <div className="inline-block badge kind mb-4">competitive intelligence for paid search</div>
        <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight leading-tight">
          Know what your competitors did<br className="hidden sm:block" /> <span style={{ color: "var(--accent)" }}>before your standup.</span>
        </h1>
        <p className="muted mt-5 max-w-2xl mx-auto text-lg leading-relaxed">
          AdWatch watches every Google ad your competitors run, every keyword they bid on, and every shift in demand — then tells you what changed, why it matters, and what to do next.
        </p>
        <div className="mt-7 flex items-center justify-center gap-3">
          <Link href={CTA} className="btn btn-primary text-base px-5 py-2.5">Start watching — free</Link>
          <a href="#how" className="btn text-base px-5 py-2.5">How it works</a>
        </div>
        <div className="muted text-xs mt-4">No ad-account access needed. Built on public data. Set up in three minutes.</div>
      </section>

      {/* product strip */}
      <section className="panel p-4 sm:p-6 grid gap-3 sm:grid-cols-3">
        {[
          ["HIGH", "brewdrop.example appeared at #1 on “cold brew delivery”", "new advertiser on keyword"],
          ["HIGH", "RoastNest went from 7 to 11 active creatives (+57%)", "creative surge"],
          ["HIGH", "Interest in “cold brew delivery” is 1.7× its 4-week average in the Bay Area", "demand spike"],
        ].map(([sev, text, kind]) => (
          <div key={text} className="panel-2 p-3">
            <div className="flex items-center gap-2"><span className="badge sev-high">{sev}</span><span className="badge kind">{kind}</span></div>
            <div className="text-sm mt-2">{text}</div>
          </div>
        ))}
        <div className="sm:col-span-3 panel-2 p-3 text-sm">
          <span className="badge kind mr-2">AI analyst</span>
          “A new entrant took the top slot on your highest-intent query while local demand for it doubled. Ship a cold-brew landing page this week and add a “cold brew delivery san francisco” ad group; no tracked competitor owns the breakout yet.”
        </div>
      </section>

      {/* how it works */}
      <section id="how" className="mt-16">
        <h2 className="text-2xl font-semibold tracking-tight">How it works</h2>
        <div className="grid gap-4 mt-5 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s) => (
            <div key={s.n} className="panel p-4">
              <div className="muted text-xs font-mono">{s.n}</div>
              <div className="font-medium text-lg mt-1">{s.t}</div>
              <p className="muted text-sm mt-2 leading-relaxed">{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* features */}
      <section className="mt-16">
        <h2 className="text-2xl font-semibold tracking-tight">What you get</h2>
        <div className="grid gap-4 mt-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(([t, d]) => (
            <div key={t} className="panel-2 p-4">
              <div className="font-medium">{t}</div>
              <p className="muted text-sm mt-1.5 leading-relaxed">{d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* why now */}
      <section className="mt-16 panel p-6">
        <h2 className="text-2xl font-semibold tracking-tight">Why this replaces the weekly ritual</h2>
        <p className="muted mt-3 leading-relaxed max-w-3xl">
          Today a paid-search team opens a competitor’s transparency page, searches its own keywords in incognito, checks a trends chart and pastes screenshots into a deck — once a week, if someone remembers. Incumbent intelligence suites cost hundreds of dollars a seat and still hand you a report, not a signal. AdWatch is the monitor with the analyst attached: change events, in your chat, with a recommended action, on public data — nothing to connect.
        </p>
      </section>

      {/* pricing */}
      <section className="mt-16">
        <h2 className="text-2xl font-semibold tracking-tight">Pricing</h2>
        <div className="grid gap-4 mt-5 sm:grid-cols-3">
          {PLANS.map((p) => (
            <div key={p.name} className="panel p-5" style={p.hot ? { borderColor: "var(--accent)" } : {}}>
              <div className="flex items-baseline justify-between"><div className="font-medium text-lg">{p.name}</div><div className="text-2xl font-semibold">{p.price}<span className="muted text-sm font-normal">/mo</span></div></div>
              <p className="muted text-sm mt-2 leading-relaxed">{p.blurb}</p>
              <Link href={CTA} className={`btn mt-4 inline-block ${p.hot ? "btn-primary" : ""}`}>{p.cta}</Link>
            </div>
          ))}
        </div>
        <div className="muted text-xs mt-3">Every SerpApi call is one search; plans map limits to a monthly search budget — see the Usage page. Full numbers in docs/COST_MODEL.md.</div>
      </section>

      <footer className="muted text-xs mt-16 border-t pt-6" style={{ borderColor: "var(--line)" }}>
        Data: SerpApi (Google Ads Transparency Center, Google Search, Google Trends). Control plane: Xano. Analysis: AdWatch diff engine + Claude.
      </footer>
    </div>
  );
}
