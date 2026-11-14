import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./lib/api";

export const useLakes = () => useQuery({ queryKey: ["lakes"], queryFn: api.lakes, staleTime: 60_000 });
export const useIndex = () => useQuery({ queryKey: ["index"], queryFn: api.index, staleTime: Infinity });
export const useLake = (id: string | null, running = false) =>
  useQuery({ queryKey: ["lake", id], queryFn: () => api.lake(id!), enabled: !!id, refetchInterval: running ? 4000 : false });
export const useLive = (id: string | null) =>
  useQuery({ queryKey: ["live", id], queryFn: () => api.live(id!), enabled: !!id, staleTime: 180_000, retry: 0 });

/** Compare selection (max 6) persisted in localStorage and shared via a window event. */
export function useCompareIds(): [string[], (id: string) => void, (...ids: string[]) => void] {
  const read = (): string[] => { try { return JSON.parse(localStorage.getItem("compare") ?? "[]"); } catch { return []; } };
  const [ids, setIds] = useState<string[]>(read);
  useEffect(() => {
    const h = () => setIds(read());
    window.addEventListener("compare-changed", h);
    return () => window.removeEventListener("compare-changed", h);
  }, []);
  const write = (v: string[]) => { localStorage.setItem("compare", JSON.stringify(v)); window.dispatchEvent(new Event("compare-changed")); };
  return [ids, (id) => { if (!ids.includes(id) && ids.length < 6) write([...ids, id]); }, (...rm) => write(ids.filter((x) => !rm.includes(x)))];
}
