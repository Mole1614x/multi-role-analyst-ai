"use client";

import { type FormEvent, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Bot, Download, Play, Save, Sparkles } from "lucide-react";
import { api, json, type Dashboard, type Job, type Result, type Schedule } from "@/lib/api";
import { ChartView, Empty, ErrorNote, getVersion, Heading, Table, VersionSelect } from "@/components/common";
import { NoDataset } from "@/components/data-studio";
import { Button } from "@/components/ui/button";
import { DashboardCharts } from "@/components/dashboard-charts";
import type { Context } from "@/components/project";
import { finished, useActiveJob } from "@/lib/jobs";

const modes = {
  chat:["AI analysts","Ask a question about your data and inspect the results and execution trace."],
  research:["Research","Read discovered sources and check percentage claims against cited passages."],
  forecast:["Forecasting & models","Compare baselines and evaluate forecasts, models, or a statistical test."],
  visualize:["Visualization builder","Choose data fields and generate a chart from verified values."],
} as const;

function useJobs(context:Context) {
  const {base,project}=context;
  return useQuery({queryKey:["jobs",project.id],queryFn:()=>api<Job[]>(base+"/jobs"), refetchOnMount:"always",
    refetchInterval:query=>query.state.data?.some(row=>!finished(row.status))?1500:false});
}

function healthLabel(status:string) {
  return status.charAt(0).toUpperCase()+status.slice(1);
}

function Details({title, data}: {title:string;data:unknown}) {
  if (!data) return null;
  return <details className="details"><summary>{title}</summary><pre>{JSON.stringify(data,null,2)}</pre></details>;
}

function ResultView({result,context}: {result:Result;context:Context}) {
  return <div className="stack">
    {result.summary&&<p className="analysis-summary">{result.summary}</p>}
    {result.source&&<p className="muted">Dataset version {result.source.version}{result.method?" · "+result.method:""}</p>}
    {!!result.role_findings?.length&&<div className="findings">{result.role_findings.map(item=><article key={item.role+item.metric} className="finding stack">
      <div className="spread"><b>{item.metric}</b><span className={`pill ${item.status}`}>{healthLabel(item.status)}</span></div>
      {item.values&&<dl>{Object.entries(item.values).map(([key,value])=><div className="spread" key={key}>
        <dt>{key.replaceAll("_"," ")}</dt><dd>{value===null?"—":typeof value==="number"?new Intl.NumberFormat(undefined,{maximumFractionDigits:6}).format(value):
          <pre>{JSON.stringify(value,null,2)}</pre>}</dd></div>)}</dl>}
      <small className="muted">{item.reason??item.review}{item.excluded_rows ? ` · ${item.excluded_rows} excluded rows` : ""}</small></article>)}</div>}
    {result.chart&&<ChartView chart={result.chart} filter/>}
    {result.query&&<details className="details" open={!result.chart}><summary>Executed SQL and results</summary>
      <pre>{result.query.sql}</pre><Table columns={result.query.columns} rows={result.query.rows}/></details>}
    {result.claim_checks?.map((check,index)=><section className="finding stack" key={index}>
      <div className="spread"><b>{check.claim.subject} · {check.claim.percent}%</b>
        <span className="pill">{healthLabel(check.status.replaceAll("_"," "))}</span></div>
      {check.citations.map((citation,i)=><blockquote key={i}><p>{citation.excerpt}</p>
        <a className="text-link" href={citation.url} target="_blank" rel="noreferrer">{citation.title}</a>
        <small className="muted"> · {new Date(citation.retrieved_at).toLocaleDateString()} · {citation.stance.replaceAll("_"," ")}</small></blockquote>)}</section>)}
    {result.evidence?.map(source=><article className="finding stack" key={source.url}><a className="text-link" href={source.url}
      target="_blank" rel="noreferrer">{source.title} <ArrowRight size={13}/></a><small className="muted">{source.publisher} · retrieved {new Date(source.retrieved_at).toLocaleDateString()}</small>
      <p>{source.snippet}</p><small>{source.assessment} {source.read_status==="unavailable"&&"Full text unavailable."}</small></article>)}
    <Details title="Forecast evaluation and predictions" data={result.forecast}/>
    <Details title="Model metrics and feature weights" data={result.model}/>
    <Details title="Statistical test results" data={result.comparison}/>
    {!!result.limitations?.length&&<section className="analysis-notes"><h3>Limitations</h3><ul>{result.limitations.map(item=><li key={item}>{item}</li>)}</ul></section>}
    {!!result.assumptions?.length&&<section className="analysis-notes"><h3>Assumptions</h3><ul>{result.assumptions.map(item=><li key={item}>{item}</li>)}</ul></section>}
    {!!result.recommendations?.length&&<section className="analysis-notes"><h3>Recommendations</h3><ul>{result.recommendations.map(item=><li key={item}>{item}</li>)}</ul></section>}
    {result.completed_steps?.map((step,index)=><details className="details" key={index}>
      <summary>Step {index+1} · {step.plan?.objective}</summary><ResultView result={step} context={context}/></details>)}
    <Details title="Source and calculation metadata" data={result.source}/>
    {result.provider_usage&&!!Object.keys(result.provider_usage).length&&<Details title="Model usage" data={result.provider_usage}/>}
    {result.artifact_id&&<div><Button asChild variant="outline"><a href={`/api${context.base}/artifacts/${result.artifact_id}`}>
      <Download size={16}/> Download {result.format?.toUpperCase()}</a></Button></div>}
    {result.dataset_id&&<Link className="text-link" href={context.base+"/datasets"}>Open imported dataset <ArrowRight size={15}/></Link>}
  </div>;
}

