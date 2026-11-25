import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost } from "@/lib/api";
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
  settlement_status:"CASH_RECORDED"|"PENDING_BANK_CONFIRMATION"|"PENDING_CHEQUE_CLEARANCE"|"CHEQUE_CLEARED";
  reconciliation_status:"UNRECONCILED"|"RECONCILED";
  bank_statement_reference?:string|null; cheque_encashment_date?:string|null; recorded_by:string; recorded_at:string;
};
type RegisterResponse = {
  rows:Movement[]; total_count:number; limit:number; offset:number;
  active_season:string; season_code:string; read_only:true;
  balances_calculated:false; currency:"TND";
};
type Account = {id:string;name:string;account_type:"CASH"|"BANK";active:boolean};
const money=(value:string)=>fmtMoney(value);
const sourceLabel=(type:string,ar:boolean)=>type==="WORKER_PAYMENT"?(ar?"دفع أجور العمال":"Paiement des salaires") : type==="TRADITIONAL_RECEIPT"?(ar?"قبض فاتورة العصر":"Encaissement facture de trituration"):type==="GS_SALE_PAYMENT"?(ar?"قبض مبيعات GS":"Encaissement vente GS"):type==="GS_SUPPLIER_PAYMENT"?(ar?"دفع لمزوّد":"Paiement fournisseur"):type;
const methodLabel=(method:string,ar:boolean)=>method==="CASH"?(ar?"نقداً":"Espèces"):method==="BANK_TRANSFER"?(ar?"تحويل بنكي":"Virement bancaire"):method==="CHEQUE"?(ar?"شيك":"Chèque"):method;
const statusLabel=(status:string,ar:boolean)=>status==="CASH_RECORDED"?(ar?"نقداً مسجّل":"Espèces enregistrées"):status==="PENDING_BANK_CONFIRMATION"?(ar?"بانتظار تأكيد البنك":"Confirmation bancaire en attente"):status==="PENDING_CHEQUE_CLEARANCE"?(ar?"بانتظار خلاص الشيك":"Compensation du chèque en attente"):status==="CHEQUE_CLEARED"?(ar?"تم تحصيل الشيك":"Chèque encaissé"):status;

