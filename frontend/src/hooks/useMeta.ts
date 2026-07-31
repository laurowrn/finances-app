import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useUsers() {
  return useQuery({ queryKey: ["users"], queryFn: api.users });
}

export function useCategories() {
  return useQuery({ queryKey: ["categories"], queryFn: api.categories });
}

export function userMap(users?: { id: string; name: string }[]): Record<string, string> {
  return Object.fromEntries((users ?? []).map((u) => [u.id, u.name]));
}

export function categoryMap(cats?: { id: string; name: string }[]): Record<string, string> {
  return Object.fromEntries((cats ?? []).map((c) => [c.id, c.name]));
}
