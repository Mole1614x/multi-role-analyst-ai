"use client";

import { type FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ArrowUpRight, Bot, Database, FileText, FolderKanban, Plus, Users } from "lucide-react";
import { api, json, type Project, type Role, type User, type Workspace } from "@/lib/api";
import { Empty, ErrorNote, Heading, RoleChooser } from "@/components/common";
import { Button } from "@/components/ui/button";

const date = (value:string)=>new Date(value).toLocaleDateString(undefined,{month:"short",day:"numeric",year:"numeric"});
const useProjects = () => useQuery({queryKey:["projects"],queryFn:()=>api<Project[]>("/projects")});
const useWorkspaces = () => useQuery({queryKey:["workspaces"],queryFn:()=>api<Workspace[]>("/workspaces")});

function ProjectCards({projects}: {projects:Project[]}) {
  if (!projects.length) return <Empty title="No projects yet" description="Create a project to add datasets, assign analysts, and save your work.">
    <Button asChild><Link href="/projects/new"><Plus size={16}/> Create project</Link></Button></Empty>;
  return <div className="project-grid">{projects.map(project=><Link className="project-card" key={project.id} href={`/projects/${project.id}`}>
    <div className="spread"><span className="icon-tile"><FolderKanban size={20}/></span><ArrowUpRight className="muted" size={17}/></div>
    <h3>{project.name}</h3><p>{project.description||"Open the project to start an analysis."}</p>
    <div className="spread project-meta"><span>{project.roles.length} analyst{project.roles.length!==1?"s":""}</span><span>{date(project.created_at)}</span></div>
  </Link>)}</div>;
}

export function Home({page}: {page:string}) {
  const projects=useProjects();
  const user=useQuery({queryKey:["user"],queryFn:()=>api<User>("/auth/me")});
  const [search,setSearch]=useState("");
  if (page==="team") return <Team/>;
  if (page==="admin") return <Admin/>;
  if (page==="settings") return <><Heading title="Settings" description="View your account details and password options."/>
    <section className="panel stack"><div><span className="label">NAME</span><p>{user.data?.name}</p></div>
      <div><span className="label">EMAIL</span><p>{user.data?.email}</p></div>
      <div><span className="label">ACCOUNT ID</span><p className="mono">{user.data?.id}</p><small className="muted">Share this ID with a workspace owner for team access.</small></div>
      <div><Button asChild variant="outline"><Link href="/forgot">Reset password <ArrowRight size={16}/></Link></Button></div></section></>;
  if (page==="projects") return <><Heading title="Projects" description="Find and reopen your analytical projects.">
    <Button asChild><Link href="/projects/new"><Plus size={16}/> Create project</Link></Button></Heading>
    <label className="project-search">Search projects<input type="search" value={search} onChange={e=>setSearch(e.target.value)}
      placeholder="Search by name"/></label>
    <ErrorNote error={projects.error}/>{projects.isPending ? <p className="muted">Loading projects…</p> : !projects.error &&
      ((projects.data ?? []).length && !(projects.data ?? []).some(p=>p.name.toLowerCase().includes(search.toLowerCase()))
        ? <Empty title="No matching projects" description="Try another project name."/>
        : <ProjectCards projects={(projects.data ?? []).filter(p=>p.name.toLowerCase().includes(search.toLowerCase()))}/>)}</>;
  const list=projects.data ?? [];
  return <>
    <section className="workspace-welcome"><div className="welcome-copy"><div className="eyebrow"><span className="status-dot"/> PERSONAL WORKSPACE</div>
      <h1>Welcome, {user.data?.name.split(" ")[0]}.</h1><p>Pick up an analysis or start a project with your data.</p>
      <Button asChild><Link href="/projects/new"><Plus size={16}/> Create a project</Link></Button></div>
      <div className="welcome-decoration" aria-hidden="true"><i/><i/><i/><i/><i/><i/></div></section>
    <div className="stats-row">{([[FolderKanban,"Projects",list.length],[Bot,"Analyst assignments",list.reduce((n,p)=>n+p.roles.length,0)],
      [Users,"Shared workspaces",new Set(list.map(p=>p.workspace_id)).size]] as const).map(([Icon,label,value])=>
      <article key={label} className="stat-card"><span className="icon-tile"><Icon size={19}/></span><div><span>{label}</span><strong>{projects.isPending?"—":value}</strong></div></article>)}</div>
    <section><div className="spread section-title"><h2>Recent projects</h2><Link className="text-link" href="/workspace/projects">View all projects <ArrowRight size={15}/></Link></div>
      <ErrorNote error={projects.error}/>{projects.isPending ? <p className="muted">Loading projects…</p>:!projects.error && <ProjectCards projects={list.slice(0,6)}/>}</section>
    <section className="starter-row"><article className="panel"><Database size={21}/><h3>Bring your data</h3><p>Import files, inspect their schema, and preserve the original when you clean them.</p></article>
      <article className="panel"><FileText size={21}/><h3>Export your findings</h3><p>Generate a report with the dataset version and calculation method included.</p></article></section>
  </>;
}

