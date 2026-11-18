import { notFound } from "next/navigation";
import { AccountForm } from "@/components/account";

export default async function AccountPage({params, searchParams}: {
  params: Promise<{account:string}>; searchParams: Promise<{token?:string}>;
}) {
  const {account} = await params;
  const {token} = await searchParams;
  if (account !== "login" && account !== "register" && account !== "forgot" && account !== "reset") notFound();
  return <AccountForm mode={account} token={token}/>;
}