function JobView({context,id}: {context:Context;id:string}) {
  const active=useActiveJob(context,id);
  const job=active.data;
  const [error,setError]=useState<unknown>(null),[title,setTitle]=useState(""),[saved,setSaved]=useState("");
  const [busy,setBusy]=useState(false);
  const cache=useQueryClient();
  async function command(action:string) {
    setError(null);setBusy(true);
    try {
      const update=await api<Job>(`${context.base}/jobs/${id}/${action}`,{method:"POST"});
      cache.setQueryData(["job",context.project.id,id],update);
      await cache.invalidateQueries({queryKey:["jobs",context.project.id]});
    } catch(problem){setError(problem);} finally{setBusy(false);}
  }
  async function save(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setError(null);setSaved("");setBusy(true);
    try {
      await api(context.base+"/dashboards",json("POST",{job_id:id,title}));
      await cache.invalidateQueries({queryKey:["dashboards",context.project.id]});
      setSaved("Dashboard saved.");
    } catch(problem){setError(problem);} finally{setBusy(false);}
  }
  if (active.error) return <ErrorNote error={active.error}/>;
  if (!job) return <div className="panel">Opening execution…</div>;
  const approval=job.status==="awaiting_approval"?job.result?.pending_approval:null;
  const approvalStep=approval==null?null:job.result?.steps?.[approval];
  return <section className="panel stack job-detail">
    <div className="spread"><div><span className="label">EXECUTION</span><h2>{job.prompt||"Analysis"}</h2></div>
      <span role="status" className={`pill ${job.status}`}>{healthLabel(job.status)}</span></div>
    <ErrorNote error={error??job.error}/>
    {!!job.trace.length&&<details className="details"><summary>Execution trace ({job.trace.length} steps)</summary>
      <ol className="trace">{job.trace.map((entry,i)=><li key={i}><strong>{entry.step}</strong> <small>{new Date(entry.at).toLocaleTimeString()}</small>
        {!!Object.keys(entry.details).length&&<pre>{JSON.stringify(entry.details,null,2)}</pre>}</li>)}</ol></details>}
    {!!job.result?.steps?.length&&<details className="details" open={approval!=null}>
      <summary>Workflow plan</summary><ol>{job.result.steps.map((step,index)=><li key={index}>{step.prompt}
        {step.require_approval||step.external?" · approval required":""}</li>)}</ol></details>}
    {approvalStep&&<p role="status">Step {(approval??0)+1} needs approval. {approvalStep.prompt}
      {approvalStep.external&&" Approval allows this step to send its request to the configured provider."}</p>}
    {!context.readOnly&&<div className="inline">{approval!=null&&<Button disabled={busy} onClick={()=>command(`approve/${approval}`)}>Approve step</Button>}
      {!finished(job.status)&&<Button variant="outline" disabled={busy} onClick={()=>command("cancel")}>Cancel job</Button>}
      {["failed","canceled"].includes(job.status)&&<Button variant="outline" disabled={busy} onClick={()=>command("retry")}>Retry job</Button>}</div>}
    {job.result&&<ResultView result={job.result} context={context}/>}
    {job.result?.chart&&!context.readOnly&&<form onSubmit={save} className="save-dashboard">
      <label>Dashboard title<input value={title} onChange={event=>setTitle(event.target.value)} required minLength={2} maxLength={100}/></label>
      <Button variant="outline" disabled={busy}><Save size={16}/> Save dashboard</Button></form>}
    {saved&&<p className="success" role="status">{saved} <Link className="text-link" href={context.base+"/dashboards"}>View dashboards</Link></p>}
  </section>;
}

