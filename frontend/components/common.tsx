"use client";

import { useState } from "react";
import { ArrowUpRight, Database } from "lucide-react";
import { CartesianGrid, Bar, BarChart, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer,
  Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import type { Chart, Dataset, Row, Role, Version } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function Heading({title, description, children}: {title:string;description?:string;children?:React.ReactNode}) {
  return <div className="view-heading"><div><h1>{title}</h1>{description && <p>{description}</p>}</div>{children}</div>;
}
export function Empty({title, description, children}: {title:string;description:string;children?:React.ReactNode}) {
  return <div className="empty"><span className="icon-tile"><Database size={20}/></span><h3>{title}</h3><p>{description}</p>{children}</div>;
}
export function ErrorNote({error}: {error:unknown}) {
  if (!error) return null;
  return <p className="error" role="alert">{error instanceof Error ? error.message : String(error)}</p>;
}
export function Table({columns, rows}: {columns:string[];rows:Row[]}) {
  const [page,setPage] = useState(0);
  const size = 10, index = Math.min(page, Math.max(0, Math.ceil(rows.length / size) - 1));
  if (!columns.length) return <p className="muted">No columns to display.</p>;
  const formatted = (value:Row[string]) => value === null || value === undefined ? "—" :
    typeof value === "number" ? new Intl.NumberFormat(undefined,{maximumFractionDigits:8}).format(value) : String(value);
  return <div className="table-frame"><div className="table-scroll"><table><thead><tr>{columns.map(c=><th key={c}>{c}</th>)}</tr></thead>
    <tbody>{rows.slice(index*size,index*size+size).map((row,i)=><tr key={i}>{columns.map(c=><td key={c}>{formatted(row[c])}</td>)}</tr>)}
      {!rows.length && <tr><td colSpan={columns.length}>No matching rows.</td></tr>}</tbody></table></div>
    {rows.length>size && <div className="table-pagination"><span>{index*size+1}–{Math.min((index+1)*size,rows.length)} of {rows.length}</span>
      <Button type="button" variant="outline" disabled={index===0} onClick={()=>setPage(index-1)}>Previous</Button>
      <Button type="button" variant="outline" disabled={(index+1)*size>=rows.length} onClick={()=>setPage(index+1)}>Next</Button></div>}
  </div>;
}

export function RoleChooser({roles, selected, onChange, readOnly=false}: {
  roles:Role[];selected:string[];onChange:(roles:string[])=>void;readOnly?:boolean;
}) {
  return <div className="role-grid">{roles.map(role=><label key={role.id} className={`role-option ${selected.includes(role.id)?"role-selected":""}`}>
    <span><input type="checkbox" checked={selected.includes(role.id)} disabled={readOnly}
      onChange={e=>onChange(e.target.checked ? [...selected,role.id] : selected.filter(r=>r!==role.id))}/>
      <b>{role.name}</b></span><small>{role.template}</small></label>)}</div>;
}

export function VersionSelect({datasets,value,onChange,optional=false,label="Dataset version"}: {
  datasets:Dataset[];value:string;onChange:(value:string)=>void;optional?:boolean;label?:string;
}) {
  return <label>{label}<select value={value} required={!optional} onChange={e=>onChange(e.target.value)}><option value="">
    {optional ? "None" : "Choose a version"}</option>
    {datasets.map(ds=><optgroup key={ds.id} label={ds.name}>{ds.versions.map(v=>
      <option key={v.id} value={v.id}>{ds.name} · v{v.number}</option>)}</optgroup>)}</select></label>;
}
export function getVersion(datasets:Dataset[], id:string): Version|undefined {
  return datasets.flatMap(item=>item.versions).find(item=>item.id===id);
}

const palette=["#3d9c78","#6b84bd","#dcb47e","#986fb2","#3e8090","#d27e64","#a2b75c","#63747a"];
const green=palette[0];
const tooltipStyle={background:"var(--panel)",border:"1px solid var(--line)",borderRadius:10,color:"var(--text)"};

export function ChartView({chart, filter=false}: {chart:Chart;filter?:boolean}) {
  const [filterValue,setFilterValue]=useState("");
  const [from,setFrom]=useState("");
  const [to,setTo]=useState("");
  const x=chart.x ?? (chart.type==="heatmap" ? "column" : chart.type==="table" ? chart.columns?.[0] ?? "group" : "group");
  const y=chart.y ?? "value";
  const temporal=chart.rows.length > 0 && chart.rows.every(row=>typeof row[x]==="string" && /^\d{4}-\d{2}-\d{2}/.test(String(row[x])));
  const list=chart.rows.filter(row=>(!filterValue || String(row[x]).toLowerCase().includes(filterValue.toLowerCase())) &&
    (!from || String(row[x]).slice(0,10)>=from) && (!to || String(row[x]).slice(0,10)<=to));
  const axes=<><CartesianGrid vertical={false} stroke="var(--line)" strokeDasharray="3 3"/>
    <XAxis dataKey={x} tick={{fill:"var(--muted)",fontSize:11}} tickFormatter={value=>temporal?String(value).slice(0,10):String(value)} />
    <YAxis tick={{fill:"var(--muted)",fontSize:11}}/><Tooltip contentStyle={tooltipStyle}/></>;
  const graph=chart.type==="line" ? <LineChart data={list} margin={{top:14,right:22,bottom:8,left:0}}>{axes}
    <Line dataKey={y} stroke={green} strokeWidth={2.5} dot={list.length<25} />
    {list.some(row=>row.lower!==undefined) && <><Line dataKey="upper" stroke="#7b8cc0" strokeDasharray="5 5" dot={false}/><Line dataKey="lower" stroke="#7b8cc0" strokeDasharray="5 5" dot={false}/></>}
    </LineChart> : chart.type==="scatter" ? <ScatterChart margin={{top:14,right:22,bottom:8,left:0}}>
      <CartesianGrid stroke="var(--line)"/><XAxis type="number" dataKey={x} name={x}/><YAxis type="number" dataKey={y} name={y}/>
      <Tooltip contentStyle={tooltipStyle}/><Scatter data={list} fill={green}/></ScatterChart>
      : chart.type==="pie" ? <PieChart><Pie data={list} dataKey={y} nameKey={x} innerRadius={52} outerRadius={92}>
        {list.map((row,i)=><Cell key={String(row[x])} fill={palette[i%palette.length]}/>)}</Pie><Tooltip contentStyle={tooltipStyle}/><Legend/></PieChart>
      : <BarChart data={list} margin={{top:14,right:22,bottom:8,left:0}}>{axes}<Bar dataKey={y} fill={green}
          radius={[4,4,0,0]} maxBarSize={48}/></BarChart>;
  return <div className="chart-panel">
    <div className="chart-caption"><span className="label">{chart.method}</span>{chart.truncated && <span className="pill">Limited results</span>}</div>
    {filter && <div className="form-grid chart-filters"><label>Filter groups<input type="search" placeholder="Filter chart data" value={filterValue}
      onChange={e=>setFilterValue(e.target.value)}/></label>{temporal && <>
        <label>From<input type="date" value={from} onChange={e=>setFrom(e.target.value)}/></label>
        <label>To<input type="date" value={to} onChange={e=>setTo(e.target.value)}/></label></>}</div>}
    {chart.type==="kpi" ? <div className="kpi-value">{String(list[0]?.[y]??"—")}</div>
      : chart.type==="table" ? <Table columns={chart.columns??[]} rows={list}/>
      : chart.type==="heatmap" ? <div className="table-scroll"><table><thead><tr><th>Column</th>{chart.columns?.map(c=><th key={c}>{c}</th>)}</tr></thead>
        <tbody>{list.map(row=><tr key={String(row.column)}><th>{row.column}</th>{chart.columns?.map(c=><td key={c}
          style={{background: typeof row[c]==="number" ? `color-mix(in srgb, ${row[c]<0?"#e89d73":green} ${Math.abs(row[c])*42}%, var(--panel))`:undefined}}>
          {typeof row[c]==="number"?row[c].toFixed(2):"—"}</td>)}</tr>)}</tbody></table></div>
      : <div className="chart-area"><ResponsiveContainer width="100%" height="100%" minWidth={0}>{graph}</ResponsiveContainer></div>}
    {chart.type!=="table" && chart.type!=="heatmap" && <details className="details"><summary>View chart data <ArrowUpRight size={13}/></summary>
      <Table columns={Object.keys(list[0]??{})} rows={list}/></details>}
  </div>;
}
