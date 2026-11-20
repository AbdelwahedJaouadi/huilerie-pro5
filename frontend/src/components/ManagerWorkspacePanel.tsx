import { Link } from "react-router-dom";
import { BarChart3, FileText, Settings, Users, Wallet, Warehouse } from "lucide-react";
import { useI18n } from "@/lib/i18n";

const destinations = [
  {
    to: "/workforce",
    icon: Users,
    tone: "border-indigo-200 bg-indigo-50 text-indigo-800",
    ar: "جدول العمال",
    fr: "Personnel",
    arHint: "الحضور والانصراف وتصحيح السجلات",
    frHint: "Présences, départs et corrections",
  },
  {
    to: "/reports",
    icon: BarChart3,
    tone: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-800",
    ar: "التقارير",
    fr: "Rapports",
    arHint: "تقارير الإنتاج والإيرادات والعمال",
    frHint: "Production, recettes et personnel",
  },
  {
    to: "/factures",
    icon: FileText,
    tone: "border-emerald-200 bg-emerald-50 text-emerald-800",
    ar: "الفواتير",
    fr: "Factures",
    arHint: "متابعة الفواتير والمدفوعات",
    frHint: "Suivi des factures et paiements",
  },
  {
    to: "/commercial",
    icon: Warehouse,
    tone: "border-cyan-200 bg-cyan-50 text-cyan-800",
    ar: "الإدارة التجارية GS",
    fr: "Gestion commerciale GS",
    arHint: "المشتريات والمخزون والإنتاج والمبيعات",
    frHint: "Achats, stock, production et ventes",
  },
  {
    to: "/commercial?tab=accounting",
    icon: Wallet,
    tone: "border-amber-200 bg-amber-50 text-amber-900",
    ar: "محاسبة GS والخزينة",
    fr: "Comptabilité GS et trésorerie",
    arHint: "الحسابات وحركة الخزينة والمطابقة",
    frHint: "Comptes, trésorerie et rapprochement",
  },
  {
    to: "/settings",
    icon: Settings,
    tone: "border-violet-200 bg-violet-50 text-violet-800",
    ar: "الإعدادات والصلاحيات",
    fr: "Paramètres et droits",
    arHint: "إدارة المستخدمين وإعدادات المعصرة",
    frHint: "Utilisateurs et configuration de l’huilerie",
  },
];

export default function ManagerWorkspacePanel() {
  const { lang } = useI18n();
  const ar = lang === "ar";

  return (
    <section
      className="mt-7 rounded-3xl border border-stone-200 bg-white p-4 shadow-sm sm:p-5"
      data-testid="manager-workspace-panel"
      dir={ar ? "rtl" : "ltr"}
    >
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="font-heading text-xl font-bold text-stone-900">
            {ar ? "إدارة المعصرة" : "Pilotage de l’huilerie"}
          </h2>
          <p className="mt-1 text-sm text-stone-500">
            {ar
              ? "وصول مباشر إلى أدوات الإدارة الموجودة دون تكرار وظائفها."
              : "Accès direct aux outils existants, sans dupliquer leurs fonctions."}
          </p>
        </div>
        <span className="rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs font-semibold text-stone-600">
          {ar ? "للمدير فقط" : "Administrateur"}
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {destinations.map(({ to, icon: Icon, tone, ar: arLabel, fr, arHint, frHint }) => (
          <Link
            key={to}
            to={to}
            data-testid={`manager-shortcut-${to.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "")}`}
            className="group flex min-w-0 items-center gap-3 rounded-2xl border border-stone-200 bg-white p-3 text-start transition-colors hover:border-stone-300 hover:bg-stone-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
          >
            <span className={`grid size-11 shrink-0 place-items-center rounded-xl border ${tone}`}>
              <Icon className="size-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block font-semibold text-stone-900">
                {ar ? arLabel : fr}
              </span>
              <span className="mt-0.5 block text-xs leading-relaxed text-stone-500">
                {ar ? arHint : frHint}
              </span>
            </span>
            <span aria-hidden="true" className="shrink-0 text-lg text-stone-300 transition-transform group-hover:-translate-x-0.5">
              {ar ? "‹" : "›"}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