export function AnalysisStudio({context,section}: {context:Context;section:keyof typeof modes}) {
  const {base,datasets,project,readOnly,roles,config}=context;
  const queue=useJobs(context);
  const cache=useQueryClient();
  const [jobId,setJobId]=useState(""),[selected,setSelected]=useState(""),[external,setExternal]=useState(false);
  const [error,setError]=useState<unknown>(null),[pending,setPending]=useState(false),[forecastMode,setForecastMode]=useState("forecast");
  const [chartType,setChartType]=useState("bar"),[aggregation,setAggregation]=useState("sum"),[features,setFeatures]=useState<string[]>([]);
  const [assignment,setAssignment]=useState<string[]>(project.roles),[followUp,setFollowUp]=useState("");
  const [extraSteps,setExtraSteps]=useState<{prompt:string;require_approval:boolean}[]>([]);
  const [claimSubject,setClaimSubject]=useState("");
  const version=selected||datasets[0]?.versions[0]?.id||"";
  const columns=getVersion(datasets,version)?.profile.columns??[];
  const research=section==="research";
  const earlier=queue.data?.filter(j=>j.kind==="analysis")??[];
  const blocked=readOnly || (research ? !config.research : !version);
  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(null);setPending(true);
    const form=event.currentTarget, data=Object.fromEntries(new FormData(form));
    const mode=section==="visualize"?"chart":section==="forecast"?forecastMode:research?"research":"analysis";
    const label=mode==="chart"?`${chartType} chart for ${String(data.x)}`:mode==="forecast"?"Forecast "+String(data.value):
      mode==="model"?"Evaluate a model for "+String(data.value):mode==="compare"?"Compare group means for "+String(data.value):String(data.prompt);
    const payload={prompt:label.trim(),mode,roles:section==="chat"?assignment:undefined,version_id:research?null:version,
      approve_external:external,date:String(data.date??""),value:String(data.value??""),horizon:Number(data.horizon??6),
      classification:data.classification==="classification",features:mode==="model"?features:[],
      chart:mode==="chart"?{type:chartType,x:data.x,y:data.y??"",aggregation}:null,previous_job_id:section==="chat"&&followUp?followUp:null,
      plan_from_prompt:section==="chat"&&!extraSteps.length&&data.plan_from_prompt==="on",
      steps:section==="chat"&&extraSteps.length?[{prompt:label.trim(),approve_external:external},...extraSteps]:[],
      claims:research&&claimSubject.trim()?[{subject:claimSubject.trim(),percent:String(data.percent)}]:[]};
    try {
      const job=await api<Job>(base+"/analyses",json("POST",payload));
      cache.setQueryData(["job",project.id,job.id],job);
      setJobId(job.id);setExternal(false);
      await queue.refetch();
    }catch(problem){setError(problem);}finally{setPending(false);}
  }
  const fields = (label:string,name:string,optional=false)=><label>{label}<select key={version+name} name={name} required={!optional}>
    <option value="">{optional?"None":"Choose a column"}</option>{columns.map(c=><option key={c.name}>{c.name}</option>)}</select></label>;
  return <>
    <Heading title={modes[section][0]} description={modes[section][1]}/>
    {section==="chat"&&config.llm==="none"&&<p className="panel muted">Deterministic analyses are available. AI-powered planning requires a configured OpenAI or Gemini API key.</p>}
    {research&&!config.research ? <Empty title="Research provider unavailable" description="Live source discovery becomes available when an operator configures Brave Search."/>
      :!research&&!datasets.length?<NoDataset base={base}/>:!readOnly&&<form className="panel stack" onSubmit={submit}>
      <div className="spread"><h2>{section==="chat"?<><Bot size={19}/> New analysis</>:modes[section][0]}</h2></div>
      {!research&&<VersionSelect datasets={datasets} value={version} onChange={value=>{setSelected(value);setFeatures([]);}}/>}
      {(section==="chat"||research)&&<label>{research?"Research question":"Analysis request"}<textarea name="prompt" rows={4}
        minLength={3} maxLength={2000} required placeholder={research?"e.g. Recent trends in retail inventory forecasting":"e.g. Total revenue by region"}/></label>}
      {section==="chat"&&<><fieldset><legend>Analysts for this request</legend><div className="chips">{roles.filter(role=>project.roles.includes(role.id)).map(role=>
        <label className="check-chip" key={role.id}><input type="checkbox" checked={assignment.includes(role.id)} onChange={event=>
          setAssignment(event.target.checked?[...assignment,role.id]:assignment.filter(id=>id!==role.id))}/>{role.name}</label>)}</div></fieldset>
        {!!earlier.some(j=>j.status==="completed")&&<label>Follow up on<select value={followUp} onChange={e=>setFollowUp(e.target.value)}>
          <option value="">New analysis</option>{earlier.filter(j=>j.status==="completed").map(j=><option key={j.id} value={j.id}>{j.prompt}</option>)}</select></label>}</>}
      {section==="chat"&&<fieldset className="stack"><legend>Workflow steps</legend>
        {!extraSteps.length&&<label className="checkbox"><input type="checkbox" name="plan_from_prompt"/>
          Plan requests separated by “then” and review before execution</label>}
        {extraSteps.map((step,i)=><div className="stack" key={i}>
          <label>Step {i+2} request<input value={step.prompt} minLength={3} maxLength={2000} required
            onChange={event=>setExtraSteps(extraSteps.map((entry,index)=>index===i?{...entry,prompt:event.target.value}:entry))}/></label>
          <div className="inline"><label className="checkbox"><input type="checkbox" checked={step.require_approval}
            onChange={event=>setExtraSteps(extraSteps.map((entry,index)=>index===i?{...entry,require_approval:event.target.checked}:entry))}/> Require approval</label>
            <Button type="button" variant="outline" onClick={()=>setExtraSteps(extraSteps.filter((_,index)=>index!==i))}>Remove step</Button></div>
        </div>)}
        <div><Button type="button" variant="outline" disabled={extraSteps.length>=5}
          onClick={()=>setExtraSteps([...extraSteps,{prompt:"",require_approval:false}])}>Add analysis step</Button></div></fieldset>}
      {research&&<div className="form-grid">
        <label>Claim subject (optional)<input value={claimSubject} minLength={5} maxLength={180}
          onChange={event=>setClaimSubject(event.target.value)} placeholder="e.g. North region 2025 adoption"/></label>
        <label>Claim percentage<input type="number" min={-1000000} max={1000000} step="any" name="percent"
          disabled={!claimSubject.trim()} required={!!claimSubject.trim()}/></label></div>}
      {(research || (section==="chat"&&config.llm!=="none"))&&<label className="checkbox"><input type="checkbox" checked={external}
        onChange={e=>setExternal(e.target.checked)} required={research}/>{research?"Send this research query to Brave Search":
          `Allow sending this request and column names/types to ${config.llm}`}</label>}
      {section==="visualize"&&<div className="form-grid">
        <label>Chart type<select value={chartType} onChange={e=>setChartType(e.target.value)}>
          {["bar","line","pie","scatter","histogram","heatmap","kpi","table"].map(kind=><option value={kind} key={kind}>{healthLabel(kind)}</option>)}</select></label>
        {fields("Category or field","x")}{fields("Measure","y",true)}
        <label>Aggregation<select value={aggregation} onChange={e=>setAggregation(e.target.value)}>
          <option value="sum">Sum</option><option value="mean">Mean</option><option value="count">Count</option></select></label>
      </div>}
      {section==="forecast"&&<><div className="form-grid">
        <label>Workflow<select value={forecastMode} onChange={e=>setForecastMode(e.target.value)}>
          <option value="forecast">Time-series forecast</option><option value="model">Predictive model</option><option value="compare">Compare two groups</option></select></label>
        {fields(forecastMode==="compare"?"Group field":forecastMode==="model"?"Order by (optional)":"Date field","date",forecastMode==="model")}
        {fields(forecastMode==="model"?"Target field":"Outcome field","value")}
        {forecastMode==="forecast"&&<label>Forecast horizon<input name="horizon" type="number" min={1} max={30} defaultValue={6} required/></label>}
        {forecastMode==="model"&&<label>Model type<select name="classification">
          <option value="regression">Linear regression</option><option value="classification">Logistic classification</option></select></label>}
      </div>{forecastMode==="model"&&<fieldset><legend>Feature columns</legend><div className="chips">{columns.map(column=><label key={column.name} className="check-chip">
        <input type="checkbox" checked={features.includes(column.name)} onChange={e=>setFeatures(e.target.checked?[...features,column.name]:
          features.filter(name=>name!==column.name))}/>{column.name}</label>)}</div></fieldset>}</>}
      <ErrorNote error={error}/>
      <div><Button disabled={blocked||pending||(section==="chat"&&!assignment.length)||(section==="forecast"&&forecastMode==="model"&&!features.length)}>
        <Sparkles size={17}/> {pending?"Submitting…":section==="visualize"?"Generate chart":research?"Search sources":"Run analysis"}</Button></div>
    </form>}
    {jobId&&<JobView context={context} id={jobId} key={jobId}/>}
    {section==="chat"&&!!earlier.length&&<section className="panel stack"><h2>Conversation history</h2>
      {earlier.slice(0,20).map(job=><button className="list-button spread" key={job.id} onClick={()=>setJobId(job.id)}>
        <span>{job.prompt}</span><span className={`pill ${job.status}`}>{healthLabel(job.status)}</span></button>)}</section>}
  </>;
}

