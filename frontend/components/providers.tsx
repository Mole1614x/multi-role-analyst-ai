"use client";

import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export function Providers({children}: {children: React.ReactNode}) {
  const [client] = useState(() => new QueryClient({defaultOptions: {queries: {retry: false, staleTime: 5_000}}}));
  useEffect(() => {
    if (localStorage.getItem("theme") === "dark") document.documentElement.dataset.theme = "dark";
  }, []);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
