import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CalendarDays, Factory, ShoppingBasket, ArrowLeftRight, ShoppingCart, FileSpreadsheet, FileText } from "lucide-react";
import { API_ORIGIN, apiGet } from "@/lib/api";
import { CodeBadge, StatCard } from "@/components/shared";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type Row = Record<string, any>;
type ExportActions = { excel: () => void; pdf: () => void; disabled: boolean };
type Props = { lang: string; onExportActionsChange?: (actions: ExportActions | null) => void };

const list = async (path: string): Promise<Row[]> => {
  const result: Row[] = [];
  for (let skip = 0, page = 0; page < 101; skip += 500, page += 1) {
    const chunk = await apiGet<Row[]>(`${path}${path.includes("?") ? "&" : "?"}limit=500&skip=${skip}`);
    result.push(...chunk);
    if (chunk.length < 500) return result;
  }
  throw new Error("Rapport GS: trop d'enregistrements pour une seule extraction.");
};
const first = (row: Row, keys: string[]) => {
  for (const key of keys) if (row[key] !== undefined && row[key] !== null && row[key] !== "") return row[key];
  return undefined;
};
const num = (row: Row, keys: string[]) => Number(first(row, keys) ?? 0) || 0;
const dateOf = (row: Row) => String(first(row, ["purchase_date", "production_date", "movement_date", "sale_date", "date", "created_at", "approved_at"]) ?? "").slice(0, 10);
const fmt = (v: number, digits = 0) => new Intl.NumberFormat("fr-TN", { maximumFractionDigits: digits }).format(v);
const labelDate = (v: string) => v ? new Date(v + "T12:00:00").toLocaleDateString() : "—";