export function Dashboards({context}: {context:Context}) {
  const {base,project,readOnly}=context;
  const saved=useQuery({queryKey:["dashboards",project.id],queryFn:()=>api<Dashboard[]>(base+"/dashboards")});
  const jobs=useJobs(context), candidates=jobs.data?.filter(job=>job.has_chart)??[];
  const [chosen,setChosen]=useState<string[]>([]),[error,setError]=useState<unknown>(null),[busy,setBusy]=useState(false);
  const [shareLinks,setShareLinks]=useState<Record<string,string>>({});
  const cache=useQueryClient();
  async function share(id:string, enabled:boolean) {
    setBusy(true);setError(null);
    try {
      const path=`${base}/dashboards/${id}/share`;
      const response=enabled ? await api<{path:string}>(path,json("POST",{confirmed:true})) :
        await api<void>(path,{method:"DELETE"});
      setShareLinks(previous=>({...previous,[id]:response?window.location.origin+response.path:""}));
      await cache.invalidateQueries({queryKey:["dashboards",project.id]});
    } catch(problem){setError(problem);} finally{setBusy(false);}
  }
  async function build(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setError(null);setBusy(true);
    const form=event.currentTarget;
    try {
      await api(base+"/dashboards",json("POST",{title:new FormData(form).get("title"),job_ids:chosen}));
      await saved.refetch();setChosen([]);form.reset();
    }catch(problem){setError(problem);}finally{setBusy(false);}
  }
  return <><Heading title="Dashboards" description="Reopen saved dashboards, filter chart data, and share with workspace members."/>
    <ErrorNote error={saved.error??jobs.error}/>
    {!readOnly&&candidates.length>1&&<form className="panel stack" onSubmit={build}><h2>Build a dashboard</h2>
      <label>Title<input name="title" required minLength={2} maxLength={100}/></label>
      <fieldset><legend>Charts (up to six)</legend><div className="chips">{candidates.map(job=>
        <label className="check-chip" key={job.id}><input type="checkbox" checked={chosen.includes(job.id)}
          disabled={chosen.length>=6&&!chosen.includes(job.id)} onChange={event=>setChosen(event.target.checked?
            [...chosen,job.id]:chosen.filter(id=>id!==job.id))}/>{job.prompt}</label>)}</div></fieldset>
      <ErrorNote error={error}/><div><Button disabled={busy||!chosen.length}>Create dashboard</Button></div></form>}
    {saved.data?.length===0&&<Empty title="No dashboards yet" description="Generate a chart and save it from the execution results.">
      <Button asChild variant="outline"><Link href={base+"/visualize"}>Build a visualization <ArrowRight size={15}/></Link></Button></Empty>}
    {saved.data?.map(view=><section className="panel stack" key={view.id} id={view.id}>
      <div className="spread"><h2>{view.title}</h2><div className="inline"><Link className="text-link" href={`${base}/dashboards#${view.id}`}>Dashboard link</Link>
        <Button asChild><a href={`/api${base}/dashboards/${view.id}/export?format=png`}><Download size={15}/> Download PNG</a></Button>
        <Button asChild variant="outline"><a href={`/api${base}/dashboards/${view.id}/export`}>Export CSV</a></Button>
        <Button asChild variant="outline"><a href={`/api${base}/dashboards/${view.id}/export?format=plotly`}>Plotly JSON</a></Button></div></div>
      <DashboardCharts chart={view.chart}/>
      {!readOnly&&<details className="details"><summary>Public sharing</summary>
        <p>Anyone with the link can read this dashboard and the data shown in its charts. Creating a link revokes the previous link.</p>
        <div className="inline">
          <Button variant="outline" disabled={busy} onClick={()=>share(view.id,true)}>{view.shared?"Replace public link":"Create public link"}</Button>
          {view.shared&&<Button variant="outline" disabled={busy} onClick={()=>share(view.id,false)}>Revoke public link</Button>}
        </div>
        {view.shared&&shareLinks[view.id]&&<label>Read-only link<input readOnly value={shareLinks[view.id]} onFocus={event=>event.target.select()}/></label>}
        <ErrorNote error={error}/>
      </details>}</section>)}
  </>;
}

