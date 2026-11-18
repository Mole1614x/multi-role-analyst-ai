"use client";

import { type FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Download, Plus, Terminal, Upload } from "lucide-react";
import { api, json, type Dataset, type Profile, type Row, type SavedQuery, type Step, type Version } from "@/lib/api";
import { Empty, ErrorNote, getVersion, Heading, Table, VersionSelect } from "@/components/common";
import { Button } from "@/components/ui/button";
import type { Context } from "@/components/project";
import { finished, useActiveJob } from "@/lib/jobs";

function ProfileView({profile}: {profile:Profile}) {
  return <>
    <div className="profile-stats"><span><b>{profile.rows.toLocaleString()}</b> rows</span>
      <span><b>{profile.column_count}</b> columns</span><span><b>{profile.duplicates.toLocaleString()}</b> duplicate rows</span></div>
    <Table columns={["Name","Type","Missing","Distinct","Mean","Outliers"]}
      rows={profile.columns.map(c=>({Name:c.name,Type:c.type,Missing:c.missing,Distinct:c.distinct,Mean:c.mean??null,Outliers:c.outliers??null}))}/>
  </>;
}

export function DataStudio({context}: {context:Context}) {
  const {base,datasets,project,readOnly}=context;
  const cache=useQueryClient();
  const [selected,setSelected]=useState(""),[message,setMessage]=useState(""),[error,setError]=useState<unknown>(null);
  const [busy,setBusy]=useState(false),[progress,setProgress]=useState(0),[connector,setConnector]=useState(false);
  const [jobId,setJobId]=useState("");
  const importJob=useActiveJob(context,jobId);
  const processing=!!jobId&&!importJob.error&&!finished(importJob.data?.status??"queued");
  const completed=importJob.data?.status==="completed";
  const version=selected||(completed ? importJob.data?.result?.version_id : "")||datasets[0]?.versions[0]?.id||"";
  const detail=useQuery({queryKey:["version",project.id,version],queryFn:()=>api<Version&{rows:Row[]}>(base+"/versions/"+version),enabled:!!version});
  const connectors=useQuery({queryKey:["connectors",project.id],queryFn:()=>api<{name:string;type:string}[]>(base+"/connectors")});
  async function upload(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form=event.currentTarget, payload=new FormData(form);
    setError(null);setMessage("");setJobId("");setBusy(true);setProgress(0);
    try {
      const result=await new Promise<Dataset&{job_id?:string}>((resolve,reject)=>{
        const request=new XMLHttpRequest();
        request.open("POST",`/api${base}/datasets`);
        request.upload.addEventListener("progress",entry=>{if(entry.lengthComputable)setProgress(Math.round(entry.loaded/entry.total*100));});
        request.responseType="json";
        request.timeout=180_000;
        request.onload=()=>request.status>=200&&request.status<300 ? resolve(request.response) :
          reject(new Error(request.response?.detail??"Upload failed."));
        request.onerror=()=>reject(new Error("Upload connection failed."));
        request.ontimeout=()=>reject(new Error("Upload timed out."));
        request.send(payload);
      });
      if (result.job_id) {
        setSelected("");
        setJobId(result.job_id);
      } else {
        setSelected(result.versions[0].id);
        setMessage("Dataset imported.");
        await cache.invalidateQueries({queryKey:["datasets",project.id]});
      }
      form.reset();
    } catch(problem){setError(problem);}
    finally{setBusy(false);}
  }
  async function connect(event:FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);setError(null);setMessage("");setJobId("");
    try {
      const dataset=await api<Dataset>(base+"/connectors",json("POST",Object.fromEntries(new FormData(event.currentTarget))));
      setSelected(dataset.versions[0].id);setMessage("Source table imported.");
      await cache.invalidateQueries({queryKey:["datasets",project.id]});
    } catch(problem){setError(problem);} finally{setBusy(false);}
  }
  return <><Heading title="Datasets" description="Import source data and inspect profiles, rows, and version history."/>
    {!readOnly&&<section className="panel stack"><div className="spread"><h2><Upload size={19}/> Import a dataset</h2>
      {!!connectors.data?.length&&<Button variant="outline" onClick={()=>setConnector(!connector)}>{connector?"Upload file":"Import from PostgreSQL"}</Button>}</div>
      {connector ? <form className="stack" onSubmit={connect}><div className="form-grid"><label>Configured source
        <select name="source" required>{connectors.data?.map(c=><option key={c.name}>{c.name}</option>)}</select></label>
        <label>Table<input name="table" required placeholder="public.table_name"/></label></div><div><Button disabled={busy||processing}>Import table</Button></div></form>
        :<form className="stack" onSubmit={upload}><div className="form-grid"><label>Data file<input type="file" name="file" required
          accept=".csv,.xlsx,.json,.parquet,.sqlite,.sqlite3,.db,.duckdb"/></label>
          <label>Table or worksheet (optional)<input name="table" maxLength={120}/></label></div>
          {busy&&<label>{progress===100?"Processing file":"Uploading file"}<progress aria-label="Upload progress" max={100} value={progress}/></label>}
          <div><Button disabled={busy||processing}><Upload size={16}/> {busy||processing?"Importing…":"Import dataset"}</Button></div></form>}
      {processing&&<p className="muted" role="status">{importJob.data?.status==="running"?"Processing dataset…":"Dataset import queued…"}</p>}
      <ErrorNote error={error??importJob.error??importJob.data?.error}/>
      {(message||completed)&&<p className="success" role="status">{message||"Dataset imported."}</p>}
    </section>}
    {!datasets.length ? <Empty title="No datasets yet" description="Imported files will appear here with a schema and data preview."/> :
      <section className="panel stack"><div className="spread"><h2>Data explorer</h2>
        {version&&<Button asChild variant="outline"><a href={`/api${base}/versions/${version}/export`}><Download size={15}/> Download Parquet</a></Button>}</div>
        <VersionSelect datasets={datasets} value={version} onChange={setSelected}/>
        <ErrorNote error={detail.error}/>
        {detail.data&&<><ProfileView profile={detail.data.profile}/><h3>Preview</h3>
          <Table key={version} columns={detail.data.profile.columns.map(c=>c.name)} rows={detail.data.rows}/>
          <details className="details"><summary>Version provenance</summary><p className="mono breakable">{detail.data.sha256}</p>
            {detail.data.transformations.map((step,i)=><p key={i}>{step.operation} {step.column} {step.value}</p>)}</details></>}
      </section>}
  </>;
}

