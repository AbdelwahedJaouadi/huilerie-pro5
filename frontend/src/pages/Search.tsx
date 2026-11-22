import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Search as SearchIcon, Droplet, Printer, ScanLine, UserRound, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiGet, apiPatch, ApiError } from "@/lib/api";
import type { Load, StatusUpdate } from "@/lib/types";
import { fmtDate, fmtNum, useI18n } from "@/lib/i18n";
import { LoadDetail, PageHeader, StatusPill } from "@/components/shared";
import OilEntryDialog from "@/components/OilEntryDialog";
import QrScanDialog from "@/components/QrScanDialog";
import { ReprintDialog } from "@/components/ReceptionTicket";

function StatusControl({ load, onNeedOil }: { load: Load; onNeedOil: () => void }) {
  const { t, errMsg } = useI18n();
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: (b: StatusUpdate) => apiPatch<Load>(`/loads/${load.id}/status`, b),
    onSuccess: () => {
      toast.success(t("status_updated"));
      ["load-by-code", "loads", "loads-search", "stats", "client"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  if (load.status === "cancelled") return null;
  return (
    <div className="space-y-2">
      <Label>{t("status_change")}</Label>
      <Select
        value={load.status}
        disabled={m.isPending}
        onValueChange={(v) => {
          const s = v as StatusUpdate["status"];
          if ((s === "done" || s === "delivered") && load.oil_kg == null) { toast.error(t("err_oil_not_ready")); onNeedOil(); return; }
          m.mutate({ status: s });
        }}
      >
        <SelectTrigger className="h-11 w-64 rounded-xl bg-white" data-testid="search-status-select"><SelectValue>{(v) => t(v as StatusUpdate["status"])}</SelectValue></SelectTrigger>
        <SelectContent>
          <SelectItem value="pending" disabled={load.oil_kg != null}>{t("pending")}</SelectItem>
          <SelectItem value="pressing" disabled={load.oil_kg != null} data-testid="search-status-option-pressing">{t("pressing")}</SelectItem>
          <SelectItem value="done" data-testid="search-status-option-done">{t("done")}</SelectItem>
          <SelectItem value="delivered" data-testid="search-status-option-delivered">{t("delivered")}</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}

export default function SearchPage() {
  const { t, lang } = useI18n();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const code = params.get("code") ?? "";
  const term = params.get("q") ?? "";
  const purchaseId = params.get("purchase_id") ?? "";
  const [input, setInput] = useState(code || term);
  const [selectedCode, setSelectedCode] = useState(code);
  const [last, setLast] = useState(code + "|" + term);
  const [editing, setEditing] = useState<Load | null>(null);
  const [reprint, setReprint] = useState<Load | null>(null);
  const [scanOpen, setScanOpen] = useState(false);
  const qc = useQueryClient();
  const pressingMutation = useMutation({
    mutationFn: (load: Load) => apiPatch<Load>(`/loads/${load.id}/status`, { status: "pressing" }),
    onSuccess: () => {
      toast.success(t("status_updated"));
      ["load-by-code", "loads", "loads-search", "stats", "client"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    },
    onError: () => toast.error(t("status_updated")),
  });
  if (code + "|" + term !== last) {
    setLast(code + "|" + term);
    setInput(code || term);
  }

  const one = useQuery({
    queryKey: ["load-by-code", selectedCode],
    queryFn: () => apiGet<Load>(`/loads/by-code/${encodeURIComponent(selectedCode)}`),
    enabled: !!selectedCode,
    retry: false,
  });
  const purchaseDetail = useQuery({
    queryKey: ["search-olive-purchase", purchaseId],
    queryFn: async () => {
      const records: Record<string, any>[] = [];
      let skip = 0;
      while (true) {
        const page = await apiGet<Record<string, any>[]>(`/commercial/v1/olive-purchases?limit=500&skip=${skip}`);
        records.push(...page);
        if (page.length < 500) break;
        skip += 500;
      }
      return records.find((purchase) => String(purchase.id) === purchaseId) ?? null;
    },
    enabled: !!purchaseId,
    retry: false,
  });
  const list = useQuery({
    queryKey: ["global-search", term],
    queryFn: () => apiGet<{ loads: Load[]; commercial: Array<{ id: string | null; source: string; code: string | null; name: string | null; phone: string | null; status: string | null }> }>(`/commercial/v1/global-search?q=${encodeURIComponent(term)}&limit=50`),
    enabled: !!term,
  });
  const results = list.isError ? [] : (list.data?.loads ?? []);
  const commercialResults = list.isError ? [] : (list.data?.commercial ?? []);
  const isOlivePurchaseResult = (item: (typeof commercialResults)[number]) =>
    /olive.*purchase|purchase.*olive|achat.*olive|olive.*achat/i.test(item.source);
  useEffect(() => {
    if (!selectedCode && term && list.isSuccess && results.length === 1 && commercialResults.length === 0) {
      setSelectedCode(results[0].code);
    }
  }, [selectedCode, term, list.isSuccess, results, commercialResults.length]);
  const singleOlivePurchase = commercialResults.length === 1 && isOlivePurchaseResult(commercialResults[0]) ? commercialResults[0] : null;
  useEffect(() => {
    if (!purchaseId && !selectedCode && term && list.isSuccess && results.length === 0 && singleOlivePurchase?.id) {
      const action = singleOlivePurchase.status?.toUpperCase() === "APPROVED" ? "receipt" : singleOlivePurchase.status?.toUpperCase() === "DRAFT" ? "edit" : "";
      const query = new URLSearchParams({ tab: "purchases", purchase_id: singleOlivePurchase.id });
      if (action) query.set("purchase_action", action);
      navigate(`/commercial?${query.toString()}`);
    }
  }, [purchaseId, selectedCode, term, list.isSuccess, results.length, singleOlivePurchase?.id, singleOlivePurchase?.status, navigate]);
  const purchaseRecord = purchaseDetail.data?.purchase ?? purchaseDetail.data;
  const purchaseNumber = (v: any) => fmtNum(Number(v?.$numberDecimal ?? v ?? 0));
  const notFound = !purchaseId && ((one.isError && one.error instanceof ApiError && one.error.status === 404) || (!!term && !selectedCode && list.isSuccess && results.length === 0 && commercialResults.length === 0));
  const shown = selectedCode ? (one.isError ? undefined : one.data) : (!term && !code && results.length === 1 ? results[0] : undefined);

  return (
    <div>
      <PageHeader title={t("search")} sub={t("search_any_hint")} accent="bg-sky-500" />
      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)]">
      <div className="min-w-0">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const v = input.trim();
          if (!v) return;
          setSelectedCode("");
          setParams({ q: v });
        }}
        className="mb-5 flex w-fit max-w-full flex-wrap items-center gap-1"
      >
        <button
          type="button"
          onClick={() => setScanOpen(true)}
          data-testid="search-qr-scan-button"
          title={t("scan_qr")}
          className="grid size-14 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-sky-500 to-teal-600 text-white shadow-lg shadow-sky-600/30 transition-transform duration-150 hover:scale-105 active:scale-95"
        >
          <ScanLine className="size-8" />
        </button>
        <div className="relative w-[16ch] min-w-0 shrink-0">
          <SearchIcon className="pointer-events-none absolute start-4 top-1/2 size-5 -translate-y-1/2 text-sky-500" />
          <Input
            data-testid="search-code-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t("search_any_hint")}
            maxLength={120}
            className="h-14 w-full rounded-2xl border-sky-200 bg-white ps-12 text-xl"
          />
        </div>
        <Button type="submit" data-testid="search-code-submit" className="h-14 rounded-2xl bg-sky-600 px-5 text-base hover:bg-sky-700">
          {t("go")}
        </Button>
      </form>

      {(one.isLoading || list.isLoading || purchaseDetail.isLoading) && <p className="text-stone-500">{t("loading")}</p>}
      {notFound && (
        <div data-testid="search-not-found" className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-800">
          {t("not_found")}: <span className="font-mono font-bold" dir="ltr">{code || term}</span>
        </div>
      )}

      </div>

      {!!term && !selectedCode && (results.length > 0 || commercialResults.length > 0) && (
        <div className="min-w-0 overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm" data-testid="search-results">
          <div className="border-b border-stone-100 bg-stone-50 px-4 py-2 text-sm font-semibold text-stone-600">{t("results")} ({results.length + commercialResults.length}) — Oroverde + GS</div>
          <ul className="divide-y divide-stone-100">
            {results.map((l) => (
              <li key={l.id}>
                <button
                  type="button"
                  onClick={() => setSelectedCode(l.code)}
                  data-testid={`search-result-${l.code}`}
                  className="flex w-full flex-wrap items-center gap-4 px-4 py-3 text-start transition-colors duration-150 hover:bg-sky-50"
                >
                  <span className="font-mono font-bold text-stone-900" dir="ltr">{l.code}</span>
                  <span className="flex min-w-40 flex-1 items-center gap-2"><UserRound className="size-4 text-teal-600" />{l.client_name} <span className="text-xs text-stone-500" dir="ltr">{l.phone}</span></span>
                  <span className="text-sm text-lime-800">{fmtNum(l.olive_kg)} kg</span>
                  <span className="text-xs text-stone-500" dir="ltr">{fmtDate(l.created_at)}</span>
                  <StatusPill status={l.status} />
                </button>
              </li>
            ))}
          </ul>
          {commercialResults.length > 0 && (
            <div className="border-t border-stone-100">
              <div className="bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800">Gestion commerciale (GS)</div>
              <ul className="divide-y divide-stone-100">
                {commercialResults.map((item, index) => (
                  <li key={item.id ?? `${item.source}-${index}`}>
                    <button type="button" onClick={() => { if (item.id && isOlivePurchaseResult(item)) navigate(`/search?purchase_id=${encodeURIComponent(item.id)}&code=${encodeURIComponent(item.code ?? "")}&supplier_name=${encodeURIComponent(item.name ?? "")}&supplier_phone=${encodeURIComponent(item.phone ?? "")}`); }} disabled={!item.id || !isOlivePurchaseResult(item)} className={`flex w-full flex-wrap items-center gap-3 px-4 py-3 text-start transition-colors ${isOlivePurchaseResult(item) ? "hover:bg-emerald-50" : "cursor-default"}`} data-testid={`search-commercial-result-${item.id ?? index}`}>
                      <span className="rounded-lg bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-800">{item.source}</span>
                      <span className="font-mono font-bold text-stone-900" dir="ltr">{item.code || "—"}</span>
                      <span className="flex min-w-40 flex-1 items-center gap-2 text-stone-700"><UserRound className="size-4 text-teal-600" />{item.name || "—"}</span>
                      {item.phone && <span className="text-xs text-stone-500" dir="ltr">{item.phone}</span>}
                      {item.status && <span className="text-xs text-stone-500">{item.status}</span>}
                      {isOlivePurchaseResult(item) && <span className="text-xs font-semibold text-emerald-700">{lang === "ar" ? "عرض التفاصيل" : "Voir les détails"}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      </div>


      {purchaseId && purchaseRecord && (
        <div className="min-w-0 space-y-4" data-testid="search-olive-purchase-detail">
          <div className="rounded-2xl border border-emerald-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3 border-b border-stone-100 pb-3">
              <div><h2 className="text-xl font-bold text-stone-900">{lang === "ar" ? "تفاصيل شراء الزيتون" : "Détails de l’achat d’olives"}</h2><p className="mt-1 text-sm text-stone-500">{lang === "ar" ? "جميع بيانات عملية الشراء" : "Toutes les informations de l’opération d’achat"}</p></div>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${purchaseRecord.status === "APPROVED" ? "bg-emerald-100 text-emerald-800" : purchaseRecord.status === "CANCELLED" ? "bg-rose-100 text-rose-800" : "bg-amber-100 text-amber-800"}`}>{purchaseRecord.status === "APPROVED" ? (lang === "ar" ? "مؤكد" : "Approuvé") : purchaseRecord.status === "CANCELLED" ? (lang === "ar" ? "ملغى" : "Annulé") : (lang === "ar" ? "مسودة" : "Brouillon")}</span>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div><p className="text-xs text-stone-500">{lang === "ar" ? "كود الشراء" : "Code d’achat"}</p><p className="mt-1 font-mono text-lg font-bold text-emerald-800" dir="ltr">{purchaseRecord.batch_code || purchaseRecord.batch_codes?.join(", ") || purchaseRecord.lines?.map((line: any) => line.batch_code).filter(Boolean).join(", ") || purchaseRecord.document_number || "—"}</p></div>
              <div><p className="text-xs text-stone-500">{lang === "ar" ? "رقم الوثيقة" : "N° du document"}</p><p className="mt-1 font-semibold">{purchaseRecord.document_number || "—"}</p></div>
              <div><p className="text-xs text-stone-500">{lang === "ar" ? "تاريخ الشراء" : "Date d’achat"}</p><p className="mt-1 font-semibold">{purchaseRecord.purchase_date ? fmtDate(purchaseRecord.purchase_date) : "—"}</p></div>
              <div><p className="text-xs text-stone-500">{lang === "ar" ? "المزوّد" : "Fournisseur"}</p><p className="mt-1 font-semibold">{purchaseRecord.supplier_name || purchaseRecord.supplier?.name || params.get("supplier_name") || "—"}</p></div>
              <div><p className="text-xs text-stone-500">{lang === "ar" ? "الهاتف" : "Téléphone"}</p><p className="mt-1 font-semibold" dir="ltr">{purchaseRecord.supplier_phone || purchaseRecord.supplier?.phone || params.get("supplier_phone") || "—"}</p></div>
              <div><p className="text-xs text-stone-500">{lang === "ar" ? "مكان الاستلام" : "Lieu de réception"}</p><p className="mt-1 font-semibold">{purchaseRecord.receiving_location_name || purchaseRecord.receiving_location?.name || "—"}</p></div>
            </div>
            <div className="mt-5 overflow-x-auto rounded-xl border border-stone-200">
              <table className="w-full min-w-[560px] text-sm"><thead className="bg-stone-50 text-stone-600"><tr><th className="px-3 py-2 text-start">{lang === "ar" ? "الصنف" : "Variété"}</th><th className="px-3 py-2 text-end">{lang === "ar" ? "الكمية كغ" : "Quantité (kg)"}</th><th className="px-3 py-2 text-end">{lang === "ar" ? "السعر/كغ" : "Prix/kg"}</th><th className="px-3 py-2 text-end">{lang === "ar" ? "المجموع" : "Total"}</th></tr></thead>
                <tbody>{(purchaseRecord.lines ?? []).map((line: any, index: number) => <tr key={line.id ?? index} className="border-t border-stone-100"><td className="px-3 py-2 font-medium">{line.variety_name || line.variety_fr || line.variety_ar || "—"}</td><td className="px-3 py-2 text-end">{purchaseNumber(line.quantity_kg)}</td><td className="px-3 py-2 text-end">{purchaseNumber(line.unit_price_dt)}</td><td className="px-3 py-2 text-end font-semibold">{purchaseNumber(line.line_total_dt ?? line.total_amount_dt)}</td></tr>)}</tbody>
              </table>
            </div>
            <div className="mt-4 flex flex-wrap justify-end gap-6"><div><p className="text-xs text-stone-500">{lang === "ar" ? "الكمية الإجمالية" : "Quantité totale"}</p><p className="text-lg font-bold text-lime-800">{purchaseNumber(purchaseRecord.total_quantity_kg)} kg</p></div><div><p className="text-xs text-stone-500">{lang === "ar" ? "المبلغ الإجمالي" : "Montant total"}</p><p className="text-lg font-bold text-emerald-800">{purchaseNumber(purchaseRecord.total_amount_dt)} TND</p></div></div>
            {purchaseRecord.notes && <div className="mt-4 border-t border-stone-100 pt-3 text-sm"><span className="text-stone-500">{lang === "ar" ? "ملاحظات" : "Notes"}: </span>{purchaseRecord.notes}</div>}
          </div>
        </div>
      )}
      {purchaseId && purchaseDetail.isError && <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{lang === "ar" ? "تعذر تحميل تفاصيل الشراء. حاول إعادة البحث." : "Impossible de charger les détails de cet achat. Relancez la recherche."}</div>}
      {shown && (
        <div className="space-y-5" data-testid="search-load-detail">
          <LoadDetail load={shown} />
          <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
            <StatusControl load={shown} onNeedOil={() => setEditing(shown)} />
            {shown.status !== "cancelled" && (
              <Button onClick={() => setEditing(shown)} disabled={shown.status === "done" || shown.status === "delivered"} title={shown.status === "done" || shown.status === "delivered" ? t("done") : undefined} data-testid="search-enter-oil-button" className="h-11 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-50">
                <Droplet className="size-4" />
                {shown.oil_kg != null ? t("edit_oil") : t("enter_oil")}
              </Button>
            )}
            <Button onClick={() => pressingMutation.mutate(shown)} disabled={pressingMutation.isPending || shown.status === "pressing" || shown.oil_kg != null || shown.status === "cancelled"} data-testid="search-pressing-button" className="h-11 rounded-xl bg-green-600 text-white hover:bg-green-700 disabled:bg-green-200">
              <Activity className="size-4" /> {t("pressing")}
            </Button>
            <Button onClick={() => setReprint(shown)} variant="outline" data-testid="search-reprint-button" className="h-11 rounded-xl border-amber-300 text-amber-800 hover:bg-amber-50">
              <Printer className="size-4" /> {t("reprint")}
            </Button>
          </div>
        </div>
      )}

      <OilEntryDialog load={editing} onClose={() => setEditing(null)} />
      <ReprintDialog load={reprint} onClose={() => setReprint(null)} />
      <QrScanDialog open={scanOpen} onClose={() => setScanOpen(false)} />
    </div>
  );
}
