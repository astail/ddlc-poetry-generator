import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "DDLC Poetry Generator",
  description: "Unofficial, non-commercial DDLC fan poem generator",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja">
      <body>
        <nav className="nav">
          <span className="brand">🌸 DDLC Poetry</span>
          <Link href="/">Generate</Link>
          <Link href="/gallery">Gallery</Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
