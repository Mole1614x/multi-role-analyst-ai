import { notFound } from "next/navigation";
import { ProjectView } from "@/components/project";

const pages = new Set(["","analysts","chat","datasets","clean","sql","visualize","dashboards","research","forecast","reports","history","jobs"]);
export default async function Page({params}: {params:Promise<{id:string;section?:string[]}>}) {
  const {id,section=[]}=await params;
  if (section.length>1 || !pages.has(section[0] ?? "")) notFound();
  return <ProjectView id={id} section={section[0] ?? ""}/>;
}
