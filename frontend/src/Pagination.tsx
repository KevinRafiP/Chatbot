import { useState, type FormEvent } from "react";

type PaginationProps = {
  page: number;
  pageCount: number;
  onChange: (page: number) => void;
  label?: string;
};

type PageItem = number | "gap-start" | "gap-end";

// The page numbers to show. Few pages: all of them. Near either end: the first three and the last three.
// Otherwise the first page, the pages around the current one, and the last; "⋯" stands for the pages in between
function pageItems(page: number, pageCount: number): PageItem[] {
  if (pageCount <= 7) {
    return Array.from({ length: pageCount }, (_, index) => index + 1);
  }
  if (page <= 2 || page >= pageCount - 1) {
    return [1, 2, 3, "gap-start", pageCount - 2, pageCount - 1, pageCount];
  }
  const items: PageItem[] = [1];
  // a gap is only worth it when it hides two pages or more
  if (page - 1 > 3) items.push("gap-start");
  else for (let number = 2; number < page - 1; number++) items.push(number);
  items.push(page - 1, page, page + 1);
  if (page + 1 < pageCount - 2) items.push("gap-end");
  else for (let number = page + 2; number < pageCount; number++) items.push(number);
  items.push(pageCount);
  return items;
}

// Page buttons for any long list: « first, ‹ previous, the page numbers, › next, » last.
// Pressing "⋯" turns it into a box where a page number can be typed
export function Pagination({ page, pageCount, onChange, label = "Halaman" }: PaginationProps) {
  const [typing, setTyping] = useState<PageItem | null>(null);

  function go(next: number) {
    const target = Math.min(Math.max(Math.round(next), 1), pageCount);
    if (target !== page) onChange(target);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = Number(new FormData(event.currentTarget).get("page"));
    if (Number.isFinite(value) && value > 0) go(value);
    setTyping(null);
  }

  return (
    <nav className="pagination" aria-label={label}>
      <button type="button" className="page-step" onClick={() => go(1)} disabled={page <= 1} aria-label="Halaman pertama">
        «
      </button>
      <button type="button" className="page-step" onClick={() => go(page - 1)} disabled={page <= 1} aria-label="Halaman sebelumnya">
        ‹
      </button>
      {pageItems(page, pageCount).map((item) =>
        typeof item === "number" ? (
          <button
            type="button"
            key={item}
            className={item === page ? "active" : ""}
            aria-current={item === page ? "page" : undefined}
            onClick={() => go(item)}
          >
            {item}
          </button>
        ) : typing === item ? (
          // noValidate: a number past the last page is moved to the last page instead of being refused
          <form key={item} className="page-jump" onSubmit={submit} noValidate>
            <input
              name="page"
              type="number"
              inputMode="numeric"
              min={1}
              max={pageCount}
              placeholder="No."
              aria-label={`Ketik nomor halaman, 1 sampai ${pageCount}`}
              autoFocus
              onBlur={(event) => event.currentTarget.form?.requestSubmit()}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  // Escape closes only this box, not the window around the list
                  event.stopPropagation();
                  event.currentTarget.value = "";
                  setTyping(null);
                }
              }}
            />
          </form>
        ) : (
          <button type="button" key={item} className="page-gap" onClick={() => setTyping(item)} aria-label="Ketik nomor halaman">
            ⋯
          </button>
        ),
      )}
      <button type="button" className="page-step" onClick={() => go(page + 1)} disabled={page >= pageCount} aria-label="Halaman berikutnya">
        ›
      </button>
      <button type="button" className="page-step" onClick={() => go(pageCount)} disabled={page >= pageCount} aria-label="Halaman terakhir">
        »
      </button>
    </nav>
  );
}
