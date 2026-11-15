import type { Metadata } from "next";
import { Disclosure } from "@/components/Disclosure";
import type { HowItWorks } from "@/lib/types";
import styles from "./how.module.css";

export const metadata: Metadata = { title: "How it works" };
export const dynamic = "force-dynamic";

const API = process.env.FIELD_SHIFT_API_URL ?? "http://127.0.0.1:8000";

const CONTENTS = [
  ["pipeline", "From satellite to options"],
  ["inputs", "The five questions"],
  ["goals", "The six goals"],
  ["numbers", "From answers to numbers"],
  ["sources", "Data sources"],
  ["rules", "Decision rules"],
  ["risks", "Benefits and local risks"],
  ["glossary", "Glossary"],
] as const;

async function load(): Promise<HowItWorks | null> {
  try {
    const res = await fetch(`${API}/api/meta/how-it-works`, { cache: "no-store" });
    return res.ok ? ((await res.json()) as HowItWorks) : null;
  } catch {
    return null;
  }
}

export default async function HowItWorksPage() {
  const d = await load();

  return (
    <div className={`page ${styles.page}`}>
      <header className={styles.head}>
        <h1 className={styles.title}>How it works</h1>
        <p className={styles.lede}>
          Field Shift turns NASA and partner Earth observations into rotation options you can
          check against local knowledge. Five plain farm questions, six goals in everyday
          language, then the methods behind them.
        </p>
      </header>

      {!d ? (
        <p className={styles.offline}>
          The methods are served by the Field Shift API, which isn’t reachable right now. Start
          it with <code>uvicorn api.main:app</code> and reload this page.
        </p>
      ) : (
        <div className={styles.layout}>
          <nav className={styles.toc} aria-label="On this page">
            <ol>
              {CONTENTS.map(([id, label]) => (
                <li key={id}>
                  <a href={`#${id}`}>{label}</a>
                </li>
              ))}
            </ol>
          </nav>

          <div className={styles.body}>
            <section id="pipeline" className={styles.section}>
              <h2>From satellite to options</h2>
              <ol className={styles.pipeline}>
                {d.pipeline.map((step, i) => (
                  <li key={i}>
                    <span className={`${styles.pipeNum} num`}>{i + 1}</span>
                    <p>{step}</p>
                  </li>
                ))}
              </ol>
            </section>

            <section id="inputs" className={styles.section}>
              <h2>The five questions</h2>
              <p className={styles.sectionLead}>
                We ask what a farmer can answer. Satellites fill in the rest.
              </p>
              <ol className={styles.inputs}>
                {d.inputs.map((q) => (
                  <li key={q.title}>
                    <h3>{q.title}</h3>
                    <p>{q.body}</p>
                    {q.options && (
                      <ul className={styles.chips} aria-label={`${q.title}: answers`}>
                        {q.options.map((o) => (
                          <li key={o}>{o}</li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ol>
            </section>

            <section id="goals" className={styles.section}>
              <h2>The six goals</h2>
              <p className={styles.sectionLead}>
                You put these in order on the Field and UK pages. Each one is measured from
                field data, not opinion.
              </p>
              <div className={styles.goals}>
                {d.goals.map((g) => (
                  <article key={g.key} className={styles.goal}>
                    <h3>
                      <i style={{ background: `var(--goal-${g.key})` }} aria-hidden="true" />
                      {g.label}
                    </h3>
                    <p className={styles.goalHint}>{g.hint}</p>
                    <dl>
                      <dt>In plain words</dt>
                      <dd>{g.plain}</dd>
                      <dt>How we measure it</dt>
                      <dd>{g.measured}</dd>
                    </dl>
                  </article>
                ))}
              </div>
            </section>

            <section id="numbers" className={styles.section}>
              <h2>From answers to numbers</h2>
              <h3 className={styles.h3}>Goal order</h3>
              <p className={styles.text}>{d.goal_order_note}</p>

              <h3 className={styles.h3}>Soil water</h3>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <caption className="sr-only">Soil water by soil type</caption>
                  <thead>
                    <tr>
                      <th scope="col">Soil</th>
                      <th scope="col">Water it holds (mm per m)</th>
                      <th scope="col">How fast rain soaks in (mm per hour)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.soil_table.rows.map((r) => (
                      <tr key={r.soil}>
                        <th scope="row">{r.soil}</th>
                        <td className="num">{r.awc_mm_per_m}</td>
                        <td className="num">{r.infiltration_mm_h}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="caption">{d.soil_table.source}</p>

              <h3 className={styles.h3}>Some irrigation</h3>
              <p className={styles.text}>{d.irrigation_note}</p>
            </section>

            <section id="sources" className={styles.section}>
              <h2>Data sources</h2>
              {d.sources_through && (
                <p className={styles.sectionLead}>
                  Demo field data runs through {d.sources_through}.
                </p>
              )}
              <ul className={styles.sources}>
                {d.sources.map((s) => (
                  <li key={`${s.name}-${s.purpose}`}>
                    <p className={styles.srcPurpose}>{s.purpose}</p>
                    <p className={styles.srcName}>
                      {s.link ? (
                        <a href={s.link} target="_blank" rel="noreferrer">
                          {s.name}
                        </a>
                      ) : (
                        s.name
                      )}
                    </p>
                    <p className={styles.srcMeta}>
                      <code>{s.access}</code>
                      <span>{s.resolution}</span>
                    </p>
                  </li>
                ))}
              </ul>
            </section>

            <section id="rules" className={styles.section}>
              <h2>Decision rules</h2>
              <p className={styles.sectionLead}>
                Options are compared with your rotation, never shown as scores. These rules decide
                which role each option gets.
              </p>
              <ul className={styles.rules}>
                {d.thresholds.map((t) => (
                  <li key={t.name}>
                    <strong>{t.name}.</strong> {t.meaning}
                  </li>
                ))}
              </ul>
              <div className={styles.disclosure}>
                <Disclosure summary="Exact values, for reviewers">
                  <dl className={styles.values}>
                    {d.thresholds.map((t) => (
                      <div key={t.name}>
                        <dt>{t.name}</dt>
                        <dd className="num">{t.value}</dd>
                      </div>
                    ))}
                  </dl>
                </Disclosure>
              </div>
            </section>

            <section id="risks" className={styles.section}>
              <h2>Benefits and local risks</h2>
              <p className={styles.text}>{d.benefits_note}</p>
              <h3 className={styles.h3}>Checked on every option</h3>
              <ul className={styles.risks}>
                {d.standard_risks.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </section>

            <section id="glossary" className={styles.section}>
              <h2>Glossary</h2>
              <dl className={styles.glossary}>
                {d.glossary.map((g) => (
                  <div key={g.term}>
                    <dt>{g.term}</dt>
                    <dd>{g.definition}</dd>
                  </div>
                ))}
              </dl>
            </section>

            <section className={styles.section}>
              <h2>Team and AI use</h2>
              <p className={styles.text}>
                Built for the NASA Space Apps Challenge 2026. AI assisted the implementation (see
                AI_USAGE.md in the repository). Agronomic decisions stay with farmers and their
                advisers.
              </p>
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
