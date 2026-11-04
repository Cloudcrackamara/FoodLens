import type { CSSProperties, ReactNode } from "react";

/**
 * The scan picture. Swap in a photo by pointing this at "/scan-hero.webp" (design/README.md).
 * The picture keeps the QR at its centre, where the viewfinder corners sit.
 */
const HERO_SRC = "/scan-hero.svg";

/**
 * Where the phone screen's QR (x 192–308, y 242–358 of scan-hero.svg's 500 × 600) sits in each
 * frame with object-cover. Recompute if the picture changes.
 */
const QR_BOX: Record<"ready" | "reading", CSSProperties> = {
  ready: { left: "38.4%", top: "40.3%", width: "23.2%", height: "19.3%" },
  reading: { left: "38.1%", top: "40.3%", width: "23.8%", height: "19.3%" },
};

/**
 * The rounded camera frame of the Scan board (Scan.dc.html): 20px radius on #22279A.
 * "ready" is 5 / 6; "reading" is the board's 1131 / 1391.
 */
export function ScanFrame({ aspect = "ready", children }: { aspect?: "ready" | "reading"; children: ReactNode }) {
  return (
    <div
      className={`relative w-full max-w-[440px] overflow-hidden rounded-[20px] bg-[#22279A] [container-type:inline-size] ${
        aspect === "ready" ? "aspect-[5/6]" : "aspect-[1131/1391]"
      }`}
    >
      {children}
    </div>
  );
}

/** The yellow scan line of Scan.dc.html; `fl-scanline` runs continuously, `fl-sweep` with the cards. */
function ScanLine({ motion }: { motion: "fl-scanline" | "fl-sweep" }) {
  return (
    <div
      className={motion}
      style={{
        position: "absolute",
        left: "4%",
        right: "4%",
        top: motion === "fl-sweep" ? "4%" : "6%",
        height: "0.7cqw",
        minHeight: 2,
        borderRadius: 2,
        background: "#FFE58A",
        boxShadow: "0 0 2.4cqw 0.8cqw rgba(255,196,47,0.75)",
      }}
    />
  );
}

/** White viewfinder corners in the middle of the frame, with the scan line running inside. */
export function Viewfinder({ className = "w-[32%]" }: { className?: string }) {
  const corner = "absolute size-[26%] border-white";
  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute left-1/2 top-1/2 aspect-square -translate-x-1/2 -translate-y-1/2 ${className}`}
    >
      <div className="absolute inset-0 overflow-hidden rounded-[14px]">
        <ScanLine motion="fl-scanline" />
      </div>
      <span className={`${corner} left-0 top-0 rounded-tl-[14px] border-l-4 border-t-4`} />
      <span className={`${corner} right-0 top-0 rounded-tr-[14px] border-r-4 border-t-4`} />
      <span className={`${corner} bottom-0 left-0 rounded-bl-[14px] border-b-4 border-l-4`} />
      <span className={`${corner} bottom-0 right-0 rounded-br-[14px] border-b-4 border-r-4`} />
    </div>
  );
}

function HeroImage() {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- a static picture; swapping the file must stay one line
    <img
      src={HERO_SRC}
      alt="A phone scanning the QR code on a food pack"
      className="absolute inset-0 block size-full object-cover"
    />
  );
}

/** Glow round the QR (fl-glow, Scan.dc.html reading state). */
function QrGlow({ frame }: { frame: "ready" | "reading" }) {
  return (
    <div className="fl-glow" aria-hidden="true" style={{ position: "absolute", ...QR_BOX[frame], borderRadius: "3cqw" }} />
  );
}

/** The ready-to-scan picture: a phone scanning the QR on a pack, breathing and glowing. */
export function ScanHero() {
  return (
    <ScanFrame>
      <div className="fl-breathe" style={{ position: "absolute", inset: 0 }}>
        <HeroImage />
        <QrGlow frame="ready" />
        <Viewfinder />
      </div>
    </ScanFrame>
  );
}

/**
 * The reading step after a QR is read (Scan.dc.html, reading state): the picture breathes, the
 * QR glows, a line sweeps it, then three cards pop in on the board's 6.5s cycle.
 */
export function ScanReadingHero({ last4 }: { last4: string }) {
  return (
    <ScanFrame aspect="reading">
      <div className="fl-breathe" style={{ position: "absolute", inset: 0 }}>
        <HeroImage />
        <QrGlow frame="reading" />
        <div aria-hidden="true" style={{ position: "absolute", ...QR_BOX.reading, overflow: "hidden", borderRadius: "2cqw" }}>
          <ScanLine motion="fl-sweep" />
        </div>
        {/* Card 1 (fl-pop): green pill. */}
        <div
          className="fl-pop"
          style={{
            position: "absolute",
            left: "19.5%",
            top: "10.4%",
            width: "37%",
            height: "9%",
            transform: "rotate(-4deg)",
            display: "flex",
            alignItems: "center",
            gap: "1.4cqw",
            padding: "0 2.6cqw",
            boxSizing: "border-box",
            borderRadius: 999,
            background: "#1B7A45",
            color: "#FFFFFF",
            fontFamily: "var(--font-heading)",
            fontSize: "2.9cqw",
            fontWeight: 600,
            whiteSpace: "nowrap",
            boxShadow: "0 1cqw 3cqw rgba(0,0,0,0.3)",
          }}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="#FFFFFF"
            strokeWidth="2.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            style={{ width: "4cqw", height: "4cqw", flex: "none" }}
          >
            <path d="M5 12.5l4.5 4.5L19 7.5" />
          </svg>
          QR code read
        </div>
        {/* Card 2 (fl-sheet): white sheet with a handle and the blinking cursor. */}
        <div
          className="fl-sheet"
          style={{
            position: "absolute",
            left: "23%",
            top: "60%",
            width: "46%",
            transform: "rotate(-4deg)",
            padding: "1.8cqw 2.6cqw 2.4cqw",
            boxSizing: "border-box",
            borderRadius: "4cqw",
            background: "#FFFFFF",
            color: "#16143D",
            boxShadow: "0 2cqw 5cqw rgba(0,0,0,0.35)",
          }}
        >
          <div
            aria-hidden="true"
            style={{ width: "7cqw", height: "0.7cqw", margin: "0 auto 1.4cqw", borderRadius: "1cqw", background: "#D5D8DF" }}
          />
          <p
            style={{
              margin: 0,
              fontFamily: "var(--font-heading)",
              fontSize: "4.2cqw",
              fontWeight: 600,
              lineHeight: 1.2,
            }}
          >
            Checking this code…
            <span className="fl-blink" aria-hidden="true" style={{ color: "#C8372D" }}>
              |
            </span>
          </p>
        </div>
        {/* Card 3 (fl-batch): small white card. */}
        <div
          className="fl-batch"
          style={{
            position: "absolute",
            left: "58%",
            top: "44%",
            width: "38%",
            padding: "2.4cqw 3cqw",
            boxSizing: "border-box",
            borderRadius: "3cqw",
            background: "#FFFFFF",
            color: "#16143D",
            boxShadow: "0 2cqw 5cqw rgba(0,0,0,0.3)",
          }}
        >
          <p style={{ margin: 0, fontSize: "3.2cqw", fontWeight: 600, lineHeight: 1.3 }}>
            Code ending <span style={{ fontFamily: "var(--font-mono)" }}>{last4}</span>
          </p>
        </div>
      </div>
    </ScanFrame>
  );
}