const operations=[["drop_duplicates","Remove duplicate rows"],["standardize_columns","Standardize column names"],
  ["drop_missing","Drop rows with missing values"],["fill_missing","Fill missing values"],["to_number","Convert to number"],
  ["to_date","Convert to date"],["drop_column","Remove column"],["filter_equals","Keep matching rows"],["trim","Trim whitespace"],
  ["cap_outliers","Cap IQR outliers"]];
const emptyStep:Step={operation:"drop_duplicates",column:"",value:""};

export function CleaningStudio({context}: {context:Context}) {
  const {base,datasets,project,readOnly}=context;
  const cache=useQueryClient();
  const [selected,setSelected]=useState(""),[steps,setSteps]=useState<Step[]>([{...emptyStep}]);
  const [preview,setPreview]=useState<{before:Profile;after:Profile;rows:Row[]}|null>(null);
  const [message,setMessage]=useState(""),[error,setError]=useState<unknown>(null),[busy,setBusy]=useState(false);
  const version=selected||datasets[0]?.versions[0]?.id||"";
  const current=getVersion(datasets,version);
  function edit(index:number,change:Partial<Step>) {
    setSteps(steps.map((step,i)=>i===index?{...step,...change}:step));setPreview(null);
  }
  async function transform(onlyPreview:boolean) {
    setBusy(true);setError(null);setMessage("");
    try {
      const response=await api<{before:Profile;after:Profile;rows:Row[]}&Version>(`${base}/versions/${version}/clean`,
        json("POST",{steps,preview:onlyPreview}));
      if (onlyPreview) setPreview(response);
      else {
        setSelected(response.id);setPreview(null);setMessage(`Saved cleaned version ${response.number}.`);
        await cache.invalidateQueries({queryKey:["datasets",project.id]});
      }
    } catch(problem){setError(problem);} finally{setBusy(false);}
  }
  return <><Heading title="Cleaning studio" description="Preview transformations and save them as a new dataset version."/>
    {!datasets.length ? <NoDataset base={base}/> : <section className="panel stack">
      <VersionSelect datasets={datasets} value={version} onChange={value=>{setSelected(value);setPreview(null);setMessage("");}}/>
      {current?.parent_id&&<div><Button variant="outline" onClick={()=>{setSelected(current.parent_id??"");setPreview(null);setMessage("");}}>
        Reopen parent version</Button></div>}
      {current&&<><div className="profile-stats"><span><b>{current.profile.rows}</b> rows</span>
        <span><b>{current.profile.duplicates}</b> duplicates</span>
        <span><b>{current.profile.columns.filter(c=>c.missing).length}</b> columns with missing values</span></div>
        {!readOnly&&<section className="stack"><h3>Suggested steps</h3>
          <div className="inline">{current.profile.duplicates>0&&<Button type="button" variant="outline" onClick={()=>edit(0,emptyStep)}>Remove duplicates</Button>}
            {current.profile.columns.filter(c=>c.missing).slice(0,4).map(c=><Button key={c.name} type="button" variant="outline"
              onClick={()=>edit(0,{operation:"drop_missing",column:c.name,value:""})}>Review missing {c.name}</Button>)}
            {!current.profile.duplicates&&!current.profile.columns.some(c=>c.missing)&&<small className="muted">No missing values or duplicate rows detected.</small>}</div></section>}</>}
      {!readOnly&&<form className="stack" onSubmit={e=>{e.preventDefault();void transform(true);}}>
        {steps.map((step,index)=><div key={index} className="form-grid"><label>Transformation {index+1}<select value={step.operation}
          onChange={e=>edit(index,{operation:e.target.value})}>{operations.map(([key,label])=><option value={key} key={key}>{label}</option>)}</select></label>
          {!["drop_duplicates","standardize_columns"].includes(step.operation)&&<label>Column<select required value={step.column}
            onChange={e=>edit(index,{column:e.target.value})}><option value="">Choose column</option>
            {current?.profile.columns.map(c=><option key={c.name}>{c.name}</option>)}</select></label>}
          {["fill_missing","filter_equals"].includes(step.operation)&&<label>Value<input required value={step.value}
            onChange={e=>edit(index,{value:e.target.value})}/></label>}
          {steps.length>1&&<Button type="button" variant="ghost" onClick={()=>{setSteps(steps.filter((_,i)=>i!==index));setPreview(null);}}>Remove step</Button>}
        </div>)}
        <div className="inline"><Button type="button" variant="outline" disabled={steps.length>=15} onClick={()=>{setSteps([...steps,{...emptyStep}]);setPreview(null);}}>
          <Plus size={15}/> Add step</Button><Button disabled={busy}>Preview changes</Button>
          {preview&&<Button type="button" variant="outline" disabled={busy} onClick={()=>transform(false)}>Save cleaned version</Button>}</div>
      </form>}
      <ErrorNote error={error}/>{message&&<p role="status" className="success">{message}</p>}
      {preview&&<><h3>Before and after</h3><p className="success">{preview.before.rows} → {preview.after.rows} rows ·
         {" "}{preview.before.duplicates} → {preview.after.duplicates} duplicate rows</p>
        <Table columns={preview.after.columns.map(c=>c.name)} rows={preview.rows}/></>}
    </section>}
  </>;
}

