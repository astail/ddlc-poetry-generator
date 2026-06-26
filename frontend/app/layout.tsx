import type { Metadata } from "next";
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
      <body>{children}</body>
    </html>
  );
}