export function Reports({context}: {context:Context}) {
  const {base,project,readOnly}=context;
  const jobs=useJobs(context),cache=useQueryClient();
  const [error,setError]=useState<unknown>(null),[id,setId]=useState(""),[busy,setBusy]=useState(false);
  const completed=jobs.data?.filter(j=>j.status==="completed"&&j.kind==="analysis")??[];
  const reports=jobs.data?.filter(j=>j.kind==="report")??[];
  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setError(null);setBusy(true);
    try {
      const job=await api<Job>(base+"/reports",json("POST",Object.fromEntries(new FormData(event.currentTarget))));
      cache.setQueryData(["job",project.id,job.id],job);
      setId(job.id);await jobs.refetch();
    }catch(problem){setError(problem);}finally{setBusy(false);}
  }
  return <><Heading title="Reports" description="Generate downloadable reports with calculations, evidence, and source metadata."/>
    {!completed.length&&!jobs.isPending&&<Empty title="Run an analysis to create a report" description="Completed analysis results can be exported in six formats.">
      <Button asChild variant="outline"><Link href={base+"/chat"}>Open AI analysts <ArrowRight size={15}/></Link></Button></Empty>}
    {!!completed.length&&!readOnly&&<form className="panel stack" onSubmit={submit}><h2>Generate a report</h2>
      <label>Completed analysis<select name="job_id" required>{completed.map(job=><option key={job.id} value={job.id}>{job.prompt}</option>)}</select></label>
      <div className="form-grid"><label>Report title<input name="title" required minLength={2} maxLength={100}/></label>
        <label>Format<select name="format">{[["pdf","PDF"],["xlsx","Excel"],["pptx","PowerPoint"],["csv","CSV"],["md","Markdown"],["html","HTML"]].map(([value,label])=>
          <option key={value} value={value}>{label}</option>)}</select></label></div>
      <ErrorNote error={error}/><div><Button disabled={busy}><Play size={16}/> Generate report</Button></div></form>}
    {id&&<JobView context={context} id={id} key={id}/>}
    <section className="panel stack"><h2>Report history</h2><ErrorNote error={jobs.error}/>
      {reports.length===0&&<p className="muted">Generated reports will appear here.</p>}
      {reports.map(row=><div className="spread list-row" key={row.id}><button className="text-button" onClick={()=>setId(row.id)}>{row.prompt}</button>
        {row.result?.artifact_id ? <a className="text-link" href={`/api${base}/artifacts/${row.result.artifact_id}`}><Download size={15}/> {row.result.format?.toUpperCase()}</a>
          :<span className={`pill ${row.status}`}>{healthLabel(row.status)}</span>}</div>)}</section>
  </>;
}

