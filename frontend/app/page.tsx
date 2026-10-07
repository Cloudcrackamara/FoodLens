export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-12">
      <h1 className="text-3xl font-bold">FoodLens</h1>
      <p className="text-lg">
        Check a packaged food product and batch number against the FoodLens demonstration
        database, and find suppliers whose profiles FoodLens has reviewed for this demo.
      </p>
      <section className="rounded-md border border-zinc-300 p-4 dark:border-zinc-700">
        <h2 className="mb-2 font-semibold">What a lookup can and cannot tell you</h2>
        <ul className="list-disc space-y-1 pl-5">
          <li>It shows whether a matching record exists in fictional demonstration data.</li>
          <li>It is not a laboratory test and does not check the package in your hand.</li>
          <li>It is not NAFDAC, SON, or any other regulator&apos;s service or decision.</li>
        </ul>
      </section>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Software engineering capstone prototype. All companies, products, and credentials shown
        are fictional.
      </p>
    </main>
  );
}
