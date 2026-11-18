"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Bot, Database, FileText, FolderKanban, LayoutDashboard, LogOut, Menu, Moon, Plus, Settings, Shield, Sun, Terminal, Users, X } from "lucide-react";
import { api, ApiError, type Project, type User } from "@/lib/api";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";

export const tools = [
  ["", "Project overview", FolderKanban], ["analysts", "Analyst roles", Users], ["chat", "AI analysts", Bot],
  ["datasets", "Datasets", Database], ["clean", "Cleaning studio", Database], ["sql", "SQL studio", Terminal],
  ["visualize", "Visualization builder", LayoutDashboard], ["dashboards", "Dashboards", LayoutDashboard],
  ["research", "Research", Shield], ["forecast", "Forecasting & models", Activity], ["reports", "Reports", FileText],
  ["history", "Analysis history", Activity], ["jobs", "Execution & schedules", Activity],
] as const;

export function Shell({children}: {children:React.ReactNode}) {
  const router = useRouter(), pathname=usePathname(), cache=useQueryClient();
  const [open,setOpen] = useState(false);
  const [dark,setDark] = useState(false);
  const user = useQuery({queryKey:["user"],queryFn:() => api<User>("/auth/me")});
  const projects = useQuery({queryKey:["projects"],queryFn:() => api<Project[]>("/projects"),enabled:!!user.data});
  const current = pathname.match(/^\/projects\/([^/]+)/)?.[1];
  const selected = projects.data?.find(project => project.id === current);
  useEffect(() => {
    if (user.error instanceof ApiError && user.error.status === 401) router.replace("/login");
  },[user.error,router]);
  useEffect(() => {
    setDark(localStorage.getItem("theme") === "dark");
  },[]);
  function changeTheme() {
    const value = !dark;
    setDark(value); localStorage.setItem("theme",value ? "dark" : "light");
    document.documentElement.dataset.theme = value ? "dark" : "light";
  }
  async function logout() {
    await api("/auth/logout",{method:"POST"}); cache.clear(); router.replace("/login");
  }
  const [logoutError, setLogoutError] = useState("");
  if (!user.data) return <main className="center-state"><Brand/><p>{user.error && !(user.error instanceof ApiError && user.error.status===401)
    ? user.error.message : "Opening your workspace…"}</p></main>;
  return <div className="shell">
    {open && <button className="sidebar-overlay" aria-label="Close navigation" onClick={()=>setOpen(false)}/>}
    <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
      <div className="sidebar-brand"><Brand href="/workspace"/><button className="icon-button mobile-menu" onClick={()=>setOpen(false)} aria-label="Close navigation"><X size={18}/></button></div>
      <div className="workspace-select"><span className="avatar workspace-avatar">{user.data.name.slice(0,1).toUpperCase()}</span>
        <div><b>My workspace</b><small>{user.data.email}</small></div></div>
      <nav aria-label="Workspace navigation" className="sidebar-links">
        <span className="nav-caption">WORKSPACE</span>
        {([["/workspace","Dashboard",LayoutDashboard],["/workspace/projects","Projects",FolderKanban],
          ["/workspace/team","Team & access",Users],["/workspace/settings","Settings",Settings]] as const).map(([href,label,Icon]) =>
          <Link onClick={()=>setOpen(false)} key={href} href={href} aria-current={pathname===href ? "page":undefined}><Icon size={17}/>{label}</Link>)}
        {user.data.admin && <Link href="/workspace/admin" aria-current={pathname.endsWith("/admin") ? "page":undefined}><Shield size={17}/>Administration</Link>}
        {selected && <><span className="nav-caption project-caption" title={selected.name}>{selected.name}</span>
          {tools.map(([section,label,Icon]) => {
            const href = `/projects/${selected.id}${section ? `/${section}` : ""}`;
            return <Link onClick={()=>setOpen(false)} key={section} href={href} aria-current={pathname===href ? "page":undefined}>
              <Icon size={16}/>{label}</Link>;
          })}</>}
      </nav>
      <div className="sidebar-footer"><span className="avatar">{user.data.name.slice(0,1).toUpperCase()}</span>
        <div><b>{user.data.name}</b><small>Account</small></div>
        <button className="icon-button" aria-label="Sign out" title="Sign out" onClick={()=>logout().catch(error=>setLogoutError(error.message))}><LogOut size={16}/></button>
      </div>{logoutError && <p className="error compact">{logoutError}</p>}
    </aside>
    <div className="shell-main"><header className="topbar">
      <div className="inline"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={()=>setOpen(true)}><Menu size={21}/></button>
        <Link href="/workspace">Workspace</Link>{selected && <><span className="breadcrumb-slash">/</span><Link href={`/projects/${selected.id}`}>{selected.name}</Link></>}</div>
      <div className="inline"><button className="icon-button" aria-label={dark?"Use light theme":"Use dark theme"} onClick={changeTheme}>{dark?<Sun size={18}/>:<Moon size={17}/>}</button>
        <Button asChild><Link href="/projects/new"><Plus size={16}/> <span>New project</span></Link></Button></div>
    </header><main className="workspace-main">{children}</main></div>
  </div>;
}
