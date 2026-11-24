import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Banknote, Save, ShieldAlert } from "lucide-react";
import { apiGet, apiPatch } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type TreasuryAccount = {
  id: string; name: string; account_type: "CASH" | "BANK"; active: boolean; version: number;
  opening_balance_status: "NOT_CONFIGURED" | "CONFIGURED";
  opening_balance_amount_tnd?: string | null; opening_balance_date?: string | null;
  current_balance_tnd?: string | null;
};
type AccountsResponse = { accounts: TreasuryAccount[] };

export default function CommercialOpeningBalanceSettings() {
  const { lang } = useI18n();
  const ar = lang === "ar";
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["accounting-treasury-accounts"],
    queryFn: () => apiGet<AccountsResponse>("/accounting/treasury/accounts"),
  });
  const accounts = query.data?.accounts ?? [];
  const [accountId, setAccountId] = useState("");
  const account = accounts.find((a) => a.id === accountId) ?? accounts[0];
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");
  useEffect(() => {
    if (!account) { setAccountId(""); setAmount(""); setDate(""); return; }
    setAccountId(account.id);
    setAmount(account.opening_balance_amount_tnd ?? "");
    setDate(account.opening_balance_date ?? "");
  }, [account?.id, account?.opening_balance_amount_tnd, account?.opening_balance_date]);

  const save = useMutation({
    mutationFn: () => apiPatch<TreasuryAccount>(
      "/accounting/treasury/accounts/" + encodeURIComponent(account!.id) + "/opening-balance",
      { expected_version: account!.version, opening_balance_amount_tnd: amount.trim(), opening_balance_date: date },
    ),
    onSuccess: async () => {
      toast.success(ar ? "تم حفظ الرصيد الافتتاحي" : "Solde initial enregistré");
      await qc.invalidateQueries({ queryKey: ["accounting-treasury-accounts"] });
    },
    onError: (error) => toast.error(error.message),
  });
  const validAmount = /^\d+(?:[.,]\d{1,3})?$/.test(amount.trim()) && Number(amount.replace(",", ".")) >= 0;
  return <section className="rounded-2xl border border-amber-200 bg-amber-50/60 p-5" data-testid="commercial-opening-balance-settings">
    <div className="mb-4 flex items-start gap-3">
      <span className="grid size-10 place-items-center rounded-xl bg-amber-600 text-white"><Banknote className="size-5"/></span>
      <div><h2 className="text-lg font-bold text-amber-950">{ar ? "الرصيد الافتتاحي للصندوق والبنك" : "Solde initial de caisse et banque"}</h2>
        <p className="text-sm text-amber-900">{ar ? "حدد الرصيد الفعلي للصندوق أو الحساب البنكي وتاريخ بداية المحاسبة." : "Définissez le solde réel de la caisse ou du compte bancaire à la date de début comptable."}</p>
      </div>
    </div>
    <div className="mb-4 flex gap-3 rounded-xl border border-amber-200 bg-white p-3 text-sm text-amber-950"><ShieldAlert className="size-5 shrink-0"/><p>{ar ? "هذا رصيد افتتاحي وليس إيراداً أو حركة قبض. تُحتسب حركات الحساب المسجلة ابتداءً من التاريخ المحدد فقط، ويُحفظ كل تغيير في سجل التدقيق." : "Ce solde n’est ni un revenu ni un encaissement. Seuls les mouvements du compte datés à partir de la date choisie sont ajoutés; chaque modification est journalisée."}</p></div>
    {query.isPending ? <p className="text-sm text-stone-600">{ar ? "جارٍ تحميل الحسابات…" : "Chargement des comptes…"}</p> :
      query.isError ? <p className="text-sm text-red-700">{ar ? "تعذر تحميل الحسابات." : "Impossible de charger les comptes."}</p> :
      accounts.length === 0 ? <p className="rounded-lg bg-white p-3 text-sm text-stone-600">{ar ? "أنشئ حساب صندوق نقدي أولاً في قسم الخزينة." : "Créez d’abord un compte de caisse ou bancaire dans la trésorerie."}</p> :
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); if (account && validAmount && date) save.mutate(); }}>
        <label className="grid gap-1 text-sm font-medium sm:col-span-2"><span>{ar ? "الحساب" : "Compte de caisse ou bancaire"}</span>
          <select className="rounded-lg border bg-white px-3 py-2" value={account?.id ?? ""} onChange={(e) => setAccountId(e.target.value)}>
            {accounts.map((a) => <option key={a.id} value={a.id}>{a.name} — {a.account_type === "BANK" ? (ar ? "بنك" : "Banque") : (ar ? "صندوق" : "Caisse")}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm font-medium"><span>{ar ? "المبلغ الافتتاحي (TND)" : "Montant initial (TND)"}</span>
          <input required type="number" min="0" step="0.001" inputMode="decimal" className="rounded-lg border bg-white px-3 py-2" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <label className="grid gap-1 text-sm font-medium"><span>{ar ? "تاريخ بداية المحاسبة" : "Date de début comptable"}</span>
          <input required type="date" className="rounded-lg border bg-white px-3 py-2" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <div className="sm:col-span-2">
          <button type="submit" disabled={!account || !validAmount || !date || save.isPending} className="inline-flex items-center gap-2 rounded-lg bg-amber-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"><Save className="size-4"/>{ar ? "حفظ الرصيد الافتتاحي" : "Enregistrer le solde initial"}</button>
        </div>
        {account?.opening_balance_status === "CONFIGURED" && <p className="text-sm text-stone-700 sm:col-span-2">{ar ? "الرصيد الحالي المحسوب: " : "Solde courant calculé : "}<strong>{Number(account.current_balance_tnd ?? 0).toLocaleString(ar ? "ar-TN" : "fr-FR",{minimumFractionDigits:3,maximumFractionDigits:3})} TND</strong></p>}
      </form>}
    {save.isError && <p className="mt-3 text-sm text-red-700">{save.error.message}</p>}
  </section>;
}
