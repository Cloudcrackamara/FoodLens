"use client";

import { useState, type FormEvent } from "react";
import { describeError } from "@/lib/api";
import {
  useCompanyAnnouncements,
  usePostAnnouncement,
  useWithdrawAnnouncement,
} from "@/lib/announcements";
import { useProducts } from "@/lib/catalogue";
import { formatDate } from "@/lib/format";
import { buttonClass } from "@/lib/ui";
import { ErrorPanel } from "@/components/ui/Panels";

const inputClass = "min-h-[46px] rounded-[10px] border border-line-input bg-white px-3 py-2 text-base text-ink";

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
      <h2 id="announcements-heading" className="font-heading text-[17px] font-semibold text-ink">Announcements</h2>
      <p className="text-sm text-text-muted">
        Short messages shown to consumers when they check your product, for example about new
        packaging. They go live straight away, are labelled &quot;Message from the company — not
        reviewed by FoodLens&quot;, and never change product details. You can warn about fake or
        counterfeit versions, but you cannot say the product is &quot;safe&quot; or &quot;unsafe&quot;.
      </p>

      {announcements.isError && <ErrorPanel>{describeError(announcements.error)}</ErrorPanel>}
      <ul className="flex flex-col gap-2">
        {announcements.data?.map((item) => (
          <li key={item.announcement_id} aria-label={item.title} className="flex flex-col gap-1 rounded-[10px] border border-line bg-white p-3.5">
            <p className="font-semibold">{item.title}</p>
            <p>{item.message}</p>
            <p className="text-sm text-text-subtle">
              {item.product_name} · posted {formatDate(item.created_at.slice(0, 10))} · {item.status === "LIVE" ? "Live" : "Hidden"}
            </p>
            {item.status === "LIVE" && (
              <button type="button" disabled={withdraw.isPending} onClick={() => withdraw.mutate(item.announcement_id)} className="self-start text-sm font-semibold text-brand-dark underline disabled:text-text-subtle">
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
        {problem && <p role="alert" className="font-semibold text-bad">{problem}</p>}
        {postAnnouncement.isError && <p role="alert" className="font-semibold text-bad">{describeError(postAnnouncement.error)}</p>}
        <button type="submit" disabled={postAnnouncement.isPending} className={`self-start ${buttonClass("primary", "sm")}`}>
          Post announcement
        </button>
      </form>
    </section>
  );
}
