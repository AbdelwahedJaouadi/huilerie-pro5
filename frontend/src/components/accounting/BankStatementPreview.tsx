import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, FileSpreadsheet, RefreshCw, ShieldCheck, Upload } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet, apiUpload } from "@/lib/api";
import { fmtMoney, useI18n } from "@/lib/i18n";

type Account={id:string;name:string;account_type:"CASH"|"BANK";active:boolean;currency?:string};
type Candidate={id:string;source_type:string;source_id:string;source_document_number?:string;amount_tnd:string;direction:"IN"|"OUT";movement_date:string;external_reference?:string;settlement_status:string};
type StatementRow={line_number:number;transaction_date:string;value_date?:string|null;amount_tnd:string;direction:"IN"|"OUT";reference?:string|null;description?:string|null;duplicate_in_file:boolean;match_status:string;candidate_count:number;candidates:Candidate[];automatic_match:false};
type Preview={account:{id:string;name:string};active_season:string;season_code:string;rows:StatementRow[];summary:{line_count:number;statuses:Record<string,number>};read_only:true;database_writes:false;automatic_match:false;imported:false;matching_window_days:number;currency:"TND"};
const statusText=(status:string,ar:boolean)=>{
 const labels:Record<string,[string,string]>={
  REFERENCE_CANDIDATE:["مرشح مطابق بالمرجع","Candidat par référence"],
  POSSIBLE_MATCH:["مطابقة محتملة","Correspondance possible"],
  AMBIGUOUS:["مطابقة غير محسومة","Correspondance ambiguë"],
  AMBIGUOUS_REFERENCE:["مرجع مكرر","Référence ambiguë"],
  REFERENCE_MISMATCH:["اختلاف المرجع","Référence différente"],
  UNMATCHED:["دون مطابقة","Sans correspondance"],
  DUPLICATE_IN_FILE:["مكرر داخل الملف","Doublon dans le fichier"],
 };
 return labels[status]?.[ar?0:1]||status;
};
export default function BankStatementPreview(){
 const {lang}=useI18n();const ar=lang==="ar";
 const [accountId,setAccountId]=useState("");const [file,setFile]=useState<File|null>(null);
 const accounts=useQuery({queryKey:["accounting-treasury-accounts"],queryFn:()=>apiGet<{accounts:Account[]}>("/accounting/treasury/accounts"),staleTime:30000});
 const bankAccounts=useMemo(()=> (accounts.data?.accounts||[]).filter(a=>a.active&&a.account_type==="BANK"&&(!a.currency||a.currency==="TND")),[accounts.data]);
 const preview=useMutation({
  mutationFn:async()=>{
   if(!file||!accountId)throw new Error(ar?"اختر الحساب والملف أولاً":"Sélectionnez un compte et un fichier CSV.");
   const form=new FormData();form.append("file",file);
   return apiUpload<Preview>(`/accounting/treasury/statement-preview?account_id=${encodeURIComponent(accountId)}`,form);
  },
 });
 const selected=bankAccounts.find(a=>a.id===accountId);
 const data=preview.data;
 return <Card data-testid="bank-statement-preview">
  <CardHeader>
   <div className="flex items-start gap-3"><div className="rounded-lg bg-blue-50 p-2 text-blue-700"><FileSpreadsheet className="size-5"/></div><div><CardTitle className="text-base">{ar?"معاينة كشف البنك":"Aperçu du relevé bancaire"}</CardTitle><CardDescription>{ar?"قراءة ملف CSV واقتراح حركات محتملة دون استيراد أو مطابقة تلقائية.":"Lecture d’un CSV et suggestions de mouvements, sans import ni rapprochement automatique."}</CardDescription></div></div>
  </CardHeader>
  <CardContent className="space-y-4">
   <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">{ar?"المبلغ والتاريخ وحدهما لا يثبتان المطابقة. كل النتائج اقتراحات للمراجعة فقط؛ لا تُحفظ بيانات الملف في قاعدة البيانات.":"Le montant et la date seuls ne prouvent pas une correspondance. Tous les résultats sont des suggestions à vérifier ; le fichier n’est pas enregistré en base."}</div>
   <div className="grid gap-3 md:grid-cols-2">
    <label className="grid gap-1 text-xs font-medium text-stone-600"><span>{ar?"الحساب البنكي":"Compte bancaire"}</span><select value={accountId} onChange={e=>{setAccountId(e.target.value);preview.reset();}} className="rounded-lg border bg-white px-3 py-2 text-sm"><option value="">{ar?"اختر حساباً بنكياً":"Choisir un compte bancaire"}</option>{bankAccounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
    <label className="grid gap-1 text-xs font-medium text-stone-600"><span>{ar?"ملف CSV (UTF-8، حد أقصى 2 Mo)":"Fichier CSV (UTF-8, 2 Mo maximum)"}</span><input type="file" accept=".csv,text/csv" onChange={e=>{setFile(e.target.files?.[0]||null);preview.reset();}} className="rounded-lg border bg-white px-3 py-2 text-sm file:me-3 file:rounded-md file:border-0 file:bg-stone-100 file:px-2 file:py-1"/></label>
   </div>
   <div className="flex flex-wrap items-center gap-3">
    <button type="button" disabled={!accountId||!file||preview.isPending} onClick={()=>preview.mutate()} className="inline-flex items-center gap-2 rounded-lg bg-stone-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"><Upload className="size-4"/>{preview.isPending?(ar?"جارٍ التحليل…":"Analyse…"):(ar?"معاينة الكشف":"Analyser le relevé")}</button>
    {selected&&<span className="text-xs text-stone-500">{selected.name} · TND</span>}
    {file&&<span className="text-xs text-stone-500">{file.name}</span>}
   </div>
   {accounts.isError&&<p className="text-sm text-red-700">{ar?"تعذّر تحميل الحسابات البنكية.":"Impossible de charger les comptes bancaires."}</p>}
   {preview.isError&&<div role="alert" className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"><AlertTriangle className="size-4"/>{preview.error instanceof Error?preview.error.message:(ar?"فشلت المعاينة":"Échec de l’aperçu")}<button type="button" onClick={()=>preview.mutate()} className="ms-auto inline-flex items-center gap-1 underline"><RefreshCw className="size-3"/>{ar?"إعادة":"Réessayer"}</button></div>}
   {data&&<>
    <div className="flex flex-wrap items-center justify-between gap-2"><div><h4 className="font-semibold">{ar?"نتيجة المعاينة":"Résultat de l’aperçu"} · {data.account.name}</h4><p className="text-xs text-stone-500">{ar?"الموسم النشط":"Saison active"}: {data.active_season} · {data.summary.line_count} {ar?"سطر":"lignes"}</p></div><span className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold"><ShieldCheck className="size-3.5"/>{ar?"لم يتم الاستيراد":"Non importé"}</span></div>
    <div className="flex flex-wrap gap-2">{Object.entries(data.summary.statuses).map(([status,count])=><span key={status} className="rounded-full border px-2.5 py-1 text-xs">{statusText(status,ar)}: <strong>{count}</strong></span>)}</div>
    <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-sm"><thead><tr className="border-b text-left text-xs text-stone-500"><th className="px-2 py-2">#</th><th className="px-2 py-2">{ar?"التاريخ":"Date"}</th><th className="px-2 py-2">{ar?"المرجع":"Référence"}</th><th className="px-2 py-2">{ar?"الاتجاه":"Sens"}</th><th className="px-2 py-2 text-right">{ar?"المبلغ":"Montant"}</th><th className="px-2 py-2">{ar?"نتيجة المقارنة":"Résultat"}</th><th className="px-2 py-2">{ar?"الحركات المقترحة":"Mouvements candidats"}</th></tr></thead><tbody>{data.rows.map(row=><tr key={row.line_number} className="border-b align-top"><td className="px-2 py-3">{row.line_number}</td><td className="px-2 py-3 tabular-nums">{row.transaction_date}{row.value_date&&<div className="text-xs text-stone-500">{ar?"تاريخ القيمة":"Valeur"}: {row.value_date}</div>}</td><td className="px-2 py-3">{row.reference||"—"}{row.description&&<div className="max-w-48 truncate text-xs text-stone-500">{row.description}</div>}</td><td className="px-2 py-3">{row.direction==="IN"?(ar?"قبض":"Entrée"):(ar?"صرف":"Sortie")}</td><td className="px-2 py-3 text-right font-semibold tabular-nums">{fmtMoney(row.amount_tnd)} TND</td><td className="px-2 py-3"><span className={row.duplicate_in_file?"font-semibold text-rose-700":"font-semibold text-amber-800"}>{statusText(row.match_status,ar)}</span></td><td className="px-2 py-3">{row.candidates.length?row.candidates.map(c=><div key={c.id} className="mb-1 rounded-md bg-stone-50 p-2 text-xs"><strong>{c.source_document_number||c.id}</strong> · {c.movement_date} · {fmtMoney(c.amount_tnd)} TND<div className="text-stone-500">{c.external_reference||c.source_type}</div></div>):<span className="text-xs text-stone-400">—</span>}</td></tr>)}</tbody></table></div>
    <p className="text-xs text-stone-500">{ar?"نطاق البحث ± 7 أيام. لم يتم إنشاء أي حركة أو ربط أو تعديل أي سجل.":"Fenêtre de recherche ± 7 jours. Aucun mouvement, lien ou enregistrement n’a été créé ou modifié."}</p>
   </>}
  </CardContent>
 </Card>;
}
