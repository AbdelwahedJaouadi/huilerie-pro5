import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { fmtMoney, useI18n } from "@/lib/i18n";
import { AlertTriangle, ArrowDownLeft, ArrowUpRight, RefreshCw, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type Movement = {
  id:string; season_code:string; source_type:string; source_id:string;
  source_document_id?:string|null; source_document_number?:string|null;
  source_party_id?:string|null; movement_kind:string; direction:"IN"|"OUT";
  movement_type:"RECEIPT"|"DISBURSEMENT"; account_id:string;
  account_name_snapshot?:string|null; account_type?:string|null;
  amount_tnd:string; currency:"TND"; movement_date:string; payment_method:string;
  external_reference?:string|null;
  settlement_status:"CASH_RECORDED"|"PENDING_BANK_CONFIRMATION"|"PENDING_CHEQUE_CLEARANCE";
  reconciliation_status:"UNRECONCILED"; recorded_by:string; recorded_at:string;
};
type RegisterResponse = {
  rows:Movement[]; total_count:number; limit:number; offset:number;
  active_season:string; season_code:string; read_only:true;
  balances_calculated:false; currency:"TND";
};
type Account = {id:string;name:string;account_type:"CASH"|"BANK";active:boolean};
const money=(value:string)=>fmtMoney(value);
const sourceLabel=(type:string,ar:boolean)=>type==="GS_SALE_PAYMENT"?(ar?"قبض مبيعات GS":"Encaissement vente GS"):type==="GS_SUPPLIER_PAYMENT"?(ar?"دفع لمزوّد":"Paiement fournisseur"):type;
const methodLabel=(method:string,ar:boolean)=>method==="CASH"?(ar?"نقداً":"Espèces"):method==="BANK_TRANSFER"?(ar?"تحويل بنكي":"Virement bancaire"):method==="CHEQUE"?(ar?"شيك":"Chèque"):method;
const statusLabel=(status:string,ar:boolean)=>status==="CASH_RECORDED"?(ar?"نقداً مسجّل":"Espèces enregistrées"):status==="PENDING_BANK_CONFIRMATION"?(ar?"بانتظار تأكيد البنك":"Confirmation bancaire en attente"):status==="PENDING_CHEQUE_CLEARANCE"?(ar?"بانتظار خلاص الشيك":"Compensation du chèque en attente"):status;

export default function TreasuryMovementRegister(){
  const {lang}=useI18n(); const ar=lang==="ar";
  const [accountId,setAccountId]=useState(""); const [direction,setDirection]=useState("");
  const [status,setStatus]=useState(""); const [startDate,setStartDate]=useState(""); const [endDate,setEndDate]=useState("");
  const [offset,setOffset]=useState(0); const limit=50;
  const accountQuery=useQuery({queryKey:["accounting-treasury-accounts"],queryFn:()=>apiGet<{accounts:Account[]}>("/accounting/treasury/accounts"),staleTime:30000});
  const params=new URLSearchParams({limit:String(limit),offset:String(offset)});
  if(accountId)params.set("account_id",accountId);
  if(direction)params.set("direction",direction);
  if(status)params.set("settlement_status",status);
  if(startDate)params.set("start_date",startDate);
  if(endDate)params.set("end_date",endDate);
  const query=useQuery({
    queryKey:["accounting-treasury-movement-register",accountId,direction,status,startDate,endDate,offset],
    queryFn:()=>apiGet<RegisterResponse>(`/accounting/treasury/movements?${params.toString()}`),
    staleTime:10000,
  });
  const reset=()=>{setAccountId("");setDirection("");setStatus("");setStartDate("");setEndDate("");setOffset(0);};
  if(query.isPending)return <p className="p-4 text-sm text-stone-500">{ar?"جارٍ تحميل سجل الحركات…":"Chargement du registre des mouvements…"}</p>;
  if(query.isError||!query.data)return <Card className="border-red-200"><CardContent className="flex items-center gap-3 p-4 text-red-800"><AlertTriangle className="size-5"/>{ar?"تعذّر تحميل سجل الحركات.":"Impossible de charger le registre."}<button type="button" onClick={()=>void query.refetch()} className="ms-auto inline-flex items-center gap-2 rounded-lg border px-3 py-2"><RefreshCw className="size-4"/>{ar?"إعادة المحاولة":"Réessayer"}</button></CardContent></Card>;
  const data=query.data; const first=data.total_count===0?0:data.offset+1; const last=Math.min(data.offset+data.rows.length,data.total_count);
  return <Card data-testid="treasury-movement-register">
    <CardHeader>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><CardTitle className="text-base">{ar?"سجل حركات الخزينة والبنوك":"Registre des mouvements de trésorerie"}</CardTitle><CardDescription>{ar?"الحركات المسجّلة صراحةً من دفعات GS · الموسم":"Mouvements explicitement enregistrés depuis les paiements GS · saison"} {data.active_season}</CardDescription></div>
        <span className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold text-stone-700"><ShieldCheck className="size-3.5"/>{ar?"قراءة فقط":"Lecture seule"}</span>
      </div>
    </CardHeader>
    <CardContent className="space-y-4">
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">{ar?"يعرض هذا السجل الحركات المسجّلة فقط. لا يحسب رصيداً افتتاحياً أو جارياً، ولا يعني أن التحويل أو الشيك تمت تسويتهما.":"Ce registre affiche uniquement les mouvements enregistrés. Il ne calcule aucun solde d’ouverture ou courant et ne signifie pas qu’un virement ou un chèque est compensé."}</div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <label className="grid gap-1 text-xs font-medium text-stone-600"><span>{ar?"الحساب":"Compte"}</span><select value={accountId} onChange={e=>{setAccountId(e.target.value);setOffset(0);}} className="rounded-lg border bg-white px-3 py-2 text-sm"><option value="">{ar?"كل الحسابات":"Tous les comptes"}</option>{(accountQuery.data?.accounts||[]).map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
        <label className="grid gap-1 text-xs font-medium text-stone-600"><span>{ar?"الاتجاه":"Sens"}</span><select value={direction} onChange={e=>{setDirection(e.target.value);setOffset(0);}} className="rounded-lg border bg-white px-3 py-2 text-sm"><option value="">{ar?"الكل":"Tous"}</option><option value="IN">{ar?"قبض":"Entrée"}</option><option value="OUT">{ar?"صرف":"Sortie"}</option></select></label>
        <label className="grid gap-1 text-xs font-medium text-stone-600"><span>{ar?"حالة التسوية":"État de règlement"}</span><select value={status} onChange={e=>{setStatus(e.target.value);setOffset(0);}} className="rounded-lg border bg-white px-3 py-2 text-sm"><option value="">{ar?"كل الحالات":"Tous les états"}</option><option value="CASH_RECORDED">{ar?"نقداً مسجّل":"Espèces enregistrées"}</option><option value="PENDING_BANK_CONFIRMATION">{ar?"بانتظار تأكيد البنك":"Virement en attente"}</option><option value="PENDING_CHEQUE_CLEARANCE">{ar?"بانتظار خلاص الشيك":"Chèque en attente"}</option></select></label>
        <label className="grid gap-1 text-xs font-medium text-stone-600"><span>{ar?"من تاريخ":"Du"}</span><input type="date" value={startDate} max={endDate||undefined} onChange={e=>{setStartDate(e.target.value);setOffset(0);}} className="rounded-lg border bg-white px-3 py-2 text-sm"/></label>
        <label className="grid gap-1 text-xs font-medium text-stone-600"><span>{ar?"إلى تاريخ":"Au"}</span><input type="date" value={endDate} min={startDate||undefined} onChange={e=>{setEndDate(e.target.value);setOffset(0);}} className="rounded-lg border bg-white px-3 py-2 text-sm"/></label>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-stone-600">{ar?"عدد الحركات":"Mouvements"}: <strong className="tabular-nums">{data.total_count}</strong> · {ar?"المعروض":"Affichés"}: {first}–{last}</p>
        <button type="button" onClick={reset} className="rounded-lg border px-3 py-2 text-xs font-semibold text-stone-700">{ar?"إزالة المرشحات":"Effacer les filtres"}</button>
      </div>
      {data.rows.length===0?<p className="rounded-lg bg-stone-50 p-4 text-sm text-stone-500">{ar?"لا توجد حركات مطابقة للمرشحات.":"Aucun mouvement ne correspond aux filtres."}</p>:
      <div className="overflow-x-auto"><table className="w-full min-w-[950px] text-sm"><thead><tr className="border-b text-left text-xs text-stone-500">
        <th className="px-2 py-2">{ar?"التاريخ":"Date"}</th><th className="px-2 py-2">{ar?"المصدر / الوثيقة":"Source / document"}</th><th className="px-2 py-2">{ar?"الحساب":"Compte"}</th><th className="px-2 py-2">{ar?"الاتجاه":"Sens"}</th><th className="px-2 py-2">{ar?"طريقة الدفع":"Mode"}</th><th className="px-2 py-2 text-right">{ar?"المبلغ":"Montant"}</th><th className="px-2 py-2">{ar?"الحالة":"État"}</th>
      </tr></thead><tbody>{data.rows.map(row=><tr key={row.id} className="border-b last:border-0 align-top">
        <td className="px-2 py-3 tabular-nums">{row.movement_date}</td>
        <td className="px-2 py-3"><div className="font-medium">{sourceLabel(row.source_type,ar)}</div><div className="text-xs text-stone-500">{row.source_document_number||row.source_id}</div>{row.external_reference&&<div className="text-xs text-stone-500">{ar?"مرجع الدفع":"Réf. paiement"}: {row.external_reference}</div>}</td>
        <td className="px-2 py-3">{row.account_name_snapshot||row.account_id}</td>
        <td className="px-2 py-3"><span className={row.direction==="IN"?"inline-flex items-center gap-1 font-semibold text-emerald-700":"inline-flex items-center gap-1 font-semibold text-rose-700"}>{row.direction==="IN"?<ArrowDownLeft className="size-4"/>:<ArrowUpRight className="size-4"/>}{row.direction==="IN"?(ar?"قبض":"Entrée"):(ar?"صرف":"Sortie")}</span></td>
        <td className="px-2 py-3">{methodLabel(row.payment_method,ar)}</td>
        <td className="px-2 py-3 text-right font-semibold tabular-nums">{money(row.amount_tnd)} TND</td>
        <td className="px-2 py-3"><span className="text-xs font-semibold text-amber-800">{statusLabel(row.settlement_status,ar)}</span><div className="mt-1 text-xs text-stone-500">{ar?"غير مطابق":"Non rapproché"}</div></td>
      </tr>)}</tbody></table></div>}
      <div className="flex items-center justify-between gap-3">
        <button type="button" disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-limit))} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40">{ar?"السابق":"Précédent"}</button>
        <span className="text-xs text-stone-500">{ar?"صفحة":"Page"} {Math.floor(offset/limit)+1} / {Math.max(1,Math.ceil(data.total_count/limit))}</span>
        <button type="button" disabled={offset+limit>=data.total_count} onClick={()=>setOffset(offset+limit)} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40">{ar?"التالي":"Suivant"}</button>
      </div>
    </CardContent>
  </Card>;
}
