"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./SiteChrome.module.css";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/field", label: "Field" },
  { href: "/how-it-works", label: "How it works" },
];

/** Three crop bands of a farming year — the product's core picture, as a mark. */
export function BrandMark() {
  return (
    <svg className={styles.mark} viewBox="0 0 24 24" aria-hidden="true">
      <rect x="2" y="4" width="14" height="4.5" rx="1.6" fill="var(--tone-poaceae)" />
      <rect x="17" y="4" width="5" height="4.5" rx="1.6" fill="var(--tone-bare)" />
      <rect x="2" y="9.75" width="5" height="4.5" rx="1.6" fill="var(--tone-bare)" />
      <rect x="8" y="9.75" width="14" height="4.5" rx="1.6" fill="var(--tone-fabaceae)" />
      <rect x="2" y="15.5" width="9" height="4.5" rx="1.6" fill="var(--green)" />
      <rect x="12" y="15.5" width="10" height="4.5" rx="1.6" fill="var(--tone-poaceae-alt)" />
    </svg>
  );
}

export function SiteHeader() {
  const path = usePathname();
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  return (
    <header className={styles.header}>
      <div className={`page ${styles.bar}`}>
        <Link href="/" className={styles.brand}>
          <BrandMark />
          <span>Field Shift</span>
        </Link>
        <nav aria-label="Main">
          <ul className={styles.nav}>
            {NAV.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={styles.link}
                  aria-current={active(item.href) ? "page" : undefined}
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className={styles.footer}>
      <div className={`page ${styles.footInner}`}>
        <p>
          Built for the NASA Space Apps Challenge 2026. Field Shift supports a farmer&apos;s
          judgement and their agronomist&apos;s — it does not replace them.
        </p>
        <p className={styles.footMeta}>
          Earth observations: Sentinel-2, NASA POWER, GPM IMERG, SMAP, GRACE.
        </p>
      </div>
    </footer>
  );
}
