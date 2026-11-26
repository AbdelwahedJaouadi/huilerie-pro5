import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ClipboardList, RefreshCw, ShieldAlert } from "lucide-react";
import { apiGet } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type Candidate = {
  candidate_key: string;
  source_type: string;
  source_id: string;
  event_type: string;
  source_document_number?: string | null;
  business_date?: string | null;
  currency?: string | null;
  amount?: string | null;
  quantity?: string | null;
  unit?: string | null;
  eligibility: string;
  blocking_reasons?: string[];
  warnings?: string[];
};
type Finding = {
  source_type?: string;
  source_id?: string;
  source_document_number?: string | null;
  reason: string;
  candidate_key?: string;
  observed_count?: number;
};
type Preview = {
  candidate_events: Candidate[];
  unresolved_items: Finding[];
  summary: {
    candidate_event_count: number;
    unresolved_item_count: number;
    eligibility_counts: Record<string, number>;
    source_counts: Record<string, number>;
    unresolved_reason_counts: Record<string, number>;
    duplicate_candidate_key_count: number;
  };
  active_season: string;
  season_code: string;
  limit_per_source: number;
  has_more: Record<string, boolean>;
  read_only: boolean;
  database_writes: boolean;
  posting_enabled: boolean;
};

const eligibilityText = (value: string, ar: boolean) => {
  if (value === "ELIGIBLE_FOR_REVIEW") return ar ? "جاهز لمراجعة المحاسب" : "À examiner";
  if (value === "BLOCKED") return ar ? "محجوب" : "Bloqué";
  if (value === "INFORMATIONAL_ONLY") return ar ? "معلومة فقط" : "Informatif";
  if (value === "LEGACY_UNRESOLVED") return ar ? "غير محسوم" : "Non résolu";
  return value || (ar ? "غير معروف" : "Inconnu");
};
const amountText = (row: Candidate) => row.amount == null ? "—" : `${row.amount} ${row.currency || ""}`.trim();

function Metric({ title, value, detail, tone }: { title: string; value: number; detail: string; tone: "green" | "amber" | "red" | "slate" }) {
  const styles = {
    green: "border-emerald-200 bg-emerald-50 text-emerald-900",
    amber: "border-amber-200 bg-amber-50 text-amber-900",
    red: "border-red-200 bg-red-50 text-red-900",
    slate: "border-stone-200 bg-stone-50 text-stone-800",
  };
  return <Card className={styles[tone]}><CardContent className="p-4">
    <p className="text-sm font-medium opacity-80">{title}</p>
    <p className="mt-1 text-2xl font-bold tabular-nums">{value}</p>
    <p className="mt-1 text-xs opacity-75">{detail}</p>
  </CardContent></Card>;
}

