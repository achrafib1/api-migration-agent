import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "API Migration Agent | Evidence-first migrations",
  description:
    "Review verified OpenAPI changes, approve an evidence-backed migration plan, and validate isolated patches.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
