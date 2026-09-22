const STEPS = [
  { title: "Scrape", desc: "Every day, listings are pulled from Bikroy across 3 cities and 5 brands." },
  { title: "Clean", desc: "Titles like \"Samsung A32 4/64 good cond\" are parsed into brand, model, storage." },
  { title: "Store", desc: "Every listing is kept in a database — including price history over time." },
  { title: "Train", desc: "An XGBoost model retrains daily, learning what each phone should cost." },
  { title: "Score", desc: "Every listing gets a fair price estimate and a 0-100 deal score." },
];

export default function HowItWorks() {
  return (
    <div className="page">
      <div className="page__header">
        <h1>How BikroyLens Works</h1>
        <p className="page__subtitle">
          No manual pricing, no guesswork — a fully automated pipeline that runs itself, every day.
        </p>
      </div>

      <div className="card">
        <span className="section-eyebrow">The Pipeline</span>
        <div className="pipeline">
          {STEPS.map((step, i) => (
            <div className="pipeline__item" key={step.title} style={{ display: "flex", alignItems: "center" }}>
              <div className="pipeline__step">
                <span className="pipeline__num">{i + 1}</span>
                <div className="pipeline__title">{step.title}</div>
                <div className="pipeline__desc">{step.desc}</div>
              </div>
              {i < STEPS.length - 1 && <span className="pipeline__arrow">→</span>}
            </div>
          ))}
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <span className="section-eyebrow">The Problem</span>
          <p className="prose">
            Bikroy pricing is entirely seller-set — there's no benchmark. A "Samsung A32, good condition" at
            ৳15,000 could be a steal, or it could be overpriced junk. Buyers have no way to know without
            manually comparing dozens of listings themselves.
          </p>
        </div>
        <div className="card">
          <span className="section-eyebrow">The Solution</span>
          <p className="prose">
            BikroyLens builds a real price benchmark from actual market data — thousands of real listings,
            updated daily — and shows a Deal Score next to every phone so the price speaks for itself.
          </p>
        </div>
      </div>

      <div className="card">
        <span className="section-eyebrow">Under the Hood</span>
        <table className="table">
          <tbody>
            <tr>
              <td className="muted" style={{ width: 180 }}>
                Scraper
              </td>
              <td>Python + Scrapy, running on a daily local scheduler</td>
            </tr>
            <tr>
              <td className="muted">Database</td>
              <td>PostgreSQL (Supabase) — every listing, every day, kept as price history</td>
            </tr>
            <tr>
              <td className="muted">Normalizer</td>
              <td>Rule-based regex + lookup dictionaries — deliberately not ML, titles are formulaic enough to parse reliably</td>
            </tr>
            <tr>
              <td className="muted">Model</td>
              <td>XGBoost, trained on log(price) to handle the wide ৳15k–1.3M range fairly</td>
            </tr>
            <tr>
              <td className="muted">API</td>
              <td>FastAPI, serving predictions straight from the database</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="card" style={{ background: "var(--accent-soft)", border: "1px solid rgba(30,111,92,0.25)" }}>
        <span className="section-eyebrow">Deal Score, explained</span>
        <p className="prose" style={{ marginBottom: 0 }}>
          <code className="mono">deal_score = 100 − ((price − fair_price) / fair_price × 100)</code>, clipped
          to 0-100. A phone priced well below its predicted fair value scores close to 100 (a great deal); a
          phone priced above fair value scores low.
        </p>
      </div>
    </div>
  );
}