export default function CommercialReports({ lang, onExportActionsChange }: Props) {
  const ar = lang === "ar";
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [selectedKinds, setSelectedKinds] = useState<string[]>([]);
  const [selectedStatus, setSelectedStatus] = useState("");
  const purchases = useQuery({ queryKey: ["commercial", "report", "purchases"], queryFn: () => list("/commercial/v1/olive-purchases") });
  const production = useQuery({ queryKey: ["commercial", "report", "production"], queryFn: () => list("/commercial/v1/production-runs") });
  const transfers = useQuery({ queryKey: ["commercial", "report", "transfers"], queryFn: () => list("/commercial/v1/internal-movements") });
  const sales = useQuery({ queryKey: ["commercial", "report", "sales"], queryFn: () => list("/commercial/v1/sales") });
  const suppliers = useQuery({ queryKey: ["commercial", "report", "suppliers"], queryFn: () => list("/commercial/v1/suppliers") });
  const buyers = useQuery({ queryKey: ["commercial", "report", "buyers"], queryFn: () => list("/commercial/v1/buyers") });
  const locations = useQuery({ queryKey: ["commercial", "report", "locations"], queryFn: () => list("/commercial/v1/locations") });
  const tanks = useQuery({ queryKey: ["commercial", "report", "tanks"], queryFn: () => list("/commercial/v1/tanks") });
  const oliveLots = useQuery({ queryKey: ["commercial", "report", "olive-lots"], queryFn: () => list("/commercial/v1/lots?product_kind=OLIVE") });

  const filtered = useMemo(() => {
    const within = (row: Row) => {
      const d = dateOf(row);
      return (!start || (d && d >= start)) && (!end || (d && d <= end));
    };
    const supplierById = new Map((suppliers.data ?? []).map(item => [String(item.id), item]));
    const buyerById = new Map((buyers.data ?? []).map(item => [String(item.id), item]));
    const locationById = new Map([...(locations.data ?? []), ...(tanks.data ?? [])].map(item => [String(item.id), item]));
    const purchaseById = new Map((purchases.data ?? []).map(item => [String(item.id), item]));
    const oliveLotById = new Map((oliveLots.data ?? []).map(item => [String(item.id), item]));
    const supplierName = (purchase: Row | undefined) => {
      if (!purchase) return undefined;
      const supplier = supplierById.get(String(purchase.supplier_id ?? ""));
      return first(supplier ?? {}, ["name"]) ?? first(purchase, ["supplier_name", "supplier"]);
    };
    const locationName = (id: unknown, fallback?: unknown) => {
      const location = locationById.get(String(id ?? ""));
      return first(location ?? {}, ["name", "code", "label"]) ?? fallback ?? (id ? String(id) : undefined);
    };
    const productionSupplierNames = (run: Row) => {
      const inputs = Array.isArray(run.inputs) ? run.inputs : [];
      const lotIds = [...new Set([
        ...inputs.map((line: Row) => line.olive_lot_id ?? line.lot_id),
        run.source_olive_lot_id,
        ...(Array.isArray(run.source_olive_lot_ids) ? run.source_olive_lot_ids : []),
      ].filter(Boolean).map(String))];
      const names = lotIds.map(id => {
        const lot = oliveLotById.get(id);
        const purchase = lot ? purchaseById.get(String(lot.source_purchase_id ?? "")) : undefined;
        return supplierName(purchase);
      }).filter(Boolean);
      return [...new Set(names)].join(", ");
    };
    const groups = [
      ...(purchases.data ?? []).filter(within).map(row => ({ row, kind: "Achat", kindAr: "شراء", date: dateOf(row), code: first(row, ["document_number", "purchase_number", "batch_code"]), party: supplierName(row) ?? "—", qty: num(row, ["total_quantity_kg", "quantity_kg", "total_olive_kg"]), unit: "kg", amount: num(row, ["total_amount_dt", "total_amount", "amount_dt"]), status: first(row, ["status", "approval_status"]) })),
      ...(production.data ?? []).filter(within).map(row => {
        const tank = locationName(row.output_tank_id, first(row, ["output_tank_name", "output_tank_code", "tank_code"]));
        const supplier = productionSupplierNames(row);
        return { row, kind: "Production", kindAr: "إنتاج", date: dateOf(row), code: first(row, ["document_number", "production_number"]), party: [supplier, tank].filter(Boolean).join(" · ") || "—", qty: num(row, ["output_quantity_liters", "output_liters", "oil_quantity_liters", "actual_oil_output_kg"]), unit: "L", amount: 0, status: first(row, ["status"]) };
      }),
      ...(transfers.data ?? []).filter(within).map(row => {
        const ownershipChange = row.movement_kind === "OWNERSHIP_TRANSFER";
        const from = locationName(row.source_location_id, first(row, ["source_location_name", "source_location"]));
        const to = locationName(row.destination_location_id, first(row, ["destination_location_name", "destination_location"]));
        return {
          row,
          kind: ownershipChange ? "Changement de propriété" : "Transfert",
          kindAr: ownershipChange ? "تغيير الملكية" : "تحويل",
          date: dateOf(row),
          code: first(row, ["document_number", "movement_number"]),
          party: ownershipChange ? (from || to || "—") : ([from, to].filter(Boolean).join(" → ") || "—"),
          qty: num(row, ["quantity", "quantity_kg", "quantity_liters"]),
          unit: first(row, ["product_kind"]) === "OIL" ? "L" : "kg",
          amount: 0,
          status: first(row, ["status", "movement_kind"]),
        };
      }),
      ...(sales.data ?? []).filter(within).map(row => {
        const buyer = buyerById.get(String(row.buyer_id ?? ""));
        const buyerName = first(buyer ?? {}, ["name"]) ?? first(row, ["buyer_name", "customer_name"]);
        const tank = locationName(row.source_tank_id, first(row, ["source_tank_name", "tank_code"]));
        return { row, kind: "Vente", kindAr: "بيع", date: dateOf(row), code: first(row, ["document_number", "sale_number", "id"]), party: [buyerName, tank].filter(Boolean).join(" · ") || "—", qty: num(row, ["quantity_liters", "total_quantity_liters", "shipped_quantity_liters", "quantity_kg"]), unit: "L", amount: num(row, ["total_amount_dt", "total_amount", "amount_dt"]), status: first(row, ["status"]) };
      }),
    ];
    return groups.sort((a, b) => b.date.localeCompare(a.date));
  }, [purchases.data, production.data, transfers.data, sales.data, suppliers.data, buyers.data, locations.data, tanks.data, oliveLots.data, start, end]);

  const operationKinds = ["Achat", "Production", "Transfert", "Changement de propriété", "Vente"];
  const availableStatuses = [...new Set(filtered.map(x => String(x.status ?? "").trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b));
  const displayedRows = filtered.filter(x => (!selectedKinds.length || selectedKinds.includes(x.kind)) && (!selectedStatus || String(x.status ?? "") === selectedStatus));
  const toggleKind = (kind: string) => setSelectedKinds(current => current.length === 0 ? [kind] : current.includes(kind) ? current.filter(value => value !== kind) : [...current, kind]);
  const totalPurchaseKg = filtered.filter(x => x.kind === "Achat").reduce((s, x) => s + x.qty, 0);
  const totalProductionL = filtered.filter(x => x.kind === "Production").reduce((s, x) => s + x.qty, 0);
  const totalSalesL = filtered.filter(x => x.kind === "Vente").reduce((s, x) => s + x.qty, 0);
  const totalSalesAmount = filtered.filter(x => x.kind === "Vente").reduce((s, x) => s + x.amount, 0);
  const chart = useMemo(() => {
    const buckets = new Map<string, { period: string; achats: number; production: number; ventes: number }>();
    filtered.forEach(x => {
      const period = x.date ? x.date.slice(0, 7) : "Sans date";
      const b = buckets.get(period) ?? { period, achats: 0, production: 0, ventes: 0 };
      if (x.kind === "Achat") b.achats += x.qty;
      if (x.kind === "Production") b.production += x.qty;
      if (x.kind === "Vente") b.ventes += x.qty;
      buckets.set(period, b);
    });
    return [...buckets.values()].sort((a, b) => a.period.localeCompare(b.period));
  }, [filtered]);
  const loading = purchases.isLoading || production.isLoading || transfers.isLoading || sales.isLoading || suppliers.isLoading || buyers.isLoading || locations.isLoading || tanks.isLoading || oliveLots.isLoading;
  const error = purchases.error || production.error || transfers.error || sales.error || suppliers.error || buyers.error || locations.error || tanks.error || oliveLots.error;

  const exportRows = () => displayedRows.map(x => [x.date || "", x.kind, x.code ?? "", x.party ?? "", x.qty, x.unit, x.amount, x.status ?? ""]);
  const exportHeaders = ar
    ? ["التاريخ", "العملية", "المرجع", "المزوّد / الحريف / الموقع", "الكمية", "الوحدة", "المبلغ TND", "الحالة"]
    : ["Date", "Opération", "Document / Code", "Fournisseur / Client / Emplacement", "Quantité", "Unité", "Montant TND", "Statut"];
  const exportBaseName = `rapport-gestion-commerciale-${start || "debut"}-${end || "fin"}`;

  const exportExcel = () => {
    const csvCell = (value: unknown) => `"${String(value ?? "").replace(/"/g, '""')}"`;
    const csv = [exportHeaders, ...exportRows()].map(row => row.map(csvCell).join(";")).join("\\r\\n");
    const blob = new Blob(["\\uFEFF", csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${exportBaseName}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const exportPdf = async () => {
    try {
      const response = await fetch(`${API_ORIGIN}/api/commercial/v1/reports/export.pdf`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: ar ? "تقرير التسيير التجاري" : "Rapport de gestion commerciale",
          period: `${ar ? "الفترة" : "Période"} : ${start || (ar ? "البداية" : "Début")} — ${end || (ar ? "النهاية" : "Fin")} · ${ar ? "العمليات" : "Opérations"} : ${displayedRows.length}`,
          headers: exportHeaders,
          rows: displayedRows.map(x => [
            x.date || "",
            ar ? x.kindAr : x.kind,
            x.code ?? "",
            x.party ?? "",
            fmt(x.qty, 3),
            x.unit,
            x.amount ? fmt(x.amount, 3) : "—",
            x.status ?? "",
          ]),
          summary: [
            [ar ? "الزيتون المشتَرى" : "Olives achetées", `${fmt(totalPurchaseKg, 3)} kg`],
            [ar ? "الإنتاج" : "Production d'huile", `${fmt(totalProductionL, 3)} L`],
            [ar ? "المبيعات" : "Volume vendu", `${fmt(totalSalesL, 3)} L`],
            [ar ? "قيمة المبيعات" : "Valeur des ventes", `${fmt(totalSalesAmount, 3)} TND`],
          ],
          chart: chart.map(item => ({
            period: item.period,
            achats: Number(item.achats) || 0,
            production: Number(item.production) || 0,
            ventes: Number(item.ventes) || 0,
          })),
          breakdown: operationKinds.map(kind => {
            const items = displayedRows.filter(item => item.kind === kind);
            const quantity = items.reduce((total, item) => total + Number(item.qty || 0), 0);
            const amount = items.reduce((total, item) => total + Number(item.amount || 0), 0);
            return {
              kind: ar ? ({ Achat: "شراء", Production: "إنتاج", Transfert: "تحويل", "Changement de propriété": "تغيير الملكية", Vente: "بيع" } as Record<string, string>)[kind] : kind,
              count: items.length,
              quantity: `${fmt(quantity, 3)} ${items[0]?.unit || (kind === "Achat" ? "kg" : "L")}`,
              amount: `${fmt(amount, 3)} TND`,
            };
          }),
        }),
      });
      if (!response.ok) {
        const detail = await response.text().catch(() => "");
        throw new Error(detail || `Erreur serveur (${response.status})`);
      }
      const blob = await response.blob();
      if (!blob.size) throw new Error("Le fichier PDF reçu est vide.");
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${exportBaseName}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1500);
    } catch (error) {
      alert(ar
        ? `تعذر تنزيل ملف PDF: ${error instanceof Error ? error.message : "خطأ غير معروف"}`
        : `Impossible de télécharger le PDF : ${error instanceof Error ? error.message : "erreur inconnue"}`);
    }
  };

  const exportActionsRef = useRef<ExportActions>({
    excel: () => undefined,
    pdf: () => undefined,
    disabled: true,
  });
  exportActionsRef.current = {
    excel: exportExcel,
    pdf: () => { void exportPdf(); },
    disabled: loading || !displayedRows.length,
  };
  useEffect(() => {
    onExportActionsChange?.({
      excel: () => exportActionsRef.current.excel(),
      pdf: () => exportActionsRef.current.pdf(),
      disabled: exportActionsRef.current.disabled,
    });
    return () => onExportActionsChange?.(null);
  }, [onExportActionsChange, loading, displayedRows.length]);

  return <div className="space-y-5" dir={ar ? "rtl" : "ltr"}>
    <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-violet-200 bg-violet-50/70 p-4">
      <div className="flex min-w-fit items-center gap-2 font-semibold text-violet-950"><CalendarDays className="size-5" /> {ar ? "الفترة" : "Période du rapport"}</div>
      <label className="grid gap-1 text-xs font-medium text-stone-600">{ar ? "من" : "Du"}<input type="date" value={start} onChange={e => setStart(e.target.value)} className="h-9 rounded-lg border bg-white px-2 text-sm" /></label>
      <label className="grid gap-1 text-xs font-medium text-stone-600">{ar ? "إلى" : "Au"}<input type="date" value={end} onChange={e => setEnd(e.target.value)} className="h-9 rounded-lg border bg-white px-2 text-sm" /></label>
      <button className="h-9 rounded-lg border border-stone-300 bg-white px-3 text-sm hover:bg-stone-100" onClick={() => { setStart(""); setEnd(""); }}>{ar ? "كل الفترات" : "Toute la période"}</button>
      <div className="mx-1 hidden h-10 border-l border-violet-200 xl:block" />
      <div className="min-w-[220px] flex-1">
        <div className="mb-2 text-xs font-semibold text-violet-950">{ar ? "أنواع العمليات المعروضة" : "Opérations à afficher"}</div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => setSelectedKinds([])} className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors ${selectedKinds.length === 0 ? "border-slate-800 bg-slate-800 text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"}`}>{ar ? "الكل" : "Toutes"}</button>
          {operationKinds.map(kind => {
            const active = selectedKinds.length === 0 || selectedKinds.includes(kind);
            const tones: Record<string, string> = { Achat: active ? "border-amber-500 bg-amber-100 text-amber-900" : "border-slate-200 bg-white text-slate-400", Production: active ? "border-emerald-500 bg-emerald-100 text-emerald-900" : "border-slate-200 bg-white text-slate-400", Transfert: active ? "border-violet-500 bg-violet-100 text-violet-900" : "border-slate-200 bg-white text-slate-400", "Changement de propriété": active ? "border-orange-500 bg-orange-100 text-orange-900" : "border-slate-200 bg-white text-slate-400", Vente: active ? "border-sky-500 bg-sky-100 text-sky-900" : "border-slate-200 bg-white text-slate-400" };
            const OperationIcon = ({ Achat: ShoppingBasket, Production: Factory, Transfert: ArrowLeftRight, "Changement de propriété": ArrowLeftRight, Vente: ShoppingCart } as Record<string, typeof ShoppingBasket>)[kind];
            return <button key={kind} type="button" aria-pressed={active} onClick={() => toggleKind(kind)} className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors hover:brightness-95 ${tones[kind]}`}><OperationIcon className="size-3.5" />{ar ? ({ Achat: "شراء", Production: "إنتاج", Transfert: "تحويل", "Changement de propriété": "تغيير الملكية", Vente: "بيع" } as Record<string, string>)[kind] : kind}</button>;
          })}
        </div>
      </div>

    </div>
    {error && <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{ar ? "تعذر تحميل جزء من بيانات التقرير. تحقق من الاتصال ثم حدّث الصفحة." : "Impossible de charger une partie des données du rapport. Vérifiez la connexion puis actualisez."}</div>}
    <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <label className="grid min-w-[190px] gap-1 text-xs font-semibold text-slate-600">{ar ? "الحالة" : "Statut"}
        <select value={selectedStatus} onChange={e => setSelectedStatus(e.target.value)} className="h-9 rounded-lg border border-slate-300 bg-white px-3 text-sm font-normal text-slate-800">
          <option value="">{ar ? "كل الحالات" : "Tous les statuts"}</option>
          {availableStatuses.map(status => <option key={status} value={status}>{status}</option>)}
        </select>
      </label>
      <button type="button" onClick={() => { setSelectedKinds([]); setSelectedStatus(""); }} className="h-9 rounded-lg border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-100">{ar ? "إعادة ضبط" : "Réinitialiser"}</button>
      <div className="text-xs text-slate-500">{ar ? "النتائج" : "Lignes affichées"}: <span className="font-bold tabular-nums text-slate-800">{displayedRows.length}</span> / {filtered.length}</div>
    </div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard tone="gold" label={ar ? "الزيتون المشتَرى" : "Olives achetées"} value={fmt(totalPurchaseKg, 3)} unit="kg" icon={<ShoppingBasket />} />
      <StatCard tone="emerald" label={ar ? "الإنتاج" : "Production d'huile"} value={fmt(totalProductionL, 3)} unit="L" icon={<Factory />} />
      <StatCard tone="sky" label={ar ? "المبيعات" : "Volume vendu"} value={fmt(totalSalesL, 3)} unit="L" icon={<ShoppingCart />} />
      <StatCard tone="rose" label={ar ? "قيمة المبيعات" : "Valeur des ventes"} value={fmt(totalSalesAmount, 3)} unit="TND" icon={<ShoppingCart />} />
    </div>
    <Card>
      <CardHeader><CardTitle>{ar ? "تطور النشاط حسب الشهر" : "Évolution mensuelle des opérations"}</CardTitle></CardHeader>
      <CardContent>
        {chart.length ? <div className="h-[320px] w-full" dir="ltr"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart} margin={{ top: 8, right: 18, left: 8, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="period" /><YAxis /><Tooltip formatter={(v: number) => fmt(Number(v), 3)} /><Legend /><Bar dataKey="achats" name="Achats (kg)" fill="#D6A33A" radius={[5,5,0,0]} /><Bar dataKey="production" name="Production (L)" fill="#15966B" radius={[5,5,0,0]} /><Bar dataKey="ventes" name="Ventes (L)" fill="#3987C9" radius={[5,5,0,0]} /></BarChart></ResponsiveContainer></div> : <p className="py-12 text-center text-sm text-stone-500">{loading ? (ar ? "جار تحميل البيانات…" : "Chargement des données…") : (ar ? "لا توجد بيانات في هذه الفترة" : "Aucune donnée sur cette période")}</p>}
      </CardContent>
    </Card>
    <Card>
      <CardHeader><CardTitle>{ar ? "سجل جميع عمليات GS" : "Journal des opérations GS"}</CardTitle></CardHeader>
      <CardContent className="p-0 sm:p-6">
        <div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>{ar ? "التاريخ" : "Date"}</TableHead><TableHead>{ar ? "العملية" : "Opération"}</TableHead><TableHead>{ar ? "المرجع" : "Document / Code"}</TableHead><TableHead>{ar ? "المزوّد / الحريف / الموقع" : "Fournisseur / Client / Emplacement"}</TableHead><TableHead className="text-end">{ar ? "الكمية" : "Quantité"}</TableHead><TableHead>{ar ? "الحالة" : "Statut"}</TableHead></TableRow></TableHeader><TableBody>
          {displayedRows.map((x, i) => { const rowTone = x.kind === "Achat" ? "bg-amber-50/80 hover:bg-amber-100/80 border-l-4 border-l-amber-500" : x.kind === "Production" ? "bg-emerald-50/80 hover:bg-emerald-100/80 border-l-4 border-l-emerald-500" : x.kind === "Transfert" ? "bg-violet-50/80 hover:bg-violet-100/80 border-l-4 border-l-violet-500" : x.kind === "Changement de propriété" ? "bg-orange-50/80 hover:bg-orange-100/80 border-l-4 border-l-orange-500" : "bg-sky-50/80 hover:bg-sky-100/80 border-l-4 border-l-sky-500"; const operationTone = x.kind === "Achat" ? "text-amber-900" : x.kind === "Production" ? "text-emerald-900" : x.kind === "Transfert" ? "text-violet-900" : x.kind === "Changement de propriété" ? "text-orange-900" : "text-sky-900"; return <TableRow key={String(x.code ?? i) + x.kind} className={rowTone}><TableCell className="whitespace-nowrap">{labelDate(x.date)}</TableCell><TableCell className={`font-bold ${operationTone}`}>{ar ? x.kindAr : x.kind}</TableCell><TableCell className="font-mono text-xs">{x.code ? <CodeBadge code={String(x.code)} /> : "—"}</TableCell><TableCell>{String(x.party ?? "—")}</TableCell><TableCell className="text-end tabular-nums">{fmt(x.qty, 3)} {x.unit}</TableCell><TableCell>{String(x.status ?? "—")}</TableCell></TableRow>; })}
          {!displayedRows.length && <TableRow><TableCell colSpan={6} className="py-10 text-center text-stone-500">{loading ? (ar ? "جار تحميل البيانات…" : "Chargement…") : (ar ? "لا توجد عمليات مسجلة" : "Aucune opération enregistrée")}</TableCell></TableRow>}
        </TableBody></Table></div>
      </CardContent>
    </Card>
    <p className="text-xs text-stone-500">{ar ? "تعرض هذه الصفحة عمليات GS المسجلة فقط. لا تشمل عمليات العصر العادية." : "Ce rapport couvre uniquement les opérations enregistrées dans GS. Les opérations de trituration classiques en sont exclues."}</p>
  </div>;
}
