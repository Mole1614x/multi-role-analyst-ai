"use client";

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Job } from "@/lib/api";
import type { Context } from "@/components/project";

export const finished = (status:string) => ["completed","failed","canceled"].includes(status);

export function useActiveJob(context:Context,id:string) {
  const {base,project}=context;
  const cache=useQueryClient();
  const key=["job",project.id,id];
  const query=useQuery({queryKey:key,queryFn:()=>api<Job>(`${base}/jobs/${id}`),enabled:!!id,
    refetchInterval:query=>query.state.data && finished(query.state.data.status) ? false : 1600});
  const terminal=!!query.data && finished(query.data.status);
  useEffect(() => {
    if (!id || terminal) return;
    const channel = new EventSource(`/api${base}/jobs/${id}/events`);
    channel.onmessage = event => {
      try {
        const update:Job=JSON.parse(event.data);
        cache.setQueryData(["job",project.id,id],update);
        if (finished(update.status)) channel.close();
      } catch {channel.close();}
    };
    channel.onerror=()=>channel.close();
    return ()=>channel.close();
  },[base,cache,id,project.id,terminal]);
  useEffect(()=>{
    if(terminal) {
      void cache.invalidateQueries({queryKey:["jobs",project.id]});
      if(query.data?.kind==="import") void cache.invalidateQueries({queryKey:["datasets",project.id]});
    }
  },[cache,project.id,query.data?.kind,terminal]);
  return query;
}