export function Jobs({context,history}: {context:Context;history:boolean}) {
  const {base}=context, executions=useJobs(context);
  const [selection,setSelection]=useState(""),[filter,setFilter]=useState("");
  const rows=executions.data?.filter(row=>(!history||row.kind==="analysis")&&(!filter||row.status===filter))??[];
  return <><Heading title={history?"Analysis history":"Execution & schedules"}
    description={history?"Reopen results and see how a previous analysis ran.":"Track jobs, inspect failures, or approve a recurring analysis."}/>
    <section className="panel stack"><div className="spread"><h2>{history?"Previous analyses":"Recent jobs"}</h2>
      <label>Filter by status<select value={filter} onChange={e=>setFilter(e.target.value)}><option value="">All statuses</option>
        {["queued","running","completed","failed","canceled"].map(status=><option key={status} value={status}>{healthLabel(status)}</option>)}</select></label></div>
      <ErrorNote error={executions.error}/>
      {!rows.length&&!executions.isPending&&<p className="muted">No jobs match this view. <Link className="text-link" href={base+"/chat"}>Run an analysis</Link></p>}
      {rows.map(row=><button className="list-button spread" key={row.id} onClick={()=>setSelection(row.id)}>
        <span>{row.prompt||row.kind}<small className="muted block">{new Date(row.created_at).toLocaleString()}</small></span>
        <span className={`pill ${row.status}`}>{healthLabel(row.status)}</span></button>)}
    </section>
    {selection&&<JobView context={context} id={selection} key={selection}/>}
    {!history&&<Schedules context={context}/>}
  </>;
}

