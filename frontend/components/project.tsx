"use client";

import { type FormEvent, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Bot, Database, FileText, ShieldCheck } from "lucide-react";
import { api, json, type Config, type Dataset, type Job, type Project, type Role } from "@/lib/api";
import { Empty, ErrorNote, Heading, RoleChooser } from "@/components/common";
import { CleaningStudio, DataStudio, SqlStudio } from "@/components/data-studio";
import { AnalysisStudio, Dashboards, Jobs, Reports } from "@/components/analysis-studio";
import { Button } from "@/components/ui/button";

export type Context = {base:string;project:Project;datasets:Dataset[];config:Config;readOnly:boolean;roles:Role[]};

export function ProjectView({id,section}: {id:string;section:string}) {
  const base=`/projects/${id}`;
  const project=useQuery({queryKey:["project",id],queryFn:()=>api<Project>(base)});
  const datasets=useQuery({queryKey:["datasets",id],queryFn:()=>api<Dataset[]>(base+"/datasets"),enabled:!!project.data});
  const config=useQuery({queryKey:["config"],queryFn:()=>api<Config>("/auth/config")});
  const roles=useQuery({queryKey:["roles"],queryFn:()=>api<Role[]>("/roles")});
  if (project.error || datasets.error) return <ErrorNote error={project.error??datasets.error}/>;
  if (!project.data || !datasets.data) return <p role="status" className="muted">Loading project…</p>;
  const context={base,project:project.data,datasets:datasets.data,config:config.data??{password_reset:false,llm:"none",research:false},
    roles:roles.data??[],readOnly:project.data.access==="viewer"};
  let content:React.ReactNode;
  switch(section) {
    case "analysts": content=<AnalystSettings context={context}/>;break;
    case "datasets": content=<DataStudio context={context}/>;break;
    case "clean": content=<CleaningStudio context={context}/>;break;
    case "sql": content=<SqlStudio context={context}/>;break;
    case "chat": case "research": case "forecast": case "visualize":
      content=<AnalysisStudio context={context} section={section}/>;break;
    case "dashboards": content=<Dashboards context={context}/>;break;
    case "reports": content=<Reports context={context}/>;break;
    case "history": case "jobs": content=<Jobs context={context} history={section==="history"}/>;break;
    default: content=<Overview context={context}/>;
  }
  return <div key={id+"/"+section}>{content}</div>;
}

function Overview({context}: {context:Context}) {
  const {base,project,datasets,roles}=context;
  const jobs=useQuery({queryKey:["jobs",project.id],queryFn:()=>api<Job[]>(base+"/jobs")});
  return <>
    <Heading title={project.name} description={project.description||"Add your data and run your first analysis."}>
      <Button asChild><Link href={base+"/chat"}><Bot size={17}/> Open AI analysts</Link></Button></Heading>
    <div className="stats-row">
      {([[Database,"Datasets",datasets.length],[Bot,"Assigned analysts",project.roles.length],[FileText,"Completed jobs",
        jobs.data?.filter(j=>j.status==="completed").length??"—"]] as const).map(([Icon,label,n])=><article className="stat-card" key={label}>
        <span className="icon-tile"><Icon size={18}/></span><div><span>{label}</span><strong>{n}</strong></div></article>)}
    </div>
    <div className="two-columns"><section className="panel stack"><div className="spread"><h2>Project data</h2>
      <Link className="text-link" href={base+"/datasets"}>Manage <ArrowRight size={15}/></Link></div>
      {!datasets.length ? <Empty title="No datasets yet" description="Import a file to start exploring this project.">
        <Button asChild variant="outline"><Link href={base+"/datasets"}>Open datasets</Link></Button></Empty> :
        datasets.map(dataset=><div key={dataset.id} className="spread list-row"><b>{dataset.name}</b>
          <span className="pill">v{dataset.versions[0].number} · {dataset.versions[0].profile.rows.toLocaleString()} rows</span></div>)}</section>
      <section className="panel stack"><div className="spread"><h2>Assigned analysts</h2>
        <Link className="text-link" href={base+"/analysts"}>View roles <ArrowRight size={15}/></Link></div>
        {roles.filter(role=>project.roles.includes(role.id)).map(role=><div key={role.id} className="list-row role-summary">
          <ShieldCheck size={18}/><div><b>{role.name}</b><small className="muted block">{role.template}</small></div></div>)}</section></div>
  </>;
}

function AnalystSettings({context}: {context:Context}) {
  const {base,project,roles,readOnly}=context;
  const cache=useQueryClient();
  const [selected,setSelected]=useState(project.roles);
  const [error,setError]=useState<unknown>(null),[message,setMessage]=useState(""),[busy,setBusy]=useState(false);
  async function save(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setBusy(true);setError(null);setMessage("");
    const values=Object.fromEntries(new FormData(event.currentTarget));
    try {
      await api(base,json("PATCH",{...values,roles:selected}));
      await Promise.all([cache.invalidateQueries({queryKey:["project",project.id]}),cache.invalidateQueries({queryKey:["projects"]})]);
      setMessage("Project settings saved.");
    } catch(problem){setError(problem);}
    finally{setBusy(false);}
  }
  return <><Heading title="Analyst roles" description="Choose the specialists assigned to this project."/>
    <form className="panel stack" onSubmit={save}>
      <div className="form-grid"><label>Project name<input name="name" required minLength={2} maxLength={100} defaultValue={project.name} readOnly={readOnly}/></label>
        <label>Description<input name="description" maxLength={2000} defaultValue={project.description} readOnly={readOnly}/></label></div>
      <RoleChooser roles={roles} selected={selected} onChange={setSelected} readOnly={readOnly}/>
      <ErrorNote error={error}/>{message&&<p role="status" className="success">{message}</p>}
      {!readOnly&&<div><Button disabled={busy||!selected.length}>Save project settings</Button></div>}
    </form></>;
}