export default function TreasuryMovementRegister(){
  const {lang}=useI18n(); const ar=lang==="ar";
  const [accountId,setAccountId]=useState(""); const [direction,setDirection]=useState("");
  const [status,setStatus]=useState(""); const [startDate,setStartDate]=useState(""); const [endDate,setEndDate]=useState("");
  const [offset,setOffset]=useState(0); const limit=50;
  const [selectedCheque,setSelectedCheque]=useState<Movement|null>(null);
  const [encashmentDate,setEncashmentDate]=useState(new Date().toISOString().slice(0,10));
  const [bankReference,setBankReference]=useState(""); const [statementVerified,setStatementVerified]=useState(false);
  const queryClient=useQueryClient();
  const confirmCheque=useMutation({
    mutationFn:()=>apiPost<Movement>(`/accounting/treasury/movements/${encodeURIComponent(selectedCheque!.id)}/confirm-encashment`,{
      encashment_date:encashmentDate,bank_reference:bankReference.trim(),confirm_bank_statement_verified:true,
    }),
    onSuccess:()=>{void queryClient.invalidateQueries({queryKey:["accounting-treasury-movement-register"]});void queryClient.invalidateQueries({queryKey:["accounting-treasury-accounts"]});setSelectedCheque(null);setBankReference("");setStatementVerified(false);},
  });
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
        <div><CardTitle className="text-base">{ar?"سجل حركات الخزينة والبنوك":"Registre des mouvements de trésorerie"}</CardTitle><CardDescription>{ar?"الحركات المسجّلة صراحةً من دفعات GS · الموسم":"Mouvements de caisse, chèques et paiements GS · saison"} {data.active_season}</CardDescription></div>
        <span className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-3 py-1 text-xs font-semibold text-stone-700"><ShieldCheck className="size-3.5"/>{ar?"قراءة فقط":"Lecture seule"}</span>
      </div>
    </CardHeader>
    <CardContent className="space-y-4">
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">{ar?"يعرض هذا السجل الحركات المسجّلة فقط. لا يحسب رصيداً افتتاحياً أو جارياً، ولا يعني أن التحويل أو الشيك تمت تسويتهما.":"Ce registre affiche les mouvements enregistrés. Un chèque reste en attente jusqu’à vérification de son crédit définitif sur le relevé bancaire et confirmation par un administrateur."}</div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <label className="grid gap-1 text-xs font-medium text-stone-600"><span>{ar?"الحساب":"Compte"}</span><select value={accountId} onChange={e=>{setAccountId(e.target.value);setOffset(0);}} className="rounded-lg border bg-white px-3 py-2 text-sm"><option value="">{ar?"كل الحسابات":"Tous les comptes"}</option>{(accountQuery.data?.accounts||[]).map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
        <label className="grid gap-1 text-xs font-medium text-stone-600"><span>{ar?"الاتجاه":"Sens"}</span><select value={direction} onChange={e=>{setDirection(e.target.value);setOffset(0);}} className="rounded-lg border bg-white px-3 py-2 text-sm"><option value="">{ar?"الكل":"Tous"}</option><option value="IN">{ar?"قبض":"Entrée"}</option><option value="OUT">{ar?"صرف":"Sortie"}</option></select></label>
        <label className="grid gap-1 text-xs font-medium text-stone-600"><span>{ar?"حالة التسوية":"État de règlement"}</span><select value={status} onChange={e=>{setStatus(e.target.value);setOffset(0);}} className="rounded-lg border bg-white px-3 py-2 text-sm"><option value="">{ar?"كل الحالات":"Tous les états"}</option><option value="CASH_RECORDED">{ar?"نقداً مسجّل":"Espèces enregistrées"}</option><option value="PENDING_BANK_CONFIRMATION">{ar?"بانتظار تأكيد البنك":"Virement en attente"}</option><option value="PENDING_CHEQUE_CLEARANCE">{ar?"بانتظار خلاص الشيك":"Chèque en attente"}</option><option value="CHEQUE_CLEARED">{ar?"شيك محصّل":"Chèque encaissé"}</option></select></label>
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
        <td className="px-2 py-3"><span className={`text-xs font-semibold ${row.reconciliation_status==="RECONCILED"?"text-emerald-700":"text-amber-800"}`}>{row.source_type==="WORKER_PAYMENT"?(ar?"مدفوع — مطابقة إدارية":"Payé — rapprochement administratif"):statusLabel(row.settlement_status,ar)}</span><div className="mt-1 text-xs text-stone-500">{row.reconciliation_status==="RECONCILED"?(row.source_type==="WORKER_PAYMENT"?(ar?"مطابق إدارياً":"Rapproché administrativement"):(ar?"مطابق":"Rapproché")):(ar?"غير مطابق":"Non rapproché")}</div>{row.bank_statement_reference&&<div className="mt-1 text-xs text-stone-500">{ar?"مرجع البنك":"Réf. banque"}: {row.bank_statement_reference}</div>}{(row.source_type==="TRADITIONAL_RECEIPT"||row.source_type==="GS_SALE_PAYMENT")&&row.direction==="IN"&&row.payment_method==="CHEQUE"&&row.settlement_status==="PENDING_CHEQUE_CLEARANCE"&&<button type="button" onClick={()=>{setSelectedCheque(row);setEncashmentDate(new Date().toISOString().slice(0,10));setBankReference("");setStatementVerified(false);}} className="mt-2 rounded-lg bg-emerald-700 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-800">{ar?"تأكيد تحصيل الشيك":"Confirmer l’encaissement"}</button>}</td>
      </tr>)}</tbody></table></div>}
      <div className="flex items-center justify-between gap-3">
        <button type="button" disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-limit))} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40">{ar?"السابق":"Précédent"}</button>
        <span className="text-xs text-stone-500">{ar?"صفحة":"Page"} {Math.floor(offset/limit)+1} / {Math.max(1,Math.ceil(data.total_count/limit))}</span>
        <button type="button" disabled={offset+limit>=data.total_count} onClick={()=>setOffset(offset+limit)} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40">{ar?"التالي":"Suivant"}</button>
      </div>
      {selectedCheque&&<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="cheque-confirm-title">
        <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl space-y-4">
          <div><h3 id="cheque-confirm-title" className="text-lg font-semibold text-stone-900">{ar?"تأكيد تحصيل الشيك":"Confirmer l'encaissement du chèque"}</h3><p className="mt-1 text-sm text-stone-600">{selectedCheque.source_document_number||selectedCheque.source_id} · {money(selectedCheque.amount_tnd)} TND</p></div>
          <label className="grid gap-1 text-sm font-medium text-stone-700"><span>{ar?"تاريخ التحصيل":"Date d’encaissement"}</span><input type="date" value={encashmentDate} onChange={e=>setEncashmentDate(e.target.value)} className="rounded-lg border px-3 py-2" required/></label>
          <label className="grid gap-1 text-sm font-medium text-stone-700"><span>{ar?"مرجع قيد البنك في كشف الحساب":"Référence de l’écriture bancaire sur le relevé"}</span><input value={bankReference} onChange={e=>setBankReference(e.target.value)} maxLength={120} className="rounded-lg border px-3 py-2" placeholder={ar?"مرجع القيد البنكي النهائي":"Référence du crédit bancaire définitif"} required/></label>
          <label className="flex items-start gap-2 text-sm text-stone-700"><input type="checkbox" checked={statementVerified} onChange={e=>setStatementVerified(e.target.checked)} className="mt-1"/><span>{ar?"أؤكد أنني تحققت من ظهور المبلغ كقيد دائن نهائي في كشف الحساب البنكي.":"Je confirme avoir vérifié que le montant apparaît comme un crédit définitif sur le relevé bancaire."}</span></label>
          {confirmCheque.isError&&<p className="text-sm text-red-700">{confirmCheque.error instanceof Error?confirmCheque.error.message:(ar?"تعذر تأكيد التحصيل":"Échec de la confirmation")}</p>}
          <div className="flex justify-end gap-2"><button type="button" onClick={()=>setSelectedCheque(null)} className="rounded-lg border px-3 py-2 text-sm">{ar?"إلغاء":"Annuler"}</button><button type="button" disabled={!encashmentDate||!bankReference.trim()||!statementVerified||confirmCheque.isPending} onClick={()=>confirmCheque.mutate()} className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">{confirmCheque.isPending?(ar?"جارٍ التأكيد…":"Confirmation…"):(ar?"تأكيد التحصيل":"Confirmer")}</button></div>
        </div>
      </div>}
    </CardContent>
  </Card>;
}
