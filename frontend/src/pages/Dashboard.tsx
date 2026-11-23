import { useCallback, useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Droplets, PackagePlus, Scale, ScanLine, Coins, Clock, FileText, Layers } from "lucide-react";
import { apiGet } from "@/lib/api";
import type { Load, Stats } from "@/lib/types";
import { fmtMoney, fmtNum, useI18n } from "@/lib/i18n";
import { useMe } from "@/lib/useMe";
import { CodeBadge, StatusPill } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import IntakePanel from "@/components/IntakePanel";
import QrScanDialog from "@/components/QrScanDialog";
import CommercialOverviewPanel from "@/components/CommercialOverviewPanel";
import OlivePurchaseTracking from "@/components/OlivePurchaseTracking";

function KpiCard({ label, value, icon, testId, tint }: { label: string; value: React.ReactNode; icon: React.ReactNode; testId: string; tint: string }) {
  return (
    <div data-testid={testId} className={`flex min-h-40 flex-col justify-between rounded-3xl border p-6 shadow-[0_1px_2px_rgba(0,0,0,0.03)] transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-md ${tint}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="text-[15px] leading-snug font-semibold opacity-80">{label}</div>
        <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-white/90 shadow-sm [&_svg]:size-5 [&_svg]:stroke-[2.5]">{icon}</div>
      </div>
      <div className="mt-4 font-heading text-3xl font-bold tracking-tight" dir="ltr">{value}</div>
    </div>
  );
}

export default function Dashboard() {
  const { t, lang } = useI18n();
  const ar = lang === "ar";
  const me = useMe();
  const navigate = useNavigate();
  const isAdmin = me.data?.role === "admin";
  const [intakeOpen, setIntakeOpen] = useState(false);
  const [scanOpen, setScanOpen] = useState(false);
  const closeScan = useCallback(() => setScanOpen(false), []);
  const [code, setCode] = useState("");
  const [premiumTheme, setPremiumTheme] = useState(() => localStorage.getItem("oroverde-dashboard-theme") === "premium");
  useEffect(() => {
    const syncTheme = () => setPremiumTheme(localStorage.getItem("oroverde-dashboard-theme") === "premium");
    window.addEventListener("oroverde-dashboard-theme-change", syncTheme);
    window.addEventListener("storage", syncTheme);
    return () => {
      window.removeEventListener("oroverde-dashboard-theme-change", syncTheme);
      window.removeEventListener("storage", syncTheme);
    };
  }, []);
  const stats = useQuery({ queryKey: ["stats"], queryFn: () => apiGet<Stats>("/stats") });
  const loads = useQuery({ queryKey: ["loads", "", ""], queryFn: () => apiGet<Load[]>("/loads") });
  const s = stats.isError ? undefined : stats.data;
  const today = (loads.isError ? [] : (loads.data ?? [])).filter((l) => s && l.day === s.today);
  const invoices = useQuery({ queryKey: ["invoices", "load-links"], queryFn: () => apiGet<Array<{ id: string; load_id: string; number: string }>>("/invoices") });
  const invoiceByLoad = new Map((invoices.data ?? []).map((invoice) => [invoice.load_id, invoice]));

  return (
    <div className={`mx-auto max-w-7xl dashboard-home ${premiumTheme ? "dashboard-home--premium" : ""}`} data-dashboard-theme={premiumTheme ? "premium" : "classic"}>
      <div className="dashboard-home__welcome mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-4xl font-bold tracking-tight text-stone-900 md:text-5xl" data-testid="dashboard-greeting">
            {t("welcome")}, {me.data?.full_name ?? ""}
          </h1>
          <p className="mt-1 text-lg text-stone-500">{t("app_tagline")}</p>
        </div>
        <Button onClick={() => setIntakeOpen(true)} data-testid="dashboard-new-reception-button" className="h-11 rounded-xl bg-[#1F4D2B] px-5 text-base shadow-md shadow-green-900/20 transition-transform hover:bg-[#173B21] active:scale-[0.97]">
          <PackagePlus className="size-5" /> {t("new_reception")}
        </Button>
      </div>

      <div className="dashboard-home__top-grid grid gap-5 lg:grid-cols-[1.15fr_2fr]">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const v = code.trim();
            if (v) navigate(/^\d{10}$/.test(v) ? `/search?code=${v}` : `/search?q=${encodeURIComponent(v)}`);
          }}
          className="dashboard-home__search relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#1B2A1C] via-[#203320] to-[#3A3A1C] p-7 text-white shadow-xl shadow-green-950/25"
          data-testid="dashboard-quick-search"
        >
          <div className="pointer-events-none absolute -end-16 -top-16 size-48 rounded-full bg-lime-400/10 blur-2xl" />
          <div className="text-sm font-semibold uppercase tracking-wide text-lime-300">{t("quick_search_title")}</div>
          <div className="mt-1 text-sm text-white/70">{t("quick_search_hint")}</div>
          <div className="mt-7 flex gap-3">
            <button type="button" onClick={() => setScanOpen(true)} data-testid="qr-scan-button" title={t("scan_qr")} className="grid size-14 shrink-0 place-items-center rounded-xl bg-lime-400 text-[#1B2A1C] shadow-lg shadow-lime-500/30 transition-transform duration-150 hover:scale-105 active:scale-95">
              <ScanLine className="size-8" />
            </button>
            <div className="relative flex-1">
              <Input
                data-testid="quick-code-search-input"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder={t("search_any_hint")}
                className="h-14 rounded-xl border-white/15 bg-white/5 text-lg text-white placeholder:text-sm placeholder:text-white/35 focus-visible:ring-lime-400/40"
              />
            </div>
            <Button type="submit" data-testid="quick-code-search-btn" className="h-14 rounded-xl bg-[#2F6B3A] px-6 text-base hover:bg-[#387E45]">
              {t("search_btn")}
            </Button>
          </div>
        </form>

        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <KpiCard testId="kpi-loads-today" label={t("today_arrivals")} value={s?.loads_today ?? "—"} icon={<Layers />} tint="border-rose-200 bg-rose-50 text-rose-900 [&_svg]:text-rose-600" />
          <KpiCard testId="kpi-olive-today" label={t("olive_today")} value={<>{fmtNum(s?.olive_kg_today)} <span className="text-2xl">{t("kg")}</span></>} icon={<Scale />} tint="border-lime-200 bg-[#F2F8EE] text-[#1E3A14] [&_svg]:text-lime-700" />
          <KpiCard testId="kpi-oil-today" label={t("oil_today")} value={<>{fmtNum(s?.oil_kg_today)} <span className="text-2xl">{t("kg")}</span></>} icon={<Droplets />} tint="border-yellow-200 bg-[#FEFCE8] text-[#713F12] [&_svg]:text-amber-600" />
          {isAdmin ? (
            <KpiCard testId="admin-revenue-metric-card" label={t("revenue_today")} value={<>{fmtMoney(s?.revenue_today)}</>} icon={<Coins />} tint="border-violet-200 bg-[#FAF5FF] text-[#581C87] [&_svg]:text-violet-600" />
          ) : (
            <KpiCard testId="kpi-pending" label={t("pending_loads")} value={s?.pending ?? "—"} icon={<Clock />} tint="border-orange-200 bg-orange-50 text-orange-900 [&_svg]:text-orange-600" />
          )}
        </div>
      </div>

      <CommercialOverviewPanel />

      <h2 className="dashboard-home__section-title mb-4 mt-10 font-heading text-2xl font-bold text-stone-900">{t("today_arrivals")}</h2>
      <div className="dashboard-home__table overflow-hidden rounded-3xl border border-stone-200/80 bg-white shadow-sm">
        <Table data-testid="today-arrivals-table">
          <TableHeader>
            <TableRow className="bg-[#E5EFF7] hover:bg-[#E5EFF7]">
              <TableHead className="h-12 ps-4 text-start text-[15px] font-semibold text-[#31536F]">{t("code")}</TableHead>
              <TableHead className="text-start text-[15px] font-semibold text-[#31536F]">{t("client")}</TableHead>
              <TableHead className="text-start text-[15px] font-semibold text-[#31536F]">{t("phone")}</TableHead>
              <TableHead className="text-start text-[15px] font-semibold text-[#31536F]">{t("varieties")}</TableHead>
              <TableHead className="text-end text-[15px] font-semibold text-[#31536F]">{t("olive_kg")}</TableHead>
              <TableHead className="text-end text-[15px] font-semibold text-[#31536F]">{t("oil_kg")}</TableHead>
              <TableHead className="text-start text-[15px] font-semibold text-[#31536F]">{t("status")}</TableHead>
              <TableHead className="text-start text-[15px] font-semibold text-[#31536F]">{ar ? "الفاتورة" : "Facture"}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {today.length === 0 && (
              <TableRow><TableCell colSpan={8} className="py-12 text-center text-stone-500">{t("no_data")}</TableCell></TableRow>
            )}
            {today.map((l) => (
              <TableRow key={l.id} data-testid={`today-row-${l.code}`} className={l.status === "cancelled" ? "bg-red-50/40 text-[15px] opacity-70" : "text-[15px] transition-colors hover:bg-amber-50/40"}>
                <TableCell className="ps-4"><Link to={`/search?code=${l.code}`}><CodeBadge code={l.code} /></Link></TableCell>
                <TableCell className="text-stone-900">{l.client_name}</TableCell>
                <TableCell className="font-mono text-stone-500" dir="ltr">{l.phone}</TableCell>
                <TableCell className="text-stone-700">{l.variety || "—"}</TableCell>
                <TableCell className="text-end font-semibold text-lime-800">{fmtNum(l.olive_kg)} {t("kg")}</TableCell>
                <TableCell className="text-end font-semibold text-amber-700">{l.oil_kg != null ? `${fmtNum(l.oil_kg, 1)} ${t("liter")}` : "—"}</TableCell>
                <TableCell><StatusPill status={l.status} size="large" /></TableCell>
                <TableCell>{invoiceByLoad.has(l.id) ? <Link to={`/factures?invoice_id=${encodeURIComponent(invoiceByLoad.get(l.id)!.id)}`} className="inline-flex items-center gap-1 rounded-lg bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-100"><FileText className="size-4" />{invoiceByLoad.get(l.id)!.number}</Link> : <span className="text-stone-400">—</span>}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <OlivePurchaseTracking />

      <section className="mt-12 space-y-10" aria-labelledby="accueil-gallery-title" data-testid="accueil-gallery">
        <div>
          <h2 id="accueil-gallery-title" className="font-heading text-2xl font-bold text-stone-900">{ar ? "مراحل إنتاج زيت الزيتون" : "Les étapes de production de l'huile d'olive"}</h2>
          <p className="mt-1 text-sm text-stone-500">{ar ? "رحلة الزيتون من الاستقبال والفرز إلى الاستخراج والتحليل والتخزين والتعبئة" : "Du contrôle des olives à l'extraction, l'analyse, le stockage et la mise en bouteille"}</p>
        </div>
        {[
          {
            title: ar ? "1. استقبال الزيتون وفرزه" : "1. Réception et tri des olives",
            description: ar ? "الوزن والاستقبال والفرز والتغذية الأولية لخط الإنتاج" : "Pesée, réception, tri et alimentation de la ligne",
            images: [
              ["IMG_8910.jpg", ar ? "وزن الزيتون عند الاستقبال" : "Pesée des olives à la réception"],
              ["IMG_8907.jpg", ar ? "فرز الزيتون على خط الاستقبال" : "Tri des olives sur convoyeur"],
              ["IMG_8914.jpg", ar ? "الفرز والمراقبة اليدوية" : "Tri et contrôle manuel"],
              ["IMG_8920.jpg", ar ? "نقل الزيتون إلى معدات المعالجة" : "Acheminement des olives vers le traitement"],
            ],
          },
          {
            title: ar ? "2. المعالجة والاستخراج" : "2. Préparation et extraction",
            description: ar ? "معدات التحضير والفصل والاستخراج ومراقبة تشغيل الخط" : "Préparation, centrifugation, séparation et conduite de la ligne",
            images: [
              ["IMG_8926.jpg", ar ? "معدات خط استخراج الزيت" : "Équipements de la ligne d'extraction"],
              ["IMG_8928.jpg", ar ? "تشغيل معدات المعالجة" : "Conduite des équipements de traitement"],
              ["IMG_8923.jpg", ar ? "متابعة آلة الاستخراج" : "Surveillance d'une machine d'extraction"],
              ["IMG_8924.jpg", ar ? "خط معالجة آلي" : "Ligne de traitement automatisée"],
              ["IMG_8908.jpg", ar ? "معدات الفصل والمعالجة" : "Équipement de séparation et de traitement"],
              ["IMG_8911.jpg", ar ? "فاصل بالطرد المركزي" : "Séparateur centrifuge"],
              ["IMG_8913.jpg", ar ? "معدات صناعية لاستخراج الزيت" : "Équipement industriel d'extraction"],
              ["IMG_8906.jpg", ar ? "منظومة صناعية متكاملة" : "Installation industrielle intégrée"],
              ["IMG_8921.jpg", ar ? "مراقبة وضبط المعدات" : "Contrôle et réglage des équipements"],
            ],
          },
          {
            title: ar ? "3. التحليل ومراقبة الجودة" : "3. Analyses et contrôle qualité",
            description: ar ? "أخذ العينات وفحص خصائص الزيت والتحقق من الجودة" : "Échantillonnage, analyses et vérification de la qualité de l'huile",
            images: [
              ["IMG_8916.jpg", ar ? "فحص عينة من الزيت" : "Examen d'un échantillon d'huile"],
              ["IMG_8917.jpg", ar ? "تحليل الزيت في المختبر" : "Analyse de l'huile en laboratoire"],
              ["IMG_8918.jpg", ar ? "اختبارات مخبرية للزيت" : "Essais de laboratoire sur l'huile"],
              ["IMG_8919.jpg", ar ? "اختبارات وقياسات مخبرية" : "Tests et mesures en laboratoire"],
            ],
          },
          {
            title: ar ? "4. تخزين الزيت" : "4. Stockage de l'huile",
            description: ar ? "حفظ الزيت في خزانات مخصصة قبل التوزيع أو التعبئة" : "Conservation de l'huile dans des cuves avant distribution ou conditionnement",
            images: [
              ["IMG_8909.jpg", ar ? "خزانات تخزين من الفولاذ المقاوم للصدأ" : "Cuves de stockage en acier inoxydable"],
              ["IMG_8912.jpg", ar ? "خزانات صناعية كبيرة" : "Grandes cuves industrielles"],
              ["IMG_8915.jpg", ar ? "منطقة تخزين الزيت" : "Espace de stockage de l'huile"],
            ],
          },
          {
            title: ar ? "5. التعبئة والتغليف" : "5. Mise en bouteille et conditionnement",
            description: ar ? "ملء القوارير وإغلاقها وتجهيزها للتوزيع" : "Remplissage, fermeture et préparation des bouteilles pour la distribution",
            images: [
              ["IMG_8922.jpg", ar ? "خط ملء قوارير الزيت" : "Ligne de remplissage des bouteilles"],
              ["IMG_8925.jpg", ar ? "تعبئة القوارير وإغلاقها" : "Remplissage et fermeture des bouteilles"],
              ["IMG_8927.jpg", ar ? "خط التغليف النهائي" : "Ligne de conditionnement final"],
            ],
          },
          {
            title: ar ? "6. متابعة الإنتاج" : "6. Suivi de la production",
            description: ar ? "متابعة مؤشرات الإنتاج والعمليات الصناعية" : "Suivi des indicateurs et des opérations de production",
            images: [
              ["IMG_8929.jpg", ar ? "لوحة متابعة الإنتاج" : "Tableau de suivi de la production"],
            ],
          },
        ].map((stage) => (
          <div key={stage.title}>
            <div className="mb-4">
              <h3 className="font-heading text-lg font-bold text-stone-800">{stage.title}</h3>
              <p className="mt-1 text-sm text-stone-500">{stage.description}</p>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {stage.images.map(([file, caption]) => (
                <figure key={file} className="group overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
                  <img src={`/images/accueil/${file}`} alt={caption} loading="lazy" decoding="async" className="aspect-[4/3] w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]" />
                  <figcaption className="min-h-12 px-3 py-2 text-sm font-medium text-stone-700">{caption}</figcaption>
                </figure>
              ))}
            </div>
          </div>
        ))}
      </section>

      <Sheet open={intakeOpen} onOpenChange={setIntakeOpen}>
        <SheetContent side="right" className="w-full overflow-y-auto bg-[#F9F8F3] p-4 sm:max-w-lg" data-testid="new-reception-sheet">
          <SheetTitle className="mb-2 font-heading text-lg">{t("new_reception")}</SheetTitle>
          <div className="origin-top-left" style={{ zoom: 0.82 }}><IntakePanel stacked /></div>
        </SheetContent>
      </Sheet>
      <QrScanDialog open={scanOpen} onClose={closeScan} />
    </div>
  );
}
