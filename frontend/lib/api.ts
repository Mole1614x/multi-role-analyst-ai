export class ApiError extends Error {
  constructor(public status: number, detail: string) { super(detail); }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init, credentials: "same-origin",
    headers: init.body && !(init.body instanceof FormData)
      ? { "Content-Type": "application/json", ...init.headers } : init.headers,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(response.status, error.detail ?? "The workspace service is unavailable.");
  }
  return response.status === 204 ? undefined as T : response.json();
}

export function json(method: string, data: unknown): RequestInit {
  return {method, body: JSON.stringify(data)};
}

export type Cell = string | number | boolean | null;
export type Row = Record<string, Cell>;
export type User = {id:string; email:string; name:string; admin:boolean};
export type Workspace = {id:string; name:string; role:string};
export type Project = {id:string; workspace_id:string; name:string; description:string; roles:string[]; created_at:string; access?:string};
export type Role = {id:string; name:string; template:string; tool:string; output:string; policy:string; columns:string[]};
export type Column = {name:string; type:string; missing:number; distinct:number; mean?:number; min?:number; max?:number; outliers?:number};
export type Profile = {rows:number; column_count:number; columns:Column[]; duplicates:number};
export type Step = {operation:string; column:string; value:string};
export type Version = {id:string; dataset_id:string; number:number; sha256:string; parent_id:string | null; profile:Profile; transformations:Step[]};
export type Dataset = {id:string; name:string; source:string; versions:Version[]};
export type QueryResult = {sql:string; columns:string[]; rows:Row[]; truncated:boolean; engine:string; source_versions?:string[]};
export type SavedQuery = {id:string; title:string; version_id:string; sql:string; result:QueryResult};
export type Chart = {type:string; x?:string; y?:string; columns?:string[]; rows:Row[]; method:string; truncated?:boolean; title?:string};
export type Finding = {role:string; metric:string; method:string; review:string; status:string; values?:Record<string,number|null>; reason?:string};
export type Evidence = {url:string; title:string; publisher:string; snippet:string; retrieved_at:string; assessment:string};
export type Result = {
  summary?:string; source?:{version_id:string; version:number; sha256:string}; plan?:{objective:string}; method?:string;
  chart?:Chart; query?:QueryResult; role_findings?:Finding[]; evidence?:Evidence[]; limitations?:string[];
  assumptions?:string[]; recommendations?:string[];
  provider_usage?:Record<string, unknown>; forecast?:Record<string, unknown>; model?:Record<string, unknown>;
  comparison?:Record<string, unknown>; artifact_id?:string; format?:string; title?:string; dataset_id?:string; version_id?:string;
};
export type Job = {id:string; kind:string; status:string; prompt:string; result:Result|null; error:string|null; created_at:string; attempt:number; has_chart:boolean;
  trace:{step:string; details:Record<string, unknown>; at:string}[]};
export type Dashboard = {id:string; title:string; job_id:string; chart:Chart | {panels:Chart[]}};
export type Schedule = {id:string; prompt:string; interval_minutes:number; next_at:string; enabled:boolean};
export type Config = {password_reset:boolean; llm:string; research:boolean};
