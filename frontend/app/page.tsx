import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { buttonClass, cardTitleClass } from "@/lib/ui";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-12">
      <h1 className="font-heading text-3xl font-bold">FoodLens</h1>
      <p className="text-lg text-text">
        Every pack gets its own QR code, issued by the manufacturer. Anyone can check a pack for
        free, with no account, to see what has been recorded for that code: whether it is in
        circulation or sold, where, and any recall.
      </p>
      <Link
        href="/check"
        className={`self-start ${buttonClass("primary", "lg")}`}
      >
        Check a pack
      </Link>
      <Card>
        <h2 className={`${cardTitleClass} mb-2`}>What a check can and cannot tell you</h2>
        <ul className="list-disc space-y-1 pl-5 text-text">
          <li>
            It shows recorded facts about the code: issued by the manufacturer, in circulation,
            sold, or recalled.
          </li>
          <li>
            A copied QR carries the same code. FoodLens spots copies by whether the code was sold,
            where it is checked, how often, and where the stock was sent, not by the QR alone. No
            QR system catches every copied code.
          </li>
          <li>
            It is not a laboratory test, and it is not NAFDAC, SON, or any other regulator&apos;s
            service or decision.
          </li>
        </ul>
      </Card>
      <p className="text-sm text-text-subtle">
        Demonstration prototype. All companies, products, and codes shown are fictional.
      </p>
    </main>
  );
}
