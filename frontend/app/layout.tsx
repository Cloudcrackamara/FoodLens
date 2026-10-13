import type { Metadata } from "next";
import { Suspense } from "react";
import { Fraunces, Geist, Geist_Mono } from "next/font/google";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { SiteHeader, SiteHeaderFallback } from "@/components/SiteHeader";
import { Providers } from "./providers";
import "./globals.css";

// next/font downloads these at build time and serves them from this site: no runtime request
// to Google, so nothing about the visitor leaves FoodLens (D106).
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-fraunces",
  subsets: ["latin"],
  weight: ["600", "700"],
});

export const metadata: Metadata = {
  title: "FoodLens (demo)",
  description:
    "Capstone prototype: look up simulated product and batch records. Demo data only, not an official regulator service.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${fraunces.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <DemoDataBanner />
        <Providers>
          <Suspense fallback={<SiteHeaderFallback />}>
            <SiteHeader />
          </Suspense>
          {children}
        </Providers>
      </body>
    </html>
  );
}
