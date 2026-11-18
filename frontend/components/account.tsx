"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Database, ShieldCheck, Workflow } from "lucide-react";
import { api, json } from "@/lib/api";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";

const copy = {
  login: ["Sign in", "Continue to your projects and saved analyses."],
  register: ["Create your workspace", "Set up an account to start your first analysis."],
  forgot: ["Reset your password", "Enter the email address associated with your account."],
  reset: ["Choose a new password", "Use at least twelve characters."],
};

export function AccountForm({mode, token}: {mode:keyof typeof copy; token?:string}) {
  const router = useRouter();
  const cache = useQueryClient();
  const [message,setMessage] = useState("");
  const [error,setError] = useState("");
  const [pending,setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(""); setMessage(""); setPending(true);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const result = await api<{message?:string}>(`/auth/${mode}`, json("POST", {...data, ...(mode === "reset" ? {token} : {})}));
      if (mode === "login" || mode === "register") {
        cache.clear(); router.push("/workspace");
      } else setMessage(result.message ?? "");
    } catch (problem) { setError(String((problem as Error).message)); }
    finally {setPending(false);}
  }
  return <main className="account">
    <div className="account-form-area"><Brand/><div className="account-card">
      <h1>{copy[mode][0]}</h1><p className="muted">{copy[mode][1]}</p>
      <form onSubmit={submit} className="stack">
        {mode === "register" && <label>Full name<input name="name" autoComplete="name" required maxLength={100}/></label>}
        {mode !== "reset" && <label>Email address<input name="email" type="email" autoComplete="email" required maxLength={254}/></label>}
        {mode !== "forgot" && <label>Password<input name="password" type="password" minLength={12} maxLength={200}
          autoComplete={mode === "login" ? "current-password" : "new-password"} required/></label>}
        {mode === "login" && <Link className="text-link" href="/forgot">Forgot password?</Link>}
        {error && <p className="error" role="alert">{error}</p>}
        {message && <p className="success" role="status">{message}</p>}
        <Button disabled={pending || (mode === "reset" && !token)}>{pending ? "Submitting…" :
          mode === "forgot" ? "Send reset link" : mode === "reset" ? "Update password" : copy[mode][0]} <ArrowRight size={16}/></Button>
      </form>
      <p className="account-link">{mode === "login" ? <>New to Analyst Workspace? <Link href="/register">Create an account</Link></>
        : <Link href="/login">Back to sign in</Link>}</p>
    </div></div>
    <aside className="account-art"><div className="account-art-inner"><div className="eyebrow">ANALYST WORKSPACE</div>
      <h2>Put your data<br/>to work.</h2>
      <div><Database size={20}/> Version and inspect your datasets</div><div><Workflow size={20}/> Run specialist workflows</div>
      <div><ShieldCheck size={20}/> Review calculations and sources</div></div></aside>
  </main>;
}
