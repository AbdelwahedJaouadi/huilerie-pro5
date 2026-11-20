import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, ClipboardCheck, RefreshCw, ShieldCheck } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type Account={id:string;name:string;account_type:"CASH"|"BANK";currency:"TND";active:boolean};
type CountRow={id:string;account_id:string;account_name_snapshot:string;count_date:string;counted_at:string;counted_amount_tnd:string;denomination_counts:Record<string,number>;notes?:string;expected_amount_calculated:false;variance_calculated:false};
type CountsResponse={rows:CountRow[];total_count:number;read_only:true;expected_cash_calculated:false;variance_calculated:false;currency:"TND"};
const denominations=["50.000","20.000","10.000","5.000","2.000","1.000","0.500","0.200","0.100","0.050","0.020","0.010","0.005"];
const fmt=(value:string)=>new Intl.NumberFormat(undefined,{minimumFractionDigits:3,maximumFractionDigits:3}).format(Number(value||0));
export default function CashCountRegister(){
 const {lang}=useI18n();const ar=lang==="ar";const qc=useQueryClient();
 const [accountId,setAccountId]=useState("");const [countDate,setCountDate]=useState("");const [notes,setNotes]=useState("");
 const [counts,setCounts]=useState<Record<string,string>>({});
 const accounts=useQuery({queryKey:["accounting-treasury-accounts"],queryFn:()=>apiGet<{accounts:Account[]}>("/accounting/treasury/accounts")});
 const cashAccounts=useMemo(()=> (accounts.data?.accounts||[]).filter(a=>a.active&&a.account_type==="CASH"&&a.currency==="TND"),[accounts.data]);
 const list=useQuery({queryKey:["accounting-cash-counts",accountId],queryFn:()=>apiGet<CountsResponse>(`/accounting/treasury/cash-counts?limit=50${accountId?"&account_id="+encodeURIComponent(accountId):""}`)});
 const previewMillimes=denominations.reduce((sum,d)=>sum+Math.round(Number(d)*1000)*Math.max(0,Math.floor(Number(counts[d]||0))),0);
 const previewAmount=(previewMillimes/1000).toFixed(3);
 const save=useMutation({
  mutationFn:()=>apiPost<CountRow>("/accounting/treasury/cash-counts",{account_id:accountId,count_date:countDate,denomination_counts:Object.fromEntries(denominations.filter(d=>counts[d]!==undefined&&counts[d]!=="").map(d=>[d,Number(counts[d])])),notes}),
  onSuccess:()=>{setCounts({});setNotes("");void qc.invalidateQueries({queryKey:["accounting-cash-counts"]});}
 });
 return <div className="space-y-4" data-testid="cash-count-register">
  <Card><CardHeader><div className="flex items-start gap-3"><div className="rounded-lg bg-emerald-50 p-2 text-emerald-700"><Banknote className="size-5"/></div><div><CardTitle className="text-base">{ar?"جرد الصندوق النقدي":"Comptage physique de caisse"}</CardTitle><CardDescription>{ar?"تسجيل القطع والأوراق النقدية المعدودة فعلياً، دون احتساب رصيد متوقع أو فرق":"Enregistrer les billets et pièces réellement comptés, sans calculer de solde théorique ni d’écart."}</CardDescription></div></div></CardHeader>
   <CardContent className="space-y-4">
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950"><ShieldCheck className="me-1 inline size-4"/>{ar?"هذا سجل إثبات للجرد فقط. لا ينشئ حركة خزينة ولا يغيّر الرصيد. لن نحسب الفرق قبل توثيق الرصيد الافتتاحي وإجراءات الصندوق.":"Il s’agit uniquement d’une preuve de comptage. Aucun mouvement ni solde n’est modifié. L’écart restera non calculé tant que le solde initial et les procédures de caisse ne sont pas validés."}</div>
    <div className="grid gap-3 sm:grid-cols-2">
     <label className="grid gap-1 text-sm"><span>{ar?"الصندوق":"Caisse"}</span><select value={accountId} onChange={e=>setAccountId(e.target.value)} className="rounded-lg border bg-white px-3 py-2"><option value="">{ar?"اختر الصندوق":"Choisir une caisse"}</option>{cashAccounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
     <label className="grid gap-1 text-sm"><span>{ar?"تاريخ الجرد":"Date du comptage"}</span><input type="date" value={countDate} onChange={e=>setCountDate(e.target.value)} className="rounded-lg border bg-white px-3 py-2"/></label>
    </div>
    <div><div className="mb-2 flex items-center justify-between"><h4 className="font-semibold text-sm">{ar?"تفصيل الفئات النقدية (TND)":"Détail des coupures (TND)"}</h4><span className="text-xs text-stone-500">{ar?"عدد القطع":"Quantité"}</span></div>
     <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">{denominations.map(d=><label key={d} className="flex items-center justify-between gap-2 rounded-lg border p-2"><span className="text-sm font-medium tabular-nums">{d}</span><input aria-label={`${d} TND count`} type="number" min="0" max="1000000" step="1" inputMode="numeric" value={counts[d]??""} onChange={e=>setCounts(v=>({...v,[d]:e.target.value.replace(/[^0-9]/g,"").slice(0,7)}))} className="w-20 rounded-md border px-2 py-1.5 text-right text-sm tabular-nums"/></label>)}</div>
    </div>
    <label className="grid gap-1 text-sm"><span>{ar?"ملاحظات (اختياري)":"Notes (facultatif)"}</span><textarea value={notes} onChange={e=>setNotes(e.target.value)} maxLength={1000} rows={2} className="rounded-lg border px-3 py-2"/></label>
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-stone-50 p-3"><div><p className="text-xs text-stone-500">{ar?"المجموع المحسوب من الفئات":"Total calculé à partir des coupures"}</p><p className="text-xl font-bold tabular-nums">{fmt(previewAmount)} TND</p></div><button type="button" disabled={!accountId||!countDate||!denominations.some(d=>counts[d]!==undefined&&counts[d]!=="")||save.isPending} onClick={()=>save.mutate()} className="inline-flex items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"><ClipboardCheck className="size-4"/>{save.isPending?(ar?"جارٍ الحفظ…":"Enregistrement…"):(ar?"حفظ محضر الجرد":"Enregistrer le comptage")}</button></div>
    {save.isError&&<p role="alert" className="text-sm text-red-700">{save.error.message}</p>}
   </CardContent>
  </Card>
  <Card><CardHeader><div className="flex items-center justify-between gap-2"><div><CardTitle className="text-base">{ar?"سجل عمليات الجرد":"Historique des comptages"}</CardTitle><CardDescription>{ar?"آخر 50 محضراً في الموسم النشط":"50 derniers comptages de la saison active"}</CardDescription></div><button type="button" onClick={()=>void list.refetch()} className="rounded-lg border p-2"><RefreshCw className="size-4"/></button></div></CardHeader><CardContent>
   {list.isPending?<p className="text-sm text-stone-500">{ar?"جارٍ التحميل…":"Chargement…"}</p>:list.isError?<p className="text-sm text-red-700">{ar?"تعذر تحميل السجل":"Impossible de charger l’historique"}</p>:list.data.rows.length===0?<p className="rounded-lg bg-stone-50 p-3 text-sm text-stone-500">{ar?"لا توجد عمليات جرد بعد":"Aucun comptage enregistré"}</p>:<div className="overflow-x-auto"><table className="w-full min-w-[540px] text-sm"><thead><tr className="border-b text-left text-xs text-stone-500"><th className="px-2 py-2">{ar?"التاريخ":"Date"}</th><th className="px-2 py-2">{ar?"الصندوق":"Caisse"}</th><th className="px-2 py-2 text-right">{ar?"المبلغ المعدود":"Montant compté"}</th><th className="px-2 py-2">{ar?"الحالة":"Statut"}</th></tr></thead><tbody>{list.data.rows.map(row=><tr key={row.id} className="border-b"><td className="px-2 py-3">{row.count_date}</td><td className="px-2 py-3">{row.account_name_snapshot}</td><td className="px-2 py-3 text-right font-semibold tabular-nums">{fmt(row.counted_amount_tnd)} TND</td><td className="px-2 py-3 text-xs text-amber-800">{ar?"الجرد محفوظ · الفرق غير محسوب":"Comptage enregistré · écart non calculé"}</td></tr>)}</tbody></table></div>}
  </CardContent></Card>
 </div>;
}
