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
  await page.getByLabel("Filter groups").fill("South");
  await page.getByText("View chart data").click();
  await expect(page.getByRole("cell",{name:"70",exact:true})).toBeVisible();
  await expect(page.getByRole("cell",{name:"North",exact:true})).toHaveCount(0);

  await workspaceLink(page,"Reports").click();
  await page.getByLabel("Report title").fill("Regional revenue report");
  await page.getByLabel("Format",{exact:true}).selectOption("csv");
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
