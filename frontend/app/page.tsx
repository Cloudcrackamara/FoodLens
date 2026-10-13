import Link from "next/link";
import { Camera, ScrollText, Search } from "lucide-react";
import { Lens } from "@/components/brand/Lens";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const steps = [
  { icon: Search, title: "Find the number", text: "Look for the NAFDAC or SON number and the batch (LOT) number on the pack." },
  { icon: Camera, title: "Type or scan it", text: "Scanning reads the numbers on your phone. No photo is uploaded." },
  { icon: ScrollText, title: "Compare the record", text: "See the matching record in the simulated register and compare it with the pack." },
];

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      {/* Hero: the large lens breathes in the background, faded so the text stays clear (D105). */}
      <section className="relative isolate overflow-hidden border-b border-border bg-card">
        <div
          aria-hidden="true"
          className="hero-lens absolute inset-0 -z-10 flex items-center justify-center md:justify-end"
        >
          <Lens
            hero
            className="size-[34rem] shrink-0 translate-x-[12%] sm:size-[40rem] md:size-[46rem] md:translate-x-[18%]"
          />
        </div>
        <div className="mx-auto flex w-full max-w-5xl flex-col justify-center gap-5 px-4 py-16 sm:py-20 md:min-h-[30rem]">
          <h1 className="text-5xl font-bold leading-none text-primary sm:text-6xl">FoodLens</h1>
          <p className="max-w-xl text-lg font-medium sm:text-xl">
            Check the NAFDAC or SON registration number printed on a food pack against a simulated
            register, and find suppliers whose profiles FoodLens has reviewed for this demo.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button asChild size="lg">
              <Link href="/check">Check a registration number</Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/suppliers">Find suppliers</Link>
            </Button>
          </div>
        </div>
      </section>

      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 py-10 sm:py-14">
        <section aria-labelledby="how-heading" className="flex flex-col gap-4">
          <h2 id="how-heading" className="text-2xl font-bold">How a check works</h2>
          <ol className="grid gap-3 sm:grid-cols-3">
            {steps.map(({ icon: Icon, title, text }, index) => (
              <li key={title}>
                <Card className="h-full gap-2 p-4">
                  <span
                    aria-hidden="true"
                    className="flex size-10 items-center justify-center rounded-full bg-secondary text-primary"
                  >
                    <Icon className="size-5" />
                  </span>
                  <p className="font-semibold">
                    {index + 1}. {title}
                  </p>
                  <p className="text-sm text-muted-foreground">{text}</p>
                </Card>
              </li>
            ))}
          </ol>
        </section>

        <Card className="gap-0">
          <CardContent className="pt-4 sm:pt-5">
            <h2 className="mb-3 text-xl font-bold">What a lookup can and cannot tell you</h2>
            <ul className="list-disc space-y-1.5 pl-5 marker:text-coral">
              <li>It shows whether the number matches a record in a simulated, fictional register.</li>
              <li>A matching number cannot rule out a number copied onto another pack.</li>
              <li>It is not a laboratory test and does not check the package in your hand.</li>
              <li>It is not NAFDAC, SON, or any other regulator&apos;s service or decision.</li>
            </ul>
          </CardContent>
        </Card>

        <p className="text-sm text-muted-foreground">
          Software engineering capstone prototype. All companies, products, and credentials shown
          are fictional.
        </p>
      </div>
    </main>
  );
}