function Schedules({context}: {context:Context}) {
  const {base,datasets,project,readOnly}=context;
  const list=useQuery({queryKey:["schedules",project.id],queryFn:()=>api<Schedule[]>(base+"/schedules")});
  const [selected,setSelected]=useState(""),[error,setError]=useState<unknown>(null),[busy,setBusy]=useState(false);
  const version=selected||datasets[0]?.versions[0]?.id||"";
  async function submit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();setError(null);setBusy(true);
    const form=event.currentTarget, fields=Object.fromEntries(new FormData(form));
    try {
      await api(base+"/schedules",json("POST",{prompt:fields.prompt,version_id:version,interval_minutes:Number(fields.interval),approved:fields.approved==="on"}));
      form.reset();await list.refetch();
    }catch(problem){setError(problem);}finally{setBusy(false);}
  }
  async function stop(id:string) {
    setError(null);setBusy(true);
    try {await api(base+"/schedules/"+id,{method:"DELETE"});await list.refetch();}
    catch(problem){setError(problem);}finally{setBusy(false);}
  }
  return <section className="panel stack"><h2>Recurring analyses</h2>
    {!readOnly&&!!datasets.length&&<form className="stack" onSubmit={submit}>
      <label>Scheduled request<input name="prompt" required minLength={3} maxLength={2000} placeholder="Total revenue by region"/></label>
      <div className="form-grid"><VersionSelect datasets={datasets} value={version} onChange={setSelected}/>
        <label>Interval in minutes<input type="number" name="interval" min={15} max={43200} defaultValue={1440} required/></label></div>
      <label className="checkbox"><input type="checkbox" name="approved" required/> Approve recurring analysis of this version</label>
      <div><Button disabled={busy}>Create schedule</Button></div></form>}
    <ErrorNote error={error??list.error}/>
    {list.data?.length===0&&<p className="muted">No saved schedules.</p>}
    {list.data?.map(schedule=><div className="spread list-row" key={schedule.id}><div><b>{schedule.prompt}</b>
      <small className="muted block">{schedule.enabled?`Every ${schedule.interval_minutes} minutes · next ${new Date(schedule.next_at).toLocaleString()}`:"Stopped"}</small></div>
      {schedule.enabled&&!readOnly&&<Button variant="outline" disabled={busy} onClick={()=>stop(schedule.id)}>Stop schedule</Button>}</div>)}
  </section>;
}
