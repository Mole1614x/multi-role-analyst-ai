import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { Buffer } from "node:buffer";

const password = "browser test password #24";
const sales = "date,region,revenue,expenses\n2025-01-01,North,100,60\n2025-01-02,South,70,40\n2025-01-03,North,50,30\n2025-01-03,North,50,30\n";

async function register(page:Page, name:string) {
  const email = `analyst-${crypto.randomUUID()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Full name").fill(name);
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password",{exact:true}).fill(password);
  await page.getByRole("button",{name:"Create your workspace"}).click();
  await expect(page.getByRole("heading",{name:`Welcome, ${name}.`})).toBeVisible();
  return email;
}

const workspaceLink = (page:Page, label:string) => page.getByRole("navigation",{name:"Workspace navigation"})
  .getByRole("link",{name:label,exact:true});

test("register, run multi-role analysis, save dashboard, download report and reopen",async({page})=>{
  const email=await register(page,"Taylor");
  await page.getByRole("link",{name:"Create a project",exact:true}).click();
  await page.getByLabel("Project name").fill("Quarterly revenue");
  await page.getByLabel("Description").fill("Compare revenue and margins by region.");
  await page.getByRole("checkbox",{name:/^Financial Analyst/}).check();
  await page.getByRole("checkbox",{name:/^Sales Analyst/}).check();
  await page.getByRole("button",{name:"Create project",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Quarterly revenue",exact:true})).toBeVisible();

  await workspaceLink(page,"Datasets").click();
  await page.getByLabel("Data file").setInputFiles({name:"sales.csv",mimeType:"text/csv",buffer:Buffer.from(sales)});
  await page.getByRole("button",{name:"Import dataset"}).click();
  await expect(page.getByText("Dataset imported.",{exact:true})).toBeVisible();
  await expect(page.getByText("1 duplicate rows")).toBeVisible();
  await expect(page.getByRole("heading",{name:"Data explorer"})).toBeVisible();

  await workspaceLink(page,"Cleaning studio").click();
  await page.getByRole("button",{name:"Preview changes"}).click();
  await expect(page.getByText(/4 → 3 rows/)).toBeVisible();
  await page.getByRole("button",{name:"Save cleaned version"}).click();
  await expect(page.getByText("Saved cleaned version 2.")).toBeVisible();

  await workspaceLink(page,"SQL studio").click();
  await page.getByLabel("Natural-language query").fill("Total revenue by region");
  await page.getByRole("button",{name:"Draft SQL"}).click();
  await expect(page.getByRole("textbox",{name:"SQL query",exact:true})).toHaveValue(/SUM\("revenue"\)/i);
  await page.getByRole("button",{name:"Run query"}).click();
  await expect(page.getByRole("cell",{name:"150",exact:true})).toBeVisible();

  await workspaceLink(page,"AI analysts").click();
  await expect(page.getByText(/AI-powered planning requires a configured/)).toBeVisible();
  await page.getByLabel("Analysis request").fill("Total revenue by region");
  await page.getByRole("button",{name:"Run analysis"}).click();
  await expect(page.getByText("3 role-specific metric groups computed.")).toBeVisible({timeout:30_000});
  await expect(page.getByText("Profit and margin",{exact:true})).toBeVisible();
  await page.getByText("View chart data").click();
  await expect(page.getByRole("cell",{name:"150",exact:true})).toBeVisible();
  await page.getByLabel("Dashboard title").fill("Regional dashboard");
  await page.getByRole("button",{name:"Save dashboard"}).click();
  await expect(page.getByText("Dashboard saved.")).toBeVisible();
  await workspaceLink(page,"Dashboards").click();
  await expect(page.getByRole("heading",{name:"Regional dashboard"})).toBeVisible();
  const dashboardDownload = page.waitForEvent("download");
  await page.getByRole("link",{name:"Download PNG"}).click();
  const image = await dashboardDownload;
  expect(image.suggestedFilename()).toBe("dashboard.png");
  const png = await readFile((await image.path())!);
  expect(png.subarray(0,8)).toEqual(Buffer.from([137,80,78,71,13,10,26,10]));
  await page.getByLabel("Filter groups").fill("South");
  await page.getByText("View chart data").click();
  await expect(page.getByRole("cell",{name:"70",exact:true})).toBeVisible();
  await expect(page.getByRole("cell",{name:"North",exact:true})).toHaveCount(0);

  await workspaceLink(page,"Reports").click();
  await page.getByLabel("Report title").fill("Regional revenue report");
  await page.getByRole("combobox",{name:"Format",exact:true}).selectOption("csv");
  await page.getByRole("button",{name:"Generate report"}).click();
  const report=page.getByRole("link",{name:"Download CSV"});
  await expect(report).toBeVisible({timeout:30_000});
  const downloadResult=page.waitForEvent("download");
  await report.click();
  const download=await downloadResult;
  expect(download.suggestedFilename()).toBe("analysis-report.csv");
  expect(await readFile((await download.path())!,"utf-8")).toContain("North,150");

  await page.getByRole("button",{name:"Sign out"}).click();
  await expect(page.getByRole("heading",{name:"Sign in"})).toBeVisible();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password",{exact:true}).fill(password);
  await page.getByRole("button",{name:"Sign in",exact:true}).click();
  await page.getByRole("link",{name:/^Quarterly revenue/}).click();
  await expect(page.getByRole("heading",{name:"Quarterly revenue"})).toBeVisible();
  await workspaceLink(page,"Analysis history").click();
  await expect(page.getByRole("button",{name:/Total revenue by region/})).toBeVisible();
});

test("mobile navigation, form validation, project empty state and theme",async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto("/");
  await expect(page.getByRole("heading",{name:"From raw data to decisions."})).toBeVisible();
  await expect(page.locator("body")).toHaveCSS("overflow-x","visible");
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByRole("link",{name:"Create a workspace"}).click();
  await page.getByRole("button",{name:"Create your workspace"}).click();
  await expect(page.getByLabel("Full name")).toBeFocused();
  await register(page,"Morgan");
  await page.getByRole("button",{name:"Open navigation"}).click();
  await workspaceLink(page,"Projects").click();
  await expect(page.getByRole("heading",{name:"No projects yet"})).toBeVisible();
  await page.getByRole("button",{name:"Use dark theme"}).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme","dark");
});

test("approve a workflow, filter dashboard panels, and revoke a public link",async({page,browser,baseURL})=>{
  await register(page,"Jamie");
  const workspace=(await (await page.request.get("/api/workspaces")).json())[0];
  const project=await page.request.post("/api/projects",{data:{
    workspace_id:workspace.id,name:"Workflow workspace",roles:["sales"],
  }});
  expect(project.status()).toBe(201);
  const id=(await project.json()).id;
  const base=`/projects/${id}`;
  const importResponse=await page.request.post(`/api${base}/datasets`,{multipart:{
    file:{name:"workflow.csv",mimeType:"text/csv",buffer:Buffer.from(sales)},
  }});
  expect([201,202]).toContain(importResponse.status());
  await expect.poll(async()=> (await (await page.request.get(`/api${base}/datasets`)).json()).length).toBe(1);

  await page.goto(base+"/chat");
  await page.getByLabel("Analysis request").fill("Total revenue by region");
  await page.getByRole("button",{name:"Add analysis step"}).click();
  await page.getByLabel("Step 2 request").fill("Average revenue by region");
  await page.getByLabel("Require approval").check();
  await page.getByRole("button",{name:"Run analysis"}).click();
  await expect(page.getByText(/Step 2 needs approval/)).toBeVisible();
  await page.reload();
  await page.getByRole("button",{name:/Total revenue by region/}).click();
  await page.getByRole("button",{name:"Approve step"}).click();
  await expect(page.getByText(/2 workflow steps completed/)).toBeVisible();
  await page.getByLabel("Dashboard title").fill("Workflow dashboard");
  await page.getByRole("button",{name:"Save dashboard"}).click();
  await expect(page.getByText("Dashboard saved.")).toBeVisible();

  const current=(await (await page.request.get(`/api${base}/datasets`)).json())[0].versions[0].id;
  const queued=await page.request.post(`/api${base}/analyses`,{data:{
    prompt:"Total expenses by region",version_id:current,
  }});
  expect(queued.status()).toBe(202);
  const other=(await queued.json()).id;
  await expect.poll(async()=> (await (await page.request.get(`/api${base}/jobs/${other}`)).json()).status).toBe("completed");
  await workspaceLink(page,"Dashboards").click();
  await page.getByRole("checkbox",{name:"Total expenses by region"}).check();
  await page.getByRole("checkbox",{name:"Total revenue by region"}).check();
  await page.getByLabel("Title",{exact:true}).fill("Compare both measures");
  await page.getByRole("button",{name:"Create dashboard"}).click();
  const dashboard=page.locator("section").filter({has:page.getByRole("heading",{name:"Compare both measures",exact:true})});
  await dashboard.getByLabel("Filter all charts by region").selectOption({label:"South"});
  for (const details of await dashboard.getByText("View chart data").all()) await details.click();
  await expect(dashboard.getByRole("cell",{name:"South",exact:true})).toHaveCount(2);
  await expect(dashboard.getByRole("cell",{name:"North",exact:true})).toHaveCount(0);

  await dashboard.getByText("Public sharing",{exact:true}).click();
  await dashboard.getByRole("button",{name:"Create public link"}).click();
  const link=dashboard.getByLabel("Read-only link");
  await expect(link).toHaveValue(/\/shared\/dashboard#/);
  const publicLink=await link.inputValue();
  const publicContext=await browser.newContext({baseURL});
  try {
    const guest=await publicContext.newPage();
    await guest.goto(publicLink);
    await expect(guest.getByRole("heading",{name:"Compare both measures"})).toBeVisible();
    await expect(guest.getByRole("heading",{name:"Workflow dashboard"})).toHaveCount(0);
    await expect(guest.getByRole("button",{name:"Revoke public link"})).toHaveCount(0);
    await dashboard.getByRole("button",{name:"Revoke public link"}).click();
    await expect(link).toHaveCount(0);
    await guest.reload();
    await expect(guest.getByText("This dashboard link is unavailable.")).toBeVisible();
  } finally {
    await publicContext.close();
  }
});
