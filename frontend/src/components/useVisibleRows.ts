import { useLayoutEffect, useState, type RefObject } from "react";

/** Height that shows exactly the first `rows` children of a list; the rest scroll. */
export function useVisibleRows(ref: RefObject<HTMLElement>, rows: number, deps: unknown[]) {
  const [maxHeight, setMaxHeight] = useState<number | undefined>(undefined);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const items = Array.from(el.children) as HTMLElement[];
    if (items.length <= rows) { setMaxHeight(undefined); return; }
    const last = items[rows - 1];
    setMaxHeight(last.offsetTop - el.offsetTop + last.offsetHeight + 2);
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return maxHeight === undefined ? {} : { maxHeight, overflowY: "auto" as const };
}
