import Link from "next/link";

export default function NotFound() {
  return (
    <div className="page" style={{ paddingTop: 80, paddingBottom: 80 }}>
      <h1 style={{ fontSize: 36, fontWeight: 620, letterSpacing: "-0.03em" }}>Page not found</h1>
      <p style={{ marginTop: 12, color: "var(--muted)", maxWidth: "42ch" }}>
        That link is not part of Field Shift.
      </p>
      <p style={{ marginTop: 24 }}>
        <Link className="btn btn-primary" href="/">
          Back to Home
        </Link>
      </p>
    </div>
  );
}
