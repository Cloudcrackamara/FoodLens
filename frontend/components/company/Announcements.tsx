"use client";

import { useState, type FormEvent } from "react";
import { describeError } from "@/lib/api";
import {
  useCompanyAnnouncements,
  usePostAnnouncement,
  useWithdrawAnnouncement,
} from "@/lib/announcements";
import { useProducts } from "@/lib/catalogue";
import { formatDate } from "@/lib/lookup";

const inputClass = "rounded-md border border-zinc-400 px-3 py-2 dark:border-zinc-600 dark:bg-zinc-900";

export function Announcements({ companyId }: { companyId: string }) {
  const products = useProducts(companyId);
  const announcements = useCompanyAnnouncements(companyId);
  const postAnnouncement = usePostAnnouncement(companyId);
  const withdraw = useWithdrawAnnouncement(companyId);
  const [productId, setProductId] = useState("");
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [problem, setProblem] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!productId || !title.trim() || !message.trim()) {
      setProblem("Choose a product and enter a title and message");
      return;
    }
    setProblem(null);
    postAnnouncement.mutate(
      { productId, title: title.trim(), message: message.trim() },
      {
        onSuccess: () => {
          setTitle("");
          setMessage("");
        },
      },
    );
  }

  return (
    <section aria-labelledby="announcements-heading" className="flex flex-col gap-4">
      <h2 id="announcements-heading" className="text-lg font-semibold">Announcements</h2>
      <p className="text-sm text-zinc-700 dark:text-zinc-300">
        Short messages shown to consumers when they check your product, for example about new
        packaging. They go live straight away, are labelled &quot;Message from the company — not
        reviewed by FoodLens&quot;, and never change product details. You can warn about fake or
        counterfeit versions, but you cannot say the product is &quot;safe&quot; or &quot;unsafe&quot;.
      </p>

      {announcements.isError && <p role="alert">{describeError(announcements.error)}</p>}
      <ul className="flex flex-col gap-2">
        {announcements.data?.map((item) => (
          <li key={item.announcement_id} aria-label={item.title} className="flex flex-col gap-1 rounded-md border border-zinc-300 p-3 dark:border-zinc-700">
            <p className="font-semibold">{item.title}</p>
            <p>{item.message}</p>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              {item.product_name} · posted {formatDate(item.created_at.slice(0, 10))} · {item.status === "LIVE" ? "Live" : "Hidden"}
            </p>
            {item.status === "LIVE" && (
              <button type="button" disabled={withdraw.isPending} onClick={() => withdraw.mutate(item.announcement_id)} className="self-start text-sm underline disabled:opacity-60">
                Withdraw
              </button>
            )}
          </li>
        ))}
      </ul>

      <form onSubmit={handleSubmit} noValidate aria-label="Post an announcement" className="flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          <span className="font-medium">Product</span>
          <select value={productId} onChange={(event) => setProductId(event.target.value)} className={inputClass}>
            <option value="">Choose…</option>
            {products.data?.map((product) => (
              <option key={product.product_id} value={product.product_id}>{product.name} ({product.product_code})</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-medium">Title</span>
          <input value={title} maxLength={80} onChange={(event) => setTitle(event.target.value)} className={inputClass} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-medium">Message</span>
          <textarea value={message} maxLength={500} onChange={(event) => setMessage(event.target.value)} className={inputClass} />
        </label>
        {problem && <p role="alert" className="text-red-700 dark:text-red-400">{problem}</p>}
        {postAnnouncement.isError && <p role="alert" className="text-red-700 dark:text-red-400">{describeError(postAnnouncement.error)}</p>}
        <button type="submit" disabled={postAnnouncement.isPending} className="self-start rounded-md bg-zinc-900 px-4 py-2 font-semibold text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900">
          Post announcement
        </button>
      </form>
    </section>
  );
}
