import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, Boxes, CalendarClock, ClipboardList, Factory, RefreshCw, ShoppingBasket, ShoppingCart, Wallet, type LucideIcon } from "lucide-react";
import { apiGet } from "@/lib/api";
import { fmtMoney, fmtNum, useI18n } from "@/lib/i18n";
import { useMe } from "@/lib/useMe";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";

type Row = Record<string, any>;
type WorkforceWorkersResponse = { workers: Row[]; total: number };
type Overview = {
  active_season: string;
  supplier_olive_purchases: Row[];
  supplier_oil_purchases: Row[];
  customer_olive_purchases: Row[];
  customer_oil_purchases: Row[];
  commercial_sales_invoices: Row[];
  traditional_invoices: Row[];
  summary: {
    supplier_olive_purchase_total: number | string;
    supplier_olive_paid_total: number | string;
    supplier_olive_outstanding_total: number | string;
    supplier_oil_purchase_total: number | string;
    supplier_oil_paid_total: number | string;
    supplier_oil_outstanding_total: number | string;
    customer_olive_purchase_total: number | string;
    customer_olive_paid_total: number | string;
    customer_oil_purchase_total: number | string;
    customer_oil_paid_total: number | string;
    gs_sales_revenue_total: number | string;
    gs_sales_collected_total: number | string;
  };
};
type Stats = {
  today: string;
  season: string;
  loads_today: number;
  loads_total: number;
  pending: number;
  olive_kg_today: number;
  oil_kg_today: number;
  olive_kg_total: number;
  oil_kg_total: number;
  revenue_today?: number;
  revenue_total?: number;
};

