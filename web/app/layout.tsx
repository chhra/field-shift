import type { Metadata, Viewport } from "next";
import "@fontsource-variable/geologica";
import "./globals.css";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";

export const metadata: Metadata = {
  title: {
    default: "Field Shift — crop rotations from NASA Earth observations",
    template: "%s · Field Shift",
  },
  description:
    "See what NASA satellites know about your field, and compare crop rotations that build soil and resilience.",
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <SiteHeader />
        <main id="main">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
