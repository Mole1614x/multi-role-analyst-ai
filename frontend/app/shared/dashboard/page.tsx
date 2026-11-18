"use client";

import { useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { DashboardCharts } from "@/components/dashboard-charts";
import { api, type DashboardSnapshot } from "@/lib/api";

function subscribe(listener:()=>void) {
  window.addEventListener("hashchange",listener);
  return ()=>window.removeEventListener("hashchange",listener);
}

export default function SharedDashboard() {
  const token=useSyncExternalStore(subscribe,()=>window.location.hash.slice(1),()=>"");
  const valid=/^[A-Za-z0-9_-]{43}$/.test(token);
  const dashboard=useQuery({
    queryKey:["shared-dashboard",token], enabled:valid, retry:false,
    queryFn:()=>api<DashboardSnapshot>("/public/dashboard",{headers:{Authorization:`Bearer ${token}`}}),
  });
  return <main className="panel stack">
    {dashboard.data?<><h1>{dashboard.data.title}</h1><DashboardCharts chart={dashboard.data.chart}/></>:
      <p role="status">{valid&&dashboard.isPending?"Opening dashboard…":"This dashboard link is unavailable."}</p>}
  </main>;
}