export default function ReconciliationPreview() {
  const { data, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ["accounting-reconciliation-preview"],
    queryFn: () => apiGet<Preview>("/accounting/reconciliation-preview?limit=200"),
    staleTime: 30_000,
    retry: 1,
  });
  const { lang } = useI18n();
  const ar = lang === "ar";

  if (isPending) return <Card><CardContent className="p-6 text-sm text-stone-600">{ar ? "جارٍ تحميل معاينة التسوية…" : "Chargement de l’aperçu de rapprochement…"}</CardContent></Card>;
  if (isError || !data) return <Card className="border-red-200"><CardContent className="flex flex-wrap items-center gap-3 p-5 text-red-800">
    <AlertTriangle className="size-5 shrink-0" />
    <span className="flex-1 text-sm">{ar ? "تعذّر تحميل المعاينة. يلزم حساب إداري نشط وصلاحية المحاسبة." : "Impossible de charger l’aperçu. Une session administrateur active est requise."}</span>
    <button type="button" onClick={() => void refetch()} className="inline-flex items-center gap-2 rounded-lg border border-red-300 px-3 py-2 text-sm"><RefreshCw className="size-4" />{ar ? "إعادة المحاولة" : "Réessayer"}</button>
  </CardContent></Card>;

  const counts = data.summary.eligibility_counts || {};
  const eligible = counts.ELIGIBLE_FOR_REVIEW || 0;
  const blocked = counts.BLOCKED || 0;
  const unresolved = (counts.LEGACY_UNRESOLVED || 0) + data.unresolved_items.length;
  const more = Object.entries(data.has_more || {}).filter(([, value]) => value).map(([key]) => key);
  const sourceName = (value: string) => ({
    TRADITIONAL_INVOICE: ar ? "فاتورة المعصرة" : "Facture huilerie",
    TRADITIONAL_RECEIPT: ar ? "قبض المعصرة" : "Encaissement huilerie",
    GS_OLIVE_PURCHASE: ar ? "شراء زيتون GS" : "Achat olives GS",
    GS_SUPPLIER_PAYMENT: ar ? "دفعة مورّد GS" : "Paiement fournisseur GS",
    GS_SALE_INVOICE: ar ? "فاتورة بيع GS" : "Facture de vente GS",
    GS_SALE_PAYMENT: ar ? "قبض مبيعات GS" : "Encaissement vente GS",
    GS_SALE_PAYMENT_REVERSAL: ar ? "عكس قبض GS" : "Annulation d’encaissement GS",
  } as Record<string, string>)[value] || value;
  const reasonName = (value: string) => {
    const labels: Record<string, string> = {
      INVOICE_HISTORY_IS_AUDIT_EVIDENCE_NOT_RECEIPTS: ar
        ? "سجل الفاتورة للتتبع والتدقيق، وليس إثباتاً للدفع"
        : "Historique de facture : élément de traçabilité, pas un justificatif de paiement",
      LEGACY_PAID_AGGREGATE_WITHOUT_ITEMIZED_RECEIPTS: ar
        ? "مبلغ مدفوع قديم دون وصولات دفع مفصلة"
        : "Montant payé historique sans justificatifs de paiement détaillés",
      ITEMIZED_PAYMENTS_DO_NOT_RECONCILE_TO_PAID_SNAPSHOT: ar
        ? "مجموع الدفعات لا يطابق المبلغ المدفوع المسجل"
        : "Le total des paiements ne correspond pas au montant payé enregistré",
    };
    return labels[value] || value.toLowerCase().replaceAll("_", " ");
  };

  return <div className="space-y-5" data-testid="accounting-reconciliation-preview">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <div className="flex items-center gap-2"><ClipboardList className="size-5 text-emerald-700" /><h2 className="text-lg font-bold text-stone-900">{ar ? "معاينة التسوية المحاسبية" : "Aperçu du rapprochement comptable"}</h2></div>
        <p className="mt-1 text-sm text-stone-500">{ar ? "الموسم" : "Saison"}: {data.active_season} · {ar ? "رمز" : "Code"}: {data.season_code} · {ar ? "حد العرض لكل مصدر" : "Limite par source"}: {data.limit_per_source}</p>
      </div>
      <button type="button" onClick={() => void refetch()} disabled={isFetching} className="inline-flex items-center gap-2 rounded-lg border bg-white px-3 py-2 text-sm font-medium text-stone-700 disabled:opacity-50"><RefreshCw className={`size-4 ${isFetching ? "animate-spin" : ""}`} />{ar ? "تحديث" : "Actualiser"}</button>
    </div>

    <div className="flex items-start gap-3 rounded-xl border border-sky-200 bg-sky-50 p-4 text-sky-950">
      <ShieldAlert className="mt-0.5 size-5 shrink-0" />
      <div className="text-sm">
        <p className="font-semibold">{ar ? "وضع القراءة فقط — لا توجد قيود محاسبية مُرحّلة" : "Lecture seule — aucune écriture comptable n’est générée"}</p>
        <p className="mt-1 opacity-80">{ar ? "هذه النتائج مرشّحات للمراجعة وليست قيوداً مؤكدة. لن يتم تعديل البيانات أو الأرصدة." : "Les éléments sont des candidats à examiner, pas des écritures validées. Aucune donnée ni aucun solde n’est modifié."}</p>
      </div>
    </div>

    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Metric title={ar ? "إجمالي المرشّحات" : "Événements candidats"} value={data.summary.candidate_event_count} detail={ar ? "من مستندات المصدر" : "Depuis les pièces sources"} tone="slate" />
      <Metric title={ar ? "جاهز للمراجعة" : "À examiner"} value={eligible} detail={ar ? "ليس ترحيلاً تلقائياً" : "Aucun transfert automatique"} tone="green" />
      <Metric title={ar ? "محجوب" : "Bloqué"} value={blocked} detail={ar ? "يتطلب معالجة السبب" : "Blocage à résoudre"} tone="red" />
      <Metric title={ar ? "غير محسوم / يحتاج توضيحاً" : "Non résolu"} value={unresolved} detail={ar ? "بيانات قديمة أو أدلة ناقصة" : "Données historiques ou preuves manquantes"} tone="amber" />
    </div>

    <Card>
      <CardHeader><CardTitle className="text-base">{ar ? "العمليات المرشّحة" : "Événements candidats"}</CardTitle><CardDescription>{ar ? "كل سطر مرتبط بمستند مصدر؛ الحالات غير المحسومة لا تُعامل كقيود." : "Chaque ligne reste liée à sa pièce source; les éléments non résolus ne sont pas considérés comme des écritures."}</CardDescription></CardHeader>
      <CardContent>
        {data.candidate_events.length === 0 ? <p className="rounded-lg bg-stone-50 p-4 text-sm text-stone-500">{ar ? "لا توجد عمليات في النطاق المعروض." : "Aucun événement dans le périmètre affiché."}</p> :
        <div className="overflow-x-auto"><table className="w-full min-w-[850px] text-sm">
          <thead><tr className="border-b text-left text-xs text-stone-500">
            <th className="px-3 py-2">{ar ? "التاريخ" : "Date"}</th><th className="px-3 py-2">{ar ? "المصدر" : "Source"}</th><th className="px-3 py-2">{ar ? "الوثيقة" : "Document"}</th><th className="px-3 py-2">{ar ? "العملية" : "Événement"}</th><th className="px-3 py-2">{ar ? "المبلغ" : "Montant"}</th><th className="px-3 py-2">{ar ? "الحالة" : "Éligibilité"}</th><th className="px-3 py-2">{ar ? "التنبيهات" : "Alertes"}</th>
          </tr></thead>
          <tbody>{data.candidate_events.map((row, index) => <tr key={`${row.candidate_key}-${index}`} className="border-b last:border-0 align-top">
            <td className="px-3 py-3 whitespace-nowrap">{row.business_date || "—"}</td>
            <td className="px-3 py-3">{sourceName(row.source_type)}</td>
            <td className="px-3 py-3 font-mono text-xs">{row.source_document_number || row.source_id || "—"}</td>
            <td className="px-3 py-3">{row.event_type}</td>
            <td className="px-3 py-3 tabular-nums whitespace-nowrap">{amountText(row)}</td>
            <td className="px-3 py-3"><span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${row.eligibility === "ELIGIBLE_FOR_REVIEW" ? "bg-emerald-100 text-emerald-800" : row.eligibility === "BLOCKED" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-900"}`}>{eligibilityText(row.eligibility, ar)}</span></td>
            <td className="px-3 py-3 text-xs text-stone-600">{[...(row.blocking_reasons || []), ...(row.warnings || [])].map(reasonName).join(" · ") || "—"}</td>
          </tr>)}</tbody>
        </table></div>}
      </CardContent>
    </Card>

    <Card>
      <CardHeader><CardTitle className="text-base">{ar ? "العناصر غير المحسومة" : "Éléments non résolus"}</CardTitle><CardDescription>{ar ? "تحتاج إلى مطابقة أو قرار محاسبي قبل أي اعتماد." : "À rapprocher ou à arbitrer avant toute validation comptable."}</CardDescription></CardHeader>
      <CardContent>
        {data.unresolved_items.length === 0 ? <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-4 text-sm text-emerald-800"><CheckCircle2 className="size-4" />{ar ? "لا توجد عناصر غير محسومة ضمن النطاق الحالي." : "Aucun élément non résolu dans le périmètre actuel."}</div> :
        <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-sm">
          <thead><tr className="border-b text-left text-xs text-stone-500"><th className="px-3 py-2">{ar ? "المصدر" : "Source"}</th><th className="px-3 py-2">{ar ? "معرّف المصدر" : "ID source"}</th><th className="px-3 py-2">{ar ? "سبب عدم الحسم" : "Motif"}</th><th className="px-3 py-2">{ar ? "العدد" : "Nombre"}</th></tr></thead>
          <tbody>{data.unresolved_items.map((row, index) => <tr key={`${row.source_type}-${row.source_id}-${row.reason}-${index}`} className="border-b last:border-0"><td className="px-3 py-2">{sourceName(row.source_type || "—")}</td><td className="px-3 py-2 font-mono text-xs">{row.source_id || row.candidate_key || "—"}</td><td className="px-3 py-2 text-xs">{reasonName(row.reason)}</td><td className="px-3 py-2 tabular-nums">{row.observed_count ?? 1}</td></tr>)}</tbody>
        </table></div>}
      </CardContent>
    </Card>

    {more.length > 0 && <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><AlertTriangle className="mt-0.5 size-4 shrink-0" /><span>{ar ? `توجد سجلات إضافية خارج حد العرض الحالي (200 لكل مصدر): ${more.join("، ")}. هذه المعاينة ليست كاملة بعد.` : `Des éléments supplémentaires existent au-delà de la limite de 200 par source : ${more.join(", ")}. Cet aperçu est partiel.`}</span></div>}
  </div>;
}
