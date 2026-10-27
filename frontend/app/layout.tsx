import type { Metadata } from "next";
import { IBM_Plex_Mono, Open_Sans, Poppins } from "next/font/google";
import { DemoDataBanner } from "@/components/DemoDataBanner";
import { SiteHeader } from "@/components/SiteHeader";
import { Providers } from "./providers";
import "./globals.css";

// Fonts and weights from the design (design/README.md); at most three weights each.
const poppins = Poppins({
  variable: "--font-poppins",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

const openSans = Open_Sans({
  variable: "--font-open-sans",
  subsets: ["latin"],
  weight: ["400", "600", "700"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
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
      className={`${poppins.variable} ${openSans.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-paper text-ink">
        <DemoDataBanner />
        <Providers>
          <SiteHeader />
          {children}
        </Providers>
      </body>
    </html>
  );
}
