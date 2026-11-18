import Link from "next/link";
import { ChartNoAxesCombined } from "lucide-react";

export function Brand({href="/"}: {href?:string}) {
  return <Link className="brand" href={href}><span className="brand-mark"><ChartNoAxesCombined size={19}/></span>
    <span>Analyst<span className="brand-second"> Workspace</span></span></Link>;
}