export function NoDataset({base}: {base:string}) {
  return <Empty title="Add a dataset first" description="Import data to enable this workflow.">
    <Button asChild variant="outline"><Link href={base+"/datasets"}>Open datasets</Link></Button></Empty>;
}

export function SqlStudio({context}: {context:Context}) {
  const {base,datasets,project,readOnly,config}=context;
  const [selected,setSelected]=useState(""),[join,setJoin]=useState(""),[statement,setStatement]=useState("SELECT * FROM dataset LIMIT 25");
  const [prompt,setPrompt]=useState(""),[title,setTitle]=useState(""),[approve,setApprove]=useState(false);
  const [result,setResult]=useState<SavedQuery|null>(null),[error,setError]=useState<unknown>(null),[busy,setBusy]=useState(false);
  const version=selected||datasets[0]?.versions[0]?.id||"";
  const item=getVersion(datasets,version);
  const history=useQuery({queryKey:["sql",project.id],queryFn:()=>api<SavedQuery[]>(base+"/sql")});
  async function submit(drafting:boolean) {
    setBusy(true);setError(null);
    try {
      const body={version_id:version,join_version_id:join||null,sql:statement,prompt,title,approve_external:approve};
      if (drafting) {
        const query=await api<{sql:string}>(base+"/sql/draft",json("POST",body));
        setStatement(query.sql);
      } else {
        setResult(await api<SavedQuery>(base+"/sql",json("POST",body)));await history.refetch();
      }
    }catch(problem){setError(problem);}finally{setBusy(false);}
  }
  return <><Heading title="SQL studio" description="Draft, inspect, and run read-only DuckDB queries."/>
    {!datasets.length?<NoDataset base={base}/>:<>
      {!readOnly&&<section className="panel stack">
        <div className="form-grid"><VersionSelect datasets={datasets} value={version} onChange={setSelected}/>
          <VersionSelect datasets={datasets} value={join} onChange={setJoin} optional label="Join dataset (dataset_b)"/></div>
        <details className="details"><summary>Available columns in dataset</summary>
          <div className="chips">{item?.profile.columns.map(column=><span className="pill" key={column.name}>{column.name} · {column.type}</span>)}</div></details>
        <form className="stack" onSubmit={e=>{e.preventDefault();void submit(true);}}>
          <label>Natural-language query<input value={prompt} onChange={e=>setPrompt(e.target.value)} maxLength={2000} placeholder="Total revenue by region" required/></label>
          {config.llm!=="none"&&<label className="checkbox"><input type="checkbox" checked={approve} onChange={e=>setApprove(e.target.checked)}/>
            Allow sharing the request and schema with {config.llm}</label>}
          <div><Button variant="outline" disabled={busy||!prompt.trim()}>Draft SQL</Button></div></form>
        <form onSubmit={e=>{e.preventDefault();void submit(false);}} className="stack">
          <label>SQL query<textarea className="sql-input" value={statement} onChange={e=>setStatement(e.target.value)} maxLength={12000} rows={5} required spellCheck={false}/></label>
          <label>Query name (optional)<input maxLength={100} value={title} onChange={e=>setTitle(e.target.value)}/></label>
          <div><Button disabled={busy}><Terminal size={16}/> Run query</Button></div>
        </form>
        <ErrorNote error={error}/>
      </section>}
      {result&&<section className="panel stack"><div className="spread"><h2>Query results</h2>
        <Button asChild variant="outline"><a href={`/api${base}/sql/${result.id}/export`}><Download size={15}/> Export CSV</a></Button></div>
        <p className="muted">{result.result.engine} · {result.result.rows.length} rows {result.result.truncated?"(limited)":""}</p>
        <pre>{result.sql}</pre><Table key={result.id} columns={result.result.columns} rows={result.result.rows}/></section>}
      <section className="panel stack"><h2>Saved query history</h2><ErrorNote error={history.error}/>
        {history.data?.length===0&&<p className="muted">Executed queries will appear here.</p>}
        {history.data?.map(query=><button className="list-button" key={query.id} onClick={()=>{setResult(query);setStatement(query.sql);setSelected(query.version_id);
          setJoin(query.result.source_versions?.[1]??"");setTitle(query.title);}}>{query.title}</button>)}</section>
    </>}
  </>;
}