function Metric({ label, value, detail, icon: Icon, tone, to }: {
  label: string; value: string; detail: string; icon: LucideIcon; tone: string; to: string;
}) {
  return <Link to={to} className="block rounded-2xl outline-none transition hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 focus-visible:ring-sky-500">
    <section className={`min-w-0 rounded-2xl border p-4 shadow-sm ${tone}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold opacity-80">{label}</p>
        <Icon className="size-5 shrink-0 opacity-80" />
      </div>
      <p className="mt-3 truncate text-2xl font-bold tabular-nums" dir="ltr">{value}</p>
      <p className="mt-1 text-xs opacity-70">{detail}</p>
    </section>
  </Link>;
}

function SummaryPanel({ title, icon: Icon, total, paid, remaining, labels, tone, to }: {
  title: string; icon: LucideIcon; total: string; paid: string; remaining: string;
  labels: { total: string; paid: string; remaining: string }; tone: string; to: string;
}) {
  return <Link to={to} className="block rounded-2xl outline-none transition hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 focus-visible:ring-sky-500">
    <section className={`min-w-0 rounded-2xl border p-4 shadow-sm transition-colors ${tone}`}>
      <div className="mb-3 flex items-center gap-2">
        <span className="grid size-9 place-items-center rounded-xl bg-white/70"><Icon className="size-5" /></span>
        <h2 className="font-bold">{title}</h2>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div className="min-w-0"><p className="text-xs text-stone-500">{labels.total}</p><p className="mt-1 truncate text-sm font-bold tabular-nums" dir="ltr">{total}</p></div>
        <div className="min-w-0"><p className="text-xs text-stone-500">{labels.paid}</p><p className="mt-1 truncate text-sm font-bold text-emerald-700 tabular-nums" dir="ltr">{paid}</p></div>
        <div className="min-w-0"><p className="text-xs text-stone-500">{labels.remaining}</p><p className="mt-1 truncate text-sm font-bold text-rose-700 tabular-nums" dir="ltr">{remaining}</p></div>
      </div>
    </section>
  </Link>;
}

export default function ManagerDashboard() {
  const { lang } = useI18n();
  const ar = lang === "ar";
  const me = useMe();
  const isAdmin = me.data?.role === "admin";
  const stats = useQuery({ queryKey: ["manager-dashboard", "stats"], queryFn: () => apiGet<Stats>("/stats"), enabled: !!isAdmin, refetchInterval: 15_000 });
  const accounting = useQuery({ queryKey: ["manager-dashboard", "accounting"], queryFn: () => apiGet<Overview>("/accounting/overview"), enabled: !!isAdmin, refetchInterval: 30_000, retry: false });
  const workers = useQuery({ queryKey: ["manager-dashboard", "workers"], queryFn: () => apiGet<WorkforceWorkersResponse>("/workforce/workers"), enabled: !!isAdmin, refetchInterval: 30_000 });

  if (me.isPending) return <div className="p-6 text-stone-500">{ar ? "جارٍ التحقق من الصلاحيات…" : "Vérification des autorisations…"}</div>;
  if (!isAdmin) return <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800">{ar ? "هذه اللوحة متاحة للمدير فقط." : "Ce tableau de bord est réservé à l’administrateur."}</div>;

  const s = stats.data;
  const summary = accounting.data?.summary;
  const purchaseTotal = summary?.supplier_olive_purchase_total;
  const purchasePaid = summary?.supplier_olive_paid_total;
  const purchaseRemaining = summary?.supplier_olive_outstanding_total
    ?? (purchaseTotal != null && purchasePaid != null ? Number(purchaseTotal) - Number(purchasePaid) : null);
  const supplierOilTotal = summary?.supplier_oil_purchase_total;
  const supplierOilPaid = summary?.supplier_oil_paid_total;
  const supplierOilRemaining = summary?.supplier_oil_outstanding_total
    ?? (supplierOilTotal != null && supplierOilPaid != null ? Number(supplierOilTotal) - Number(supplierOilPaid) : null);
  const customerOliveTotal = summary?.customer_olive_purchase_total;
  const customerOlivePaid = summary?.customer_olive_paid_total;
  const customerOliveRemaining = customerOliveTotal != null && customerOlivePaid != null
    ? Number(customerOliveTotal) - Number(customerOlivePaid) : null;
  const customerOilTotal = summary?.customer_oil_purchase_total;
  const customerOilPaid = summary?.customer_oil_paid_total;
  const customerOilRemaining = customerOilTotal != null && customerOilPaid != null
    ? Number(customerOilTotal) - Number(customerOilPaid) : null;
  const salesTotal = summary?.gs_sales_revenue_total;
  const salesPaid = summary?.gs_sales_collected_total;
  const salesRemaining = salesTotal != null && salesPaid != null
    ? Number(salesTotal) - Number(salesPaid)
    : null;
  const gsChargements = (accounting.data?.supplier_olive_purchases ?? []).filter((purchase) => purchase.purchase_kind !== "OIL");
  const gsChargementCount = (status: string) => gsChargements.filter((purchase) => String(purchase.status ?? "").toUpperCase() === status).length;
  const loading = stats.isPending || accounting.isPending;
  const failed = stats.isError || accounting.isError;
  const money = (v: unknown) => fmtMoney(Number(v ?? 0));
  const moneyOrDash = (v: unknown) => v == null ? "—" : money(v);
  const refresh = () => { void Promise.all([stats.refetch(), accounting.refetch()]); };

  return <div className="mx-auto max-w-[1600px] space-y-4 pb-6" data-testid="manager-dashboard">
    <header className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-[#101C2B] px-5 py-4 text-white shadow-lg">
      <div>
        <div className="flex items-center gap-2"><Activity className="size-5 text-teal-300" /><h1 className="text-xl font-bold">{ar ? "لوحة المدير" : "Tableau de bord du directeur"}</h1></div>
        <p className="mt-1 text-sm text-slate-300">{ar ? "مراقبة المعصرة والعمليات التجارية في شاشة واحدة" : "Vue consolidée de l’huilerie et des opérations commerciales"}</p>
        <p className="mt-1 text-xs text-slate-400">{ar ? "الموسم الحالي" : "Saison active"}: {accounting.data?.active_season ?? s?.season ?? "—"}</p>
      </div>
      <Button variant="outline" size="sm" onClick={refresh} className="border-slate-600 bg-slate-800 text-white hover:bg-slate-700"><RefreshCw className="me-2 size-4" />{ar ? "تحديث" : "Actualiser"}</Button>
    </header>

    {failed && <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><AlertTriangle className="size-4 shrink-0" />{ar ? "تعذر تحميل بعض المؤشرات. الأرقام غير المتاحة لا تُعرض كأنها صفر." : "Certaines données n’ont pas pu être chargées. Les valeurs indisponibles ne sont pas présentées comme zéro."}</div>}

    <section className="space-y-3">
      <div className="flex items-center gap-2 px-1"><Activity className="size-5 text-sky-700" /><h2 className="text-base font-bold text-slate-800">{ar ? "مؤشرات نشاط اليوم" : "Indicateurs du jour"}</h2></div>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <Metric label={ar ? "حمولات اليوم" : "Réceptions aujourd’hui"} value={s ? fmtNum(s.loads_today) : "—"} detail={ar ? "عدد الحمولات المسجلة اليوم" : "Nombre de réceptions du jour"} icon={Boxes} tone="border-sky-200 bg-sky-50 text-sky-950" to="/loads" />
        <Metric label={ar ? "الزيتون المعالج اليوم" : "Olives traitées aujourd’hui"} value={s ? `${fmtNum(s.olive_kg_today)} kg` : "—"} detail={ar ? "حسب سجل الحمولات" : "D’après les chargements"} icon={Factory} tone="border-lime-200 bg-lime-50 text-lime-950" to="/loads" />
        <Metric label={ar ? "الزيت المستخرج اليوم" : "Huile extraite aujourd’hui"} value={s ? `${fmtNum(s.oil_kg_today)} kg` : "—"} detail={ar ? "حسب وحدة سجل الإنتاج" : "Selon l’unité du registre de production"} icon={Activity} tone="border-amber-200 bg-amber-50 text-amber-950" to="/loads" />
        <Metric label={ar ? "مداخيل العصر اليوم" : "Recettes de pressage aujourd’hui"} value={s ? money(s.revenue_today) : "—"} detail="TND" icon={Wallet} tone="border-violet-200 bg-violet-50 text-violet-950" to="/comptabilite" />
      </div>
    </section>

    <section className="space-y-3">
      <div className="flex items-center gap-2 px-1"><ShoppingBasket className="size-5 text-emerald-700" /><h2 className="text-base font-bold text-slate-800">{ar ? "المشتريات والتزويد" : "Achats et approvisionnements"}</h2></div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryPanel title={ar ? "شراء الزيتون من المزودين" : "Achats d’olives auprès des fournisseurs"} icon={ShoppingBasket}
          total={moneyOrDash(purchaseTotal)} paid={moneyOrDash(purchasePaid)} remaining={moneyOrDash(purchaseRemaining)}
          labels={{ total: ar ? "إجمالي معتمد" : "Total approuvé", paid: ar ? "المدفوع" : "Payé", remaining: ar ? "غير مدفوع" : "Impayé" }} tone="border-emerald-200 bg-emerald-50 text-emerald-950" to="/commercial?tab=purchases" />
        <SummaryPanel title={ar ? "شراء الزيت من المزودين" : "Achats d’huile auprès des fournisseurs"} icon={ShoppingBasket}
          total={moneyOrDash(supplierOilTotal)} paid={moneyOrDash(supplierOilPaid)} remaining={moneyOrDash(supplierOilRemaining)}
          labels={{ total: ar ? "إجمالي معتمد" : "Total approuvé", paid: ar ? "المدفوع" : "Payé", remaining: ar ? "غير مدفوع" : "Impayé" }} tone="border-amber-200 bg-amber-50 text-amber-950" to="/commercial?tab=supplier-oil-purchases" />
        <SummaryPanel title={ar ? "شراء الزيتون من الحرفاء" : "Achats d’olives auprès des clients"} icon={ShoppingBasket}
          total={moneyOrDash(customerOliveTotal)} paid={moneyOrDash(customerOlivePaid)} remaining={moneyOrDash(customerOliveRemaining)}
          labels={{ total: ar ? "إجمالي الشراء" : "Total achats", paid: ar ? "المدفوع" : "Payé", remaining: ar ? "غير مدفوع" : "Impayé" }} tone="border-cyan-200 bg-cyan-50 text-cyan-950" to="/commercial?tab=customer-purchases" />
        <SummaryPanel title={ar ? "شراء الزيت من الحرفاء" : "Achats d’huile auprès des clients"} icon={ShoppingBasket}
          total={moneyOrDash(customerOilTotal)} paid={moneyOrDash(customerOilPaid)} remaining={moneyOrDash(customerOilRemaining)}
          labels={{ total: ar ? "إجمالي الشراء" : "Total achats", paid: ar ? "المدفوع" : "Payé", remaining: ar ? "غير مدفوع" : "Impayé" }} tone="border-violet-200 bg-violet-50 text-violet-950" to="/commercial?tab=custody" />
      </div>
    </section>

    <section className="space-y-3">
      <div className="flex items-center gap-2 px-1"><ClipboardList className="size-5 text-indigo-700" /><h2 className="text-base font-bold text-slate-800">{ar ? "المبيعات والحمولات والفواتير" : "Ventes, chargements et facturation"}</h2></div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <SummaryPanel title={ar ? "بيع الزيت للحرفاء" : "Ventes d’huile aux clients"} icon={ShoppingCart}
          total={moneyOrDash(salesTotal)} paid={moneyOrDash(salesPaid)} remaining={moneyOrDash(salesRemaining)}
          labels={{ total: ar ? "صافي المبيعات" : "Ventes nettes", paid: ar ? "المقبوض" : "Encaissé", remaining: ar ? "المتبقي" : "À encaisser" }} tone="border-blue-200 bg-blue-50 text-blue-950" to="/commercial?tab=sales" />

        <Link to="/loads" className="block rounded-2xl outline-none transition hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 focus-visible:ring-sky-500">
          <section className="h-full rounded-2xl border border-orange-200 bg-orange-50 p-4 text-orange-950 shadow-sm">
            <div className="flex items-center gap-2"><CalendarClock className="size-5 text-orange-700" /><h2 className="font-bold">{ar ? "حالة الحمولات" : "État des chargements"}</h2></div>
            <div className="mt-3 grid grid-cols-2 gap-3"><div><p className="text-2xl font-bold">{s ? fmtNum(s.pending) : "—"}</p><p className="text-xs opacity-70">{ar ? "قيد المعالجة" : "En attente"}</p></div><div><p className="text-2xl font-bold">{s ? fmtNum(s.loads_total - s.pending) : "—"}</p><p className="text-xs opacity-70">{ar ? "اكتملت" : "Terminés"}</p></div></div>
          </section>
        </Link>

        <Link to="/loads?tab=chargement&chargement_section=olive-purchases" className="block rounded-2xl outline-none transition hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 focus-visible:ring-sky-500">
          <section className="h-full rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-950 shadow-sm">
            <div className="flex items-center gap-2"><Boxes className="size-5 text-emerald-700" /><h2 className="font-bold">{ar ? "حالة الشحنات – التسيير التجاري" : "État des chargements – Gestion commerciale"}</h2></div>
            <div className="mt-3 grid grid-cols-4 gap-2">
              <div><p className="text-xl font-bold tabular-nums">{accounting.data ? gsChargements.length : "—"}</p><p className="text-xs opacity-70">{ar ? "الإجمالي" : "Total"}</p></div>
              <div><p className="text-xl font-bold text-amber-700 tabular-nums">{accounting.data ? gsChargementCount("DRAFT") : "—"}</p><p className="text-xs opacity-70">{ar ? "مسودة" : "Brouillons"}</p></div>
              <div><p className="text-xl font-bold text-emerald-700 tabular-nums">{accounting.data ? gsChargementCount("APPROVED") : "—"}</p><p className="text-xs opacity-70">{ar ? "معتمد" : "Approuvés"}</p></div>
              <div><p className="text-xl font-bold text-rose-700 tabular-nums">{accounting.data ? gsChargementCount("CANCELLED") : "—"}</p><p className="text-xs opacity-70">{ar ? "ملغى" : "Annulés"}</p></div>
            </div>
          </section>
        </Link>

        <Link to="/factures" className="block rounded-2xl outline-none transition hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 focus-visible:ring-sky-500">
          <section className="h-full rounded-2xl border border-indigo-200 bg-indigo-50 p-4 text-indigo-950 shadow-sm">
            <div className="flex items-center gap-2"><ClipboardList className="size-5 text-indigo-700" /><h2 className="font-bold">{ar ? "فواتير العصر" : "Factures de pressage"}</h2></div>
            <p className="mt-3 text-2xl font-bold tabular-nums">{accounting.data ? accounting.data.traditional_invoices.length : "—"}</p>
            <p className="mt-1 text-xs opacity-70">{ar ? "الفواتير التقليدية لعمليات العصر" : "Facturation traditionnelle des opérations de pressage"}</p>
          </section>
        </Link>

        <Link to="/commercial?tab=factures" className="block rounded-2xl outline-none transition hover:-translate-y-0.5 hover:shadow-md focus-visible:ring-2 focus-visible:ring-sky-500">
          <section className="h-full rounded-2xl border border-fuchsia-200 bg-fuchsia-50 p-4 text-fuchsia-950 shadow-sm">
            <div className="flex items-center gap-2"><ClipboardList className="size-5 text-fuchsia-700" /><h2 className="font-bold">{ar ? "فواتير التسيير التجاري" : "Factures Gestion commerciale"}</h2></div>
            <p className="mt-3 text-2xl font-bold text-fuchsia-800 tabular-nums">{accounting.data ? accounting.data.commercial_sales_invoices.length : "—"}</p>
            <p className="mt-1 text-xs opacity-70">{ar ? "فواتير المبيعات التجارية في GS" : "Factures de vente du module GS"}</p>
          </section>
        </Link>
      </div>
    </section>

    <section className="rounded-2xl border border-teal-200 bg-teal-50 p-4 shadow-sm md:col-span-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="font-bold text-teal-950">{ar ? "العمال" : "Employés"}</h2>
        <span className="rounded-full bg-white/80 px-3 py-1 text-sm font-semibold text-teal-800">{workers.data ? workers.data.workers.length : "—"}</span>
      </div>
      {workers.isError ? <p className="text-sm text-amber-700">{ar ? "تعذر تحميل قائمة العمال." : "Impossible de charger la liste des employés."}</p> :
        workers.isPending ? <p className="text-sm text-stone-500">{ar ? "جارٍ تحميل العمال…" : "Chargement des employés…"}</p> :
        workers.data.workers.length === 0
          ? <p className="text-sm text-stone-500">{ar ? "لا يوجد عمال مسجلون." : "Aucun employé enregistré."}</p>
          : <div className="flex flex-col gap-2">
              {workers.data.workers.map((worker) => (
                <div key={String(worker.id ?? worker._id ?? worker.username)} className="flex w-full items-center justify-between gap-3 rounded-xl border border-teal-100 bg-white/80 px-3 py-3">
                  <span className="min-w-0 truncate font-medium text-stone-800">{worker.full_name || worker.username || "—"}</span>
                  <span className={`shrink-0 rounded-full px-2 py-1 text-xs font-semibold ${worker.archived === true ? "bg-stone-100 text-stone-700" : worker.active === true ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"}`}>{worker.archived === true ? (ar ? "مؤرشف" : "Archivé") : worker.active === true ? (ar ? "نشط" : "Actif") : (ar ? "غير نشط" : "Inactif")}</span>
                </div>
              ))}
            </div>}
      <p className="mt-3 text-xs text-teal-900/70">{ar ? "تعرض هذه القائمة جميع العمال وحالتهم الحالية؛ وتُتابع أوقات الحضور والانصراف في صفحة Travail." : "Liste complète du registre des employés avec leur statut actuel ; les heures de présence et de départ sont suivies dans la page Travail."}</p>
    </section>
    {loading && <p className="text-xs text-stone-500">{ar ? "جارٍ تحميل البيانات…" : "Chargement des données…"}</p>}
  </div>;
}
