"use client";

import { useState } from "react";
import { ChartView } from "@/components/common";
import type { Chart, DashboardSnapshot } from "@/lib/api";

function groupField(chart:Chart) {
  if (!["bar","line","pie"].includes(chart.type)) return null;
  if (chart.dimension) return chart.dimension;
  // Earlier chart snapshots record the grouping column in the chart method.
  if (chart.x==="group") return chart.method.match(/ grouped by (.+)$/)?.[1]??null;
  return chart.x??null;
}

export function DashboardCharts({chart}: {chart:DashboardSnapshot["chart"]}) {
  const [group,setGroup]=useState("");
  const panels="panels" in chart?chart.panels:[chart];
  const field=groupField(panels[0]);
  const shared=panels.length>1&&field&&panels.every(panel=>groupField(panel)===field);
  const groups=shared?[...new Set(panels.flatMap(panel=>panel.rows.map(row=>JSON.stringify(row[panel.x??"group"]))))].filter(Boolean):[];
  return <>
    {shared&&groups.length>0&&<label>Filter all charts by {field}
      <select value={group} onChange={event=>setGroup(event.target.value)}>
        <option value="">All groups</option>
        {groups.map(value=><option key={value} value={value}>{String(JSON.parse(value)??"Missing")}</option>)}
      </select></label>}
    {panels.length===1?<ChartView chart={panels[0]} filter/>:
      <div className="two-columns">{panels.map((panel,index)=><div className="stack" key={index}>
        {panel.title&&<h3>{panel.title}</h3>}
        <ChartView chart={shared&&group?{...panel,rows:panel.rows.filter(row=>JSON.stringify(row[panel.x??"group"])===group)}:panel} filter/>
      </div>)}</div>}
  </>;
}
