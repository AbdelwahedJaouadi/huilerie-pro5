import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { useI18n, fmtMoney } from "@/lib/i18n";
import { AlertTriangle, ArrowDownLeft, ArrowUpRight, RefreshCw, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type Candidate = {
  candidate_key: string; source_type: string; source_id: string;
  source_document_number?: string | null; business_date?: string | null;
  direction: "IN" | "OUT"; account_id?: string | null; account_name?: string | null;
  payment_method?: string | null; amount?: string | null; currency?: string | null;
  eligibility: "ELIGIBLE_FOR_REVIEW" | "BLOCKED";
  blocking_reasons: string[]; warnings: string[]; proposal_status: "PREVIEW_ONLY";
};
type Preview = {
  candidates: Candidate[];
  unresolved_items: Array<{source_type:string;source_id:string;source_document_number?:string;reason:string;detail:string}>;
  summary: {candidate_count:number;eligible_for_review:number;blocked:number;unresolved_count:number};
  read_only: true; database_writes: false; movement_creation_enabled: false;
  opening_balances_used: false; active_season: string; has_more: Record<string,boolean>;
};
const labels: Record<string,{ar:string;fr:string}> = {
  GS_SALE_PAYMENT:{ar:"قبض من بيع زيت GS",fr:"Encaissement vente GS"},
  GS_SUPPLIER_PAYMENT:{ar:"دفع لمزوّد",fr:"Paiement fournisseur"},
};
const reasonLabels: Record<string,{ar:string;fr:string}> = {
  TREASURY_ACCOUNT_NOT_ASSIGNED:{ar:"لم يُعيّن حساب خزينة",fr:"Compte de trésorerie non affecté"},
  TREASURY_ACCOUNT_UNKNOWN:{ar:"حساب الخزينة غير موجود",fr:"Compte de trésorerie inconnu"},
  TREASURY_ACCOUNT_INACTIVE:{ar:"حساب الخزينة غير نشط",fr:"Compte de trésorerie inactif"},
  TREASURY_ACCOUNT_CURRENCY_NOT_TND:{ar:"عملة الحساب ليست TND",fr:"Devise du compte différente de TND"},
  TREASURY_ACCOUNT_TYPE_MISMATCH:{ar:"نوع الحساب لا يطابق طريقة الدفع",fr:"Type de compte incompatible avec le paiement"},
  AMOUNT_MISSING_OR_INVALID:{ar:"المبلغ غير صالح",fr:"Montant invalide"},
  PAYMENT_DATE_MISSING_OR_INVALID:{ar:"تاريخ الدفع غير صالح",fr:"Date de paiement invalide"},
  PAYMENT_METHOD_UNSUPPORTED:{ar:"طريقة الدفع غير مدعومة",fr:"Mode de paiement non pris en charge"},
  DUPLICATE_SOURCE_EVENT_IDENTITY:{ar:"تكرار معرّف الحركة المصدر",fr:"Identité de source dupliquée"},
};
const money = (value:string|null|undefined) => {
  if(!value) return "—";
  const [whole,fraction="000"] = value.split(".");
  return `${fmtMoney(whole)}.${fraction.padEnd(3,"0").slice(0,3)}`;
};
export default function TreasuryMovementPreview() {
  const {lang}=useI18n(); const ar=lang==="ar";
  const query=useQuery({queryKey:["accounting-treasury-movement-preview"],queryFn:()=>apiGet<Preview>("/accounting/treasury/movement-preview?limit=200"),staleTime:15000});
  if(query.isPending) return <p className="p-4 text-sm text-stone-500">{ar?"جارٍ إعداد معاينة حركات الخزينة…":"Préparation de l’aperçu des mouvements…"}</p>;
  if(query.isError||!query.data) return <Card className="border-red-200"><CardContent className="flex items-center gap-3 p-4 text-red-800"><AlertTriangle className="size-5"/>{ar?"تعذّر تحميل المعاينة.":"Impossible de charger l’aperçu."}<button onClick={()=>void query.refetch()} className="ms-auto inline-flex items-center gap-2 rounded-lg border px-3 py-2"><RefreshCw className="size-4"/>{ar?"إعادة المحاولة":"Réessayer"}</button></CardContent></Card>;
  const data=query.data;
  return <div className="space-y-4" data-testid="treasury-movement-preview">
    <div className="flex items-start gap-3 rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-950">
      <ShieldCheck className="mt-0.5 size-5 shrink-0"/>
      <div><strong>{ar?"معاينة فقط — لم تُنشأ أي حركة مالية":"Aperçu uniquement — aucun mouvement financier créé"}</strong>
      <p className="mt-1">{ar?"هذه مقترحات مستخرجة من دفعات GS المسجلة. لا تغيّر الأرصدة أو الفواتير أو الديون، ولا يتم اعتمادها تلقائياً. التحويلات البنكية والشيكات لا تعتبر مؤكدة التسوية دون كشف بنكي.":"Propositions issues des paiements GS enregistrés. Aucun solde, facture ou dette n’est modifié. Les virements et chèques ne sont pas considérés comme compensés sans relevé bancaire."}</p></div>
    </div>
    <div className="grid gap-3 sm:grid-cols-3">
      <Card><CardContent className="p-4"><p className="text-sm text-stone-500">{ar?"المقترحات":"Propositions"}</p><p className="text-2xl font-bold">{data.summary.candidate_count}</p></CardContent></Card>
      <Card><CardContent className="p-4"><p className="text-sm text-stone-500">{ar?"صالحة للمراجعة":"À examiner"}</p><p className="text-2xl font-bold text-emerald-700">{data.summary.eligible_for_review}</p></CardContent></Card>
      <Card><CardContent className="p-4"><p className="text-sm text-stone-500">{ar?"موقوفة":"Bloquées"}</p><p className="text-2xl font-bold text-rose-700">{data.summary.blocked+data.summary.unresolved_count}</p></CardContent></Card>
    </div>
    <Card><CardHeader><CardTitle className="text-base">{ar?"مقترحات حركة الصندوق والبنك":"Propositions de mouvements de caisse et banque"}</CardTitle><CardDescription>{ar?"الموسم النشط":"Saison active"}: {data.active_season}</CardDescription></CardHeader>
      <CardContent className="space-y-3">
      {data.candidates.length===0?<p className="rounded-lg bg-stone-50 p-4 text-sm text-stone-500">{ar?"لا توجد دفعات GS ضمن نطاق المعاينة.":"Aucun paiement GS dans le périmètre de l’aperçu."}</p>:
      <div className="overflow-x-auto"><table className="w-full min-w-[850px] text-sm"><thead><tr className="border-b text-left text-xs text-stone-500">
        <th className="px-2 py-2">{ar?"التاريخ":"Date"}</th><th className="px-2 py-2">{ar?"المصدر":"Source"}</th><th className="px-2 py-2">{ar?"المرجع":"Référence"}</th><th className="px-2 py-2">{ar?"الحساب":"Compte"}</th><th className="px-2 py-2">{ar?"الاتجاه":"Sens"}</th><th className="px-2 py-2 text-right">{ar?"المبلغ":"Montant"}</th><th className="px-2 py-2">{ar?"النتيجة":"Résultat"}</th>
      </tr></thead><tbody>{data.candidates.map(row=><tr key={row.candidate_key} className="border-b align-top">
        <td className="px-2 py-3">{row.business_date||"—"}</td>
        <td className="px-2 py-3">{labels[row.source_type]?.[ar?"ar":"fr"]||row.source_type}</td>
        <td className="px-2 py-3">{row.source_document_number||row.source_id}</td>
        <td className="px-2 py-3">{row.account_name||"—"}</td>
        <td className="px-2 py-3"><span className="inline-flex items-center gap-1">{row.direction==="IN"?<ArrowDownLeft className="size-4 text-emerald-700"/>:<ArrowUpRight className="size-4 text-rose-700"/>}{row.direction==="IN"?(ar?"داخل":"Entrée"):(ar?"خارج":"Sortie")}</span></td>
        <td className="px-2 py-3 text-right font-semibold tabular-nums">{money(row.amount)} TND</td>
        <td className="px-2 py-3"><span className={row.eligibility==="ELIGIBLE_FOR_REVIEW"?"font-semibold text-emerald-700":"font-semibold text-rose-700"}>{row.eligibility==="ELIGIBLE_FOR_REVIEW"?(ar?"صالحة للمراجعة":"À examiner"):(ar?"موقوفة":"Bloquée")}</span>
          {row.blocking_reasons.length>0&&<ul className="mt-1 list-disc ps-4 text-xs text-rose-700">{row.blocking_reasons.map(reason=><li key={reason}>{reasonLabels[reason]?.[ar?"ar":"fr"]||reason}</li>)}</ul>}
          {row.warnings.map(w=><p key={w} className="mt-1 text-xs text-amber-700">{w}</p>)}
        </td>
      </tr>)}</tbody></table></div>}
      {data.unresolved_items.map(item=><div key={item.source_type+item.source_id} className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm"><strong>{ar?"مراجعة مطلوبة":"À vérifier"} · {item.source_document_number||item.source_id}</strong><p className="text-amber-900">{ar?"إلغاء قبض لا يثبت رجوع الأموال فعلياً إلى الصندوق أو البنك.":"L’annulation d’un règlement ne prouve pas le retour effectif des fonds en caisse ou en banque."}</p></div>)}
      {Object.values(data.has_more).some(Boolean)&&<p className="text-xs text-amber-700">{ar?"تم بلوغ حد المعاينة؛ توجد سجلات إضافية غير معروضة.":"La limite d’aperçu est atteinte; d’autres documents ne sont pas affichés."}</p>}
      </CardContent>
    </Card>
  </div>;
}
