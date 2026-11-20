import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, Landmark, Plus, RefreshCw, ShieldAlert, Power } from "lucide-react";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type Account = {
  id: string; name: string; account_type: "CASH" | "BANK"; currency: "TND";
  bank_name?: string | null; account_suffix?: string | null; location?: string | null;
  custodian_user_id?: string | null; notes?: string; active: boolean; version: number;
  opening_balance_status: "NOT_CONFIGURED";
};
type ResponseData = { accounts: Account[]; currency: "TND"; opening_balances_configured: false; ledger_enabled: false; read_only_balances: true };
type Draft = { name: string; account_type: "CASH" | "BANK"; bank_name: string; account_suffix: string; location: string; custodian_user_id: string; notes: string };

export default function TreasuryAccounts() {
  const { lang } = useI18n(); const ar = lang === "ar"; const qc = useQueryClient();
  const empty: Draft = {name:"",account_type:"CASH",bank_name:"",account_suffix:"",location:"",custodian_user_id:"",notes:""};
  const [draft,setDraft] = useState<Draft>(empty);
  const query = useQuery({queryKey:["accounting-treasury-accounts"],queryFn:()=>apiGet<ResponseData>("/accounting/treasury/accounts"),staleTime:15000});
  const create = useMutation({mutationFn:(body:Draft)=>apiPost<Account>("/accounting/treasury/accounts",{...body,bank_name:body.bank_name||null,account_suffix:body.account_suffix||null,location:body.location||null,custodian_user_id:body.custodian_user_id||null}),onSuccess:()=>{void qc.invalidateQueries({queryKey:["accounting-treasury-accounts"]});setDraft(empty);}});
  const toggle = useMutation({mutationFn:(row:Account)=>apiPatch<Account>("/accounting/treasury/accounts/"+encodeURIComponent(row.id)+"/status",{expected_version:row.version,active:!row.active}),onSuccess:()=>void qc.invalidateQueries({queryKey:["accounting-treasury-accounts"]})});
  const accounts = query.data?.accounts || [];
  return <div className="space-y-5" data-testid="treasury-account-directory">
    <div><h2 className="text-lg font-bold text-stone-900">{ar?"حسابات الخزينة والبنوك":"Comptes de trésorerie et banques"}</h2><p className="mt-1 text-sm text-stone-500">{ar?"دليل الصناديق والحسابات البنكية للشركة":"Répertoire des caisses et comptes bancaires de l’entreprise"}</p></div>
    <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"><ShieldAlert className="mt-0.5 size-5 shrink-0"/><div><strong>{ar?"تعريف الحسابات فقط — لا توجد أرصدة أو حركات":"Répertoire uniquement — aucun solde ni mouvement"}</strong><p className="mt-1">{ar?"لا نسجل أرصدة افتتاحية أو حالية ولا ننشئ حركات مالية تلقائياً. بعض دفعات GS مرتبطة بالحسابات وتظهر في المعاينة أدناه. لا تدخل رقم الحساب البنكي كاملاً؛ يكفي اسم البنك وآخر أربعة أرقام اختيارياً.":"Aucun solde d’ouverture ou courant et aucun mouvement financier automatique. Certains paiements GS sont déjà affectés à ces comptes et apparaissent dans l’aperçu ci-dessous. Ne saisissez jamais le numéro bancaire complet; le nom de la banque et les quatre derniers chiffres sont facultatifs."}</p></div></div>
    <Card><CardHeader><CardTitle className="text-base">{ar?"إضافة حساب":"Ajouter un compte"}</CardTitle><CardDescription>{ar?"إنشاء سجل إداري دون أثر مالي":"Créer une fiche administrative sans effet financier"}</CardDescription></CardHeader><CardContent className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-sm"><span>{ar?"نوع الحساب":"Type de compte"}</span><select className="rounded-lg border bg-white px-3 py-2" value={draft.account_type} onChange={e=>setDraft(v=>({...v,account_type:e.target.value as Draft["account_type"],bank_name:"",account_suffix:""}))}><option value="CASH">{ar?"صندوق نقدي":"Caisse"}</option><option value="BANK">{ar?"حساب بنكي":"Banque"}</option></select></label>
        <label className="grid gap-1 text-sm"><span>{ar?"اسم الحساب":"Nom du compte"}</span><input required minLength={2} maxLength={80} className="rounded-lg border bg-white px-3 py-2" value={draft.name} onChange={e=>setDraft(v=>({...v,name:e.target.value}))} placeholder={ar?"مثال: الصندوق الرئيسي":"Ex. Caisse principale"}/></label>
        {draft.account_type==="BANK" ? <>
          <label className="grid gap-1 text-sm"><span>{ar?"اسم البنك":"Nom de la banque"}</span><input required maxLength={100} className="rounded-lg border bg-white px-3 py-2" value={draft.bank_name} onChange={e=>setDraft(v=>({...v,bank_name:e.target.value}))}/></label>
          <label className="grid gap-1 text-sm"><span>{ar?"آخر أربعة أرقام (اختياري)":"4 derniers chiffres (facultatif)"}</span><input inputMode="numeric" maxLength={4} pattern="[0-9]{4}" className="rounded-lg border bg-white px-3 py-2" value={draft.account_suffix} onChange={e=>setDraft(v=>({...v,account_suffix:e.target.value.split("").filter(char=>char.charCodeAt(0)>=48&&char.charCodeAt(0)<=57).join("").slice(0,4)}))}/></label>
        </> : <>
          <label className="grid gap-1 text-sm"><span>{ar?"الموقع":"Emplacement"}</span><input maxLength={120} className="rounded-lg border bg-white px-3 py-2" value={draft.location} onChange={e=>setDraft(v=>({...v,location:e.target.value}))}/></label>
          <label className="grid gap-1 text-sm"><span>{ar?"المسؤول (معرّف المستخدم)":"Responsable (ID utilisateur)"}</span><input maxLength={80} className="rounded-lg border bg-white px-3 py-2" value={draft.custodian_user_id} onChange={e=>setDraft(v=>({...v,custodian_user_id:e.target.value}))}/></label>
        </>}
        <label className="grid gap-1 text-sm sm:col-span-2"><span>{ar?"ملاحظات":"Notes"}</span><textarea rows={2} maxLength={500} className="rounded-lg border bg-white px-3 py-2" value={draft.notes} onChange={e=>setDraft(v=>({...v,notes:e.target.value}))}/></label>
      </div>
      <button type="button" disabled={create.isPending||draft.name.trim().length<2||(draft.account_type==="BANK"&&!draft.bank_name.trim())||(draft.account_suffix.length>0&&draft.account_suffix.length!==4)} onClick={()=>create.mutate(draft)} className="inline-flex items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"><Plus className="size-4"/>{ar?"إضافة الحساب":"Ajouter le compte"}</button>
      {create.isError&&<p className="text-sm text-red-700">{create.error.message}</p>}
    </CardContent></Card>
    <Card><CardHeader><div className="flex items-center justify-between gap-2"><div><CardTitle className="text-base">{ar?"الحسابات المسجلة":"Comptes enregistrés"}</CardTitle><CardDescription>{ar?"العملة في هذه المرحلة: TND":"Devise de cette étape : TND"}</CardDescription></div><button type="button" onClick={()=>void query.refetch()} className="rounded-lg border p-2" title={ar?"تحديث":"Actualiser"}><RefreshCw className="size-4"/></button></div></CardHeader><CardContent>
      {query.isPending?<p className="text-sm text-stone-500">{ar?"جارٍ التحميل…":"Chargement…"}</p>:query.isError?<p className="text-sm text-red-700">{ar?"تعذّر تحميل الحسابات.":"Impossible de charger les comptes."}</p>:accounts.length===0?<p className="rounded-lg bg-stone-50 p-4 text-sm text-stone-500">{ar?"لم تُسجل حسابات بعد.":"Aucun compte enregistré."}</p>:
      <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-sm"><thead><tr className="border-b text-left text-xs text-stone-500"><th className="px-3 py-2">{ar?"الحساب":"Compte"}</th><th className="px-3 py-2">{ar?"النوع":"Type"}</th><th className="px-3 py-2">{ar?"المعلومات":"Informations"}</th><th className="px-3 py-2">{ar?"الرصيد الافتتاحي":"Solde initial"}</th><th className="px-3 py-2">{ar?"الحالة":"Statut"}</th><th className="px-3 py-2">{ar?"إجراء":"Action"}</th></tr></thead><tbody>{accounts.map(row=><tr key={row.id} className="border-b last:border-0"><td className="px-3 py-3 font-semibold">{row.name}</td><td className="px-3 py-3"><span className="inline-flex items-center gap-1">{row.account_type==="BANK"?<Landmark className="size-4"/>:<Banknote className="size-4"/>}{row.account_type==="BANK"?(ar?"بنك":"Banque"):(ar?"صندوق":"Caisse")}</span></td><td className="px-3 py-3">{row.account_type==="BANK"?(String(row.bank_name||"—")+(row.account_suffix?" · •••• "+row.account_suffix:"")):([row.location,row.custodian_user_id].filter(Boolean).join(" · ")||"—")}</td><td className="px-3 py-3 text-stone-500">{ar?"غير محدد":"Non configuré"}</td><td className="px-3 py-3">{row.active?(ar?"نشط":"Actif"):(ar?"معطل":"Inactif")}</td><td className="px-3 py-3"><button type="button" disabled={toggle.isPending} onClick={()=>toggle.mutate(row)} className="inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs"><Power className="size-3"/>{row.active?(ar?"تعطيل":"Désactiver"):(ar?"تفعيل":"Réactiver")}</button></td></tr>)}</tbody></table></div>}
      {toggle.isError&&<p className="mt-3 text-sm text-red-700">{toggle.error.message}</p>}
    </CardContent></Card>
  </div>;
}
