import Link from "next/link";
import { ArrowRight, ArrowUpRight, ChartColumnIncreasing, Database, FileText, Layers3, PanelTop, ShieldCheck, Workflow } from "lucide-react";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";

const workflow = [
  [Database, "Bring your data", "Import spreadsheets, CSV files, and database snapshots. Profile fields and keep the original alongside each cleaned version."],
  [Workflow, "Run an analysis", "Choose the analysts for your project, ask a question, and inspect the SQL and calculations behind the findings."],
  [FileText, "Share the results", "Save charts and export your analysis as a PDF, Excel workbook, PowerPoint deck, or data file."],
] as const;

export default function Landing() {
  return <div className="landing">
    <header className="landing-header"><div className="landing-inner landing-nav"><Brand/>
      <nav aria-label="Main navigation"><a href="#workflow">Workflow</a><a href="#roles">Analyst roles</a></nav>
      <div className="inline"><Link className="plain-link" href="/login">Sign in</Link>
        <Button asChild><Link href="/register">Get started <ArrowUpRight size={15}/></Link></Button></div>
    </div></header>
    <main>
      <section className="landing-inner hero">
        <div className="hero-copy">
          <div className="eyebrow"><span className="status-dot"/> ANALYTICS WORKSPACE</div>
          <h1>From raw data<br/>to <em>decisions.</em></h1>
          <p>Bring your data and specialist analysts into one workspace. Run analyses, inspect the evidence, and share results your team can trace back to the source.</p>
          <div className="inline hero-actions"><Button asChild><Link href="/register">Create a workspace <ArrowRight size={17}/></Link></Button>
            <Button asChild variant="outline"><a href="#workflow">See how it works</a></Button></div>
          <div className="hero-note"><ShieldCheck size={16}/> Workspace access controls and versioned data</div>
        </div>
        <div className="hero-visual" aria-label="Illustration of an analysis workspace using sample data">
          <div className="example-window">
            <div className="windowbar"><div className="windowdots"><i/><i/><i/></div><span>Sample project</span><Layers3 size={15}/></div>
            <div className="example-body"><aside><div className="example-logo"><ChartColumnIncreasing size={14}/></div>
              <div className="fake-line active"/><div className="fake-line"/><div className="fake-line"/><div className="fake-line"/></aside>
              <div className="example-content"><div className="example-top"><div><small>SALES ANALYSIS</small><strong>Revenue overview</strong></div><span>Jan – Jun</span></div>
                <div className="example-metrics"><div><small>Total revenue</small><b>$184,500</b></div><div><small>Orders</small><b>1,246</b></div><div><small>Regions</small><b>4</b></div></div>
                <div className="example-chart"><div><b>Monthly revenue</b><small>Sample data</small></div><div className="illustration-bars">{[37,51,45,66,59,85].map((n,i)=>
                  <div key={i}><span style={{height:`${n}%`}}/><small>{["Jan","Feb","Mar","Apr","May","Jun"][i]}</small></div>)}</div></div>
              </div>
            </div>
          </div>
          <div className="example-pill"><span><ShieldCheck size={17}/></span><div><b>Calculation checked</b><small>Dataset version 2 · DuckDB</small></div></div>
        </div>
      </section>
      <section className="workflow-strip" id="workflow"><div className="landing-inner workflow-inner">
        <div className="section-heading"><h2>How it works</h2></div>
        <div className="workflow-grid">{workflow.map(([Icon,title,description])=><article key={title}><span className="icon-tile"><Icon size={21}/></span>
          <h3>{title}</h3><p>{description}</p></article>)}</div>
      </div></section>
      <section className="landing-inner roles-section" id="roles"><span className="icon-tile"><PanelTop size={20}/></span>
        <h2>Twelve analyst roles. One project.</h2><p>Combine specialists in data, business, market research, finance, marketing, sales, product, HR, operations, business intelligence, risk, and investment.</p>
        <Button asChild><Link href="/register">Choose your analysts <ArrowRight size={16}/></Link></Button>
      </section>
    </main>
    <footer className="landing-footer"><div className="landing-inner"><Brand/><Link href="/login">Sign in <ArrowRight size={14}/></Link></div></footer>
  </div>;
}
