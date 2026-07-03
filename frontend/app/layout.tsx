import type { Metadata } from "next";
import "./globals.css";
import { LangProvider } from "./i18n";
import SiteNav from "./site-nav";

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
        <LangProvider>
          <SiteNav />
          {children}
        </LangProvider>
      </body>
    </html>
  );
}