export function ProjectForm() {
  const router=useRouter(), cache=useQueryClient(), spaces=useWorkspaces();
  const roles=useQuery({queryKey:["roles"],queryFn:()=>api<Role[]>("/roles")});
  const [selected,setSelected]=useState(["data"]);
  const [error,setError]=useState<unknown>(null),[pending,setPending]=useState(false);
  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError(null);
    try {
      const values=Object.fromEntries(new FormData(event.currentTarget));
      const project=await api<Project>("/projects",json("POST",{...values,roles:selected}));
      await cache.invalidateQueries({queryKey:["projects"]});
      router.push(`/projects/${project.id}`);
    } catch (problem) {setError(problem);}
    finally {setPending(false);}
  }
  return <><Heading title="Create a project" description="Choose a workspace, name your project, and assign analysts."/>
    <form className="panel stack" onSubmit={submit}>
      <div className="form-grid"><label>Project name<input name="name" required minLength={2} maxLength={100} placeholder="e.g. Quarterly revenue review"/></label>
        <label>Workspace<select name="workspace_id" required>{spaces.data?.filter(w=>w.role!=="viewer").map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</select></label></div>
      <label>Description<textarea name="description" rows={3} maxLength={2000} placeholder="What do you want to understand?"/></label>
      <fieldset><legend>Analyst roles</legend><RoleChooser roles={roles.data??[]} selected={selected} onChange={setSelected}/></fieldset>
      <ErrorNote error={error??spaces.error??roles.error}/>
      <div className="inline"><Button disabled={pending||!selected.length||!spaces.data?.some(w=>w.role!=="viewer")}>
        {pending?"Creating…":"Create project"} <ArrowRight size={16}/></Button>
        <Button asChild variant="outline"><Link href="/workspace/projects">Cancel</Link></Button></div>
    </form></>;
}

function Team() {
  const spaces=useWorkspaces();
  const [choice,setChoice]=useState(""),[error,setError]=useState<unknown>(null),[pending,setPending]=useState(false);
  const workspace=spaces.data?.find(w=>w.id===choice)??spaces.data?.[0];
  const base=`/workspaces/${workspace?.id}`;
  const members=useQuery({queryKey:["members",workspace?.id],queryFn:()=>api<{id:string;name:string;role:string}[]>(base+"/members"),enabled:!!workspace});
  const activity=useQuery({queryKey:["activity",workspace?.id],queryFn:()=>api<{id:string;action:string;created_at:string}[]>(base+"/activity"),
    enabled:workspace?.role==="owner"});
  async function change(options:RequestInit, suffix="") {
    setError(null);setPending(true);
    try {await api(base+"/members"+suffix,options);await Promise.all([members.refetch(),activity.refetch()]);}
    catch(problem){setError(problem);}
    finally{setPending(false);}
  }
  return <><Heading title="Team & access" description="Manage workspace memberships and review access activity."/>
    <section className="panel stack"><label>Workspace<select value={workspace?.id??""} onChange={event=>setChoice(event.target.value)}>
      {spaces.data?.map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
      <h2>Members</h2>
      <ErrorNote error={error??members.error}/>
      {members.data?.map(member=><div className="spread list-row" key={member.id}><div><b>{member.name}</b><small className="muted block">{member.role}</small></div>
        {workspace?.role==="owner"&&member.role!=="owner"&&<Button type="button" variant="outline" disabled={pending}
          onClick={()=>change({method:"DELETE"},`/${member.id}`)}>Remove access</Button>}</div>)}
      {workspace?.role==="owner" && <form className="stack" onSubmit={event=>{
        event.preventDefault(); void change(json("PUT",Object.fromEntries(new FormData(event.currentTarget))));
      }}><h3>Grant or update access</h3><div className="form-grid"><label>Account ID<input name="user_id" required minLength={36} maxLength={36}/></label>
        <label>Access level<select name="role"><option value="viewer">Viewer</option><option value="editor">Editor</option></select></label></div>
        <div><Button disabled={pending}>Save access</Button></div></form>}
    </section>
    {workspace?.role==="owner"&&<section className="panel stack"><h2>Activity</h2><ErrorNote error={activity.error}/>
      {activity.data?.length===0&&<p className="muted">No workspace activity yet.</p>}
      {activity.data?.map(entry=><div className="spread list-row" key={entry.id}><span>{entry.action}</span><span className="muted">{date(entry.created_at)}</span></div>)}</section>}
  </>;
}

function Admin() {
  const stats=useQuery({queryKey:["admin"],queryFn:()=>api<Record<string,number>>("/admin")});
  return <><Heading title="Administration" description="View usage counts for this deployment."/><ErrorNote error={stats.error}/>
    <div className="stats-row">{Object.entries(stats.data??{}).map(([key,value])=><article className="stat-card" key={key}><div><span>{key}</span><strong>{value}</strong></div></article>)}</div></>;
}
