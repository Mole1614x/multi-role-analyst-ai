import { notFound } from "next/navigation";
import { Home } from "@/components/home";

export default async function Page({params}: {params:Promise<{section?:string[]}>}) {
  const {section=[]}=await params;
  const page=section[0] ?? "dashboard";
  if (section.length>1 || !["dashboard","projects","team","settings","admin"].includes(page)) notFound();
  return <Home page={page}/>;
}
