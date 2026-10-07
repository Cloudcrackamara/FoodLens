import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { Providers } from "./providers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
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
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <DemoDataBanner />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
