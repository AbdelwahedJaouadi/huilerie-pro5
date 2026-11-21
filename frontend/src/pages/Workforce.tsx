import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Clock3, LogIn, LogOut, Pencil, Printer, UserX } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { PageHeader } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

type Worker = { id: string; full_name: string; username: string; active?: boolean };
type Attendance = {
  id: string; worker_id: string; worker_name: string; day: string;
  status: "PRESENT" | "ABSENT"; check_in_at: string | null; check_out_at: string | null;
  marked_absent_at?: string | null;
};
type AttendanceResponse = { day: string | null; start_date: string; end_date: string; workers: Worker[]; records: Attendance[]; open_shifts: Attendance[] };
type Action = "check-in" | "check-out" | "mark-absent";
type Summary = { key: string; minutes: number; shifts: number };

function tunisParts(value: Date) {
  return Object.fromEntries(new Intl.DateTimeFormat("en-GB", {
    timeZone: "Africa/Tunis", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
  }).formatToParts(value).filter((part) => part.type !== "literal").map((part) => [part.type, part.value]));
}
function localDay() {
  const parts = tunisParts(new Date());
  return `${parts.year}-${parts.month}-${parts.day}`;
}
function firstDayOfMonth(day: string) { return `${day.slice(0, 7)}-01`; }
function localDateTime(value: string | null | undefined) {
  if (!value) return "";
  const parts = tunisParts(new Date(value));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}
function tunisInputToIso(value: string) {
  const [datePart, timePart] = value.split("T");
  const [year, month, day] = datePart.split("-").map(Number);
  const [hour, minute] = timePart.split(":").map(Number);
  const guess = Date.UTC(year, month - 1, day, hour, minute);
  const atGuess = tunisParts(new Date(guess));
  const tunisAsUtc = Date.UTC(Number(atGuess.year), Number(atGuess.month) - 1, Number(atGuess.day), Number(atGuess.hour), Number(atGuess.minute), Number(atGuess.second));
  return new Date(guess - (tunisAsUtc - guess)).toISOString();
}
function displayTime(value: string | null | undefined, locale: string) {
  return value ? new Date(value).toLocaleTimeString(locale, { timeZone: "Africa/Tunis", hour: "2-digit", minute: "2-digit" }) : "—";
}
function workedMinutes(record: Attendance): number {
  if (record.status !== "PRESENT" || !record.check_in_at || !record.check_out_at) return 0;
  const elapsed = new Date(record.check_out_at).getTime() - new Date(record.check_in_at).getTime();
  // Invalid, reversed, or over-24-hour shifts are excluded pending manager review.
  if (!Number.isFinite(elapsed) || elapsed <= 0 || elapsed > 24 * 60 * 60 * 1000) return 0;
  return Math.floor(elapsed / 60000);
}
function weekStart(day: string) {
  const date = new Date(`${day}T00:00:00Z`);
  const offset = (date.getUTCDay() + 6) % 7;
  date.setUTCDate(date.getUTCDate() - offset);
  return date.toISOString().slice(0, 10);
}
function durationLabel(minutes: number) {
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}`;
}
function summarize(records: Attendance[], period: (record: Attendance) => string): Summary[] {
  const grouped = new Map<string, Summary>();
  for (const record of records) {
    const minutes = workedMinutes(record);
    if (!minutes) continue;
    const key = period(record);
    const item = grouped.get(key) ?? { key, minutes: 0, shifts: 0 };
    item.minutes += minutes;
    item.shifts += 1;
    grouped.set(key, item);
  }
  return [...grouped.values()].sort((a, b) => a.key.localeCompare(b.key));
}


function escapeReportHtml(value: string) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#39;");
}

function printWorkforceReport({
  records, workers, startDate, endDate, ar, locale,
}: {
  records: Attendance[];
  workers: Worker[];
  startDate: string;
  endDate: string;
  ar: boolean;
  locale: string;
}) {
  const printWindow = window.open("", "_blank");
  if (!printWindow) return false;

  const text = ar ? {
    title: "تقرير الحضور والانصراف", subtitle: "Oro Verde — جدول العمال",
    period: "الفترة", employee: "العامل", all: "جميع العمال",
    summary: "ملخص ساعات العمل حسب العامل", details: "تفاصيل الحضور والانصراف",
    name: "اسم العامل", shifts: "الورديات المكتملة", hours: "مجموع ساعات العمل",
    open: "ورديات مفتوحة", absent: "غياب مؤكد", noRecords: "لا توجد سجلات",
    date: "التاريخ", status: "الحالة", arrival: "الحضور", departure: "الانصراف",
    duration: "المدة", complete: "مكتمل", openStatus: "وردية مفتوحة — غير محسوبة",
    absentStatus: "غياب مؤكد", review: "تتطلب مراجعة", noData: "لا توجد سجلات في الفترة المختارة",
    note: "لا يتم خصم الاستراحة. الورديات المفتوحة لا تدخل في مجموع الساعات. عدم وجود سجل لا يعني الغياب.",
    total: "الإجمالي العام", generated: "تاريخ استخراج التقرير",
  } : {
    title: "Rapport du personnel et du pointage", subtitle: "Oro Verde — Tableau des employés",
    period: "Période", employee: "Employé", all: "Tous les employés",
    summary: "Synthèse des heures par employé", details: "Détail des arrivées et départs",
    name: "Nom de l’employé", shifts: "Quarts terminés", hours: "Total des heures",
    open: "Quarts ouverts", absent: "Absences confirmées", noRecords: "Aucun pointage",
    date: "Date", status: "Statut", arrival: "Arrivée", departure: "Départ",
    duration: "Durée", complete: "Terminé", openStatus: "Quart ouvert — exclu",
    absentStatus: "Absent confirmé", review: "À vérifier", noData: "Aucun pointage sur la période sélectionnée",
    note: "Aucune pause n’est déduite. Les quarts ouverts sont exclus du total. L’absence d’un pointage ne signifie pas une absence.",
    total: "Total général", generated: "Rapport généré le",
  };
  const selectedName = workers.length === 1 ? workers[0].full_name : text.all;
  const sortedRecords = [...records].sort((a, b) =>
    a.day.localeCompare(b.day) || a.worker_name.localeCompare(b.worker_name, locale)
  );
  const stats = workers.map((worker) => {
    const rows = records.filter((record) => record.worker_id === worker.id);
    const minutes = rows.reduce((sum, record) => sum + workedMinutes(record), 0);
    return {
      name: worker.full_name, minutes,
      complete: rows.filter((record) => workedMinutes(record) > 0).length,
      open: rows.filter((record) => record.status === "PRESENT" && !!record.check_in_at && !record.check_out_at).length,
      absent: rows.filter((record) => record.status === "ABSENT").length,
      count: rows.length,
    };
  });
  const totalMinutes = records.reduce((sum, record) => sum + workedMinutes(record), 0);
  const totalComplete = records.filter((record) => workedMinutes(record) > 0).length;
  const totalOpen = records.filter((record) => record.status === "PRESENT" && !!record.check_in_at && !record.check_out_at).length;
  const totalAbsent = records.filter((record) => record.status === "ABSENT").length;
  const dayLabel = (day: string) => new Date(day + "T12:00:00").toLocaleDateString(locale, {
    timeZone: "Africa/Tunis", year: "numeric", month: "2-digit", day: "2-digit",
  });
  const summaryRows = stats.map((item) => `
    <tr><td class="employee">${escapeReportHtml(item.name)}</td>
    <td class="num">${item.count ? item.complete : text.noRecords}</td>
    <td class="num strong">${durationLabel(item.minutes)}</td>
    <td class="num">${item.open}</td><td class="num">${item.absent}</td></tr>`
  ).join("");
  const detailRows = sortedRecords.map((record) => {
    const minutes = workedMinutes(record);
    const isOpen = record.status === "PRESENT" && !!record.check_in_at && !record.check_out_at;
    const isInvalid = record.status === "PRESENT" && !!record.check_in_at && !!record.check_out_at && minutes === 0;
    const status = record.status === "ABSENT" ? text.absentStatus : isOpen ? text.openStatus : isInvalid ? text.review : text.complete;
    const statusClass = record.status === "ABSENT" ? "absent" : isOpen ? "open" : isInvalid ? "review" : "complete";
    return `<tr><td class="date">${dayLabel(record.day)}</td>
      <td class="employee">${escapeReportHtml(record.worker_name)}</td>
      <td><span class="status ${statusClass}">${status}</span></td>
      <td class="time">${displayTime(record.check_in_at, locale)}</td>
      <td class="time">${displayTime(record.check_out_at, locale)}</td>
      <td class="num strong">${minutes ? durationLabel(minutes) : "—"}</td></tr>`;
  }).join("");
  const generatedAt = new Date().toLocaleString(locale, { timeZone: "Africa/Tunis", dateStyle: "medium", timeStyle: "short" });
  const direction = ar ? "rtl" : "ltr";
  const html = `<!doctype html><html lang="${ar ? "ar" : "fr"}" dir="${direction}"><head><meta charset="utf-8">
    <title>${text.title} — ${startDate} — ${endDate}</title>
    <style>
      @page { size: A4 landscape; margin: 13mm 12mm 15mm; }
      * { box-sizing: border-box; }
      body { margin: 0; color: #1f2937; font-family: Tahoma, Arial, sans-serif; font-size: 10px; direction: ${direction}; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      .top { display:flex; align-items:center; justify-content:space-between; border-bottom:3px solid #647a3b; padding:0 0 12px; margin-bottom:13px; }
      .brand { color:#34451f; font-size:19px; font-weight:800; letter-spacing:.4px; }
      .eyebrow { color:#75805f; font-size:9px; margin-top:3px; }
      h1 { margin:0; color:#18251b; font-size:19px; font-weight:800; }
      .subtitle { color:#64748b; margin-top:4px; font-size:10px; }
      .meta { display:flex; gap:24px; margin:12px 0; padding:10px 13px; background:#f3f5ef; border:1px solid #e1e7d7; border-radius:7px; }
      .meta-label { color:#64748b; font-size:8px; margin-bottom:4px; }
      .meta-value { color:#25351d; font-size:11px; font-weight:700; }
      h2 { font-size:12px; color:#34451f; margin:15px 0 7px; }
      table { width:100%; border-collapse:collapse; table-layout:fixed; }
      thead { display:table-header-group; }
      tr { break-inside:avoid; page-break-inside:avoid; }
      th { background:#34451f; color:white; padding:8px 7px; text-align:start; font-size:9px; font-weight:700; }
      td { border-bottom:1px solid #e5e7eb; padding:7px; vertical-align:middle; }
      tbody tr:nth-child(even) { background:#f8faf7; }
      .employee { font-weight:700; }
      .num { text-align:center; font-variant-numeric:tabular-nums; }
      .strong { color:#34451f; font-weight:800; }
      .date,.time { direction:ltr; unicode-bidi:embed; text-align:start; font-variant-numeric:tabular-nums; }
      .status { display:inline-block; border-radius:12px; padding:3px 7px; font-size:8px; font-weight:700; white-space:nowrap; }
      .complete { background:#e5f3e9; color:#24623b; }
      .open { background:#fff1d6; color:#8a5700; }
      .absent { background:#fde8e8; color:#a12b2b; }
      .review { background:#ffedd5; color:#9a3412; }
      .totals { margin-top:8px; display:flex; justify-content:flex-end; gap:20px; padding:9px 12px; background:#f3f5ef; border:1px solid #e1e7d7; font-size:9px; }
      .note { margin-top:13px; padding:8px 10px; background:#fff9e9; border-inline-start:3px solid #c49a3a; color:#6b5728; font-size:8px; line-height:1.6; }
      .footer { display:flex; justify-content:space-between; margin-top:12px; padding-top:7px; border-top:1px solid #d9ded2; color:#7b8490; font-size:8px; }
      @media screen { body { padding:18px; max-width:1100px; margin:auto; } }
    </style></head><body>
      <header class="top"><div><div class="brand">ORO VERDE</div><div class="eyebrow">HUILERIE • GESTION DU PERSONNEL</div></div>
      <div style="text-align:${ar ? "left" : "right"}"><h1>${text.title}</h1><div class="subtitle">${text.subtitle}</div></div></header>
      <section class="meta"><div><div class="meta-label">${text.period}</div><div class="meta-value" dir="ltr">${startDate} — ${endDate}</div></div>
      <div><div class="meta-label">${text.employee}</div><div class="meta-value">${escapeReportHtml(selectedName)}</div></div></section>
      <h2>${text.summary}</h2>
      <table><thead><tr><th style="width:34%">${text.name}</th><th>${text.shifts}</th><th>${text.hours}</th><th>${text.open}</th><th>${text.absent}</th></tr></thead>
      <tbody>${summaryRows || `<tr><td colspan="5" style="text-align:center;padding:15px">${text.noData}</td></tr>`}</tbody></table>
      <div class="totals"><span>${text.total}</span><strong>${durationLabel(totalMinutes)}</strong><span>${text.shifts}: ${totalComplete}</span><span>${text.open}: ${totalOpen}</span><span>${text.absent}: ${totalAbsent}</span></div>
      <h2>${text.details}</h2>
      <table><thead><tr><th style="width:14%">${text.date}</th><th style="width:22%">${text.name}</th><th style="width:22%">${text.status}</th><th style="width:14%">${text.arrival}</th><th style="width:14%">${text.departure}</th><th style="width:14%">${text.duration}</th></tr></thead>
      <tbody>${detailRows || `<tr><td colspan="6" style="text-align:center;padding:18px">${text.noData}</td></tr>`}</tbody></table>
      <div class="note">${text.note}</div>
      <footer class="footer"><span>ORO VERDE</span><span>${text.generated}: ${generatedAt}</span></footer>
      <script>window.addEventListener("load", function(){ setTimeout(function(){ window.focus(); window.print(); }, 350); });</script>
    </body></html>`;
  printWindow.document.open();
  printWindow.document.write(html);
  printWindow.document.close();
  return true;
}

export default function Workforce() {
  const { lang, errMsg } = useI18n();
  const ar = lang === "ar";
  const locale = ar ? "ar-TN" : "fr-FR";
  const qc = useQueryClient();
  const today = localDay();
  const [startDate, setStartDate] = useState(firstDayOfMonth(today));
  const [endDate, setEndDate] = useState(today);
  const [selectedWorkerId, setSelectedWorkerId] = useState("all");
  const [editing, setEditing] = useState<Attendance | null>(null);
  const [editIn, setEditIn] = useState("");
  const [editOut, setEditOut] = useState("");
  const [reason, setReason] = useState("");
  const [editStatus, setEditStatus] = useState<"PRESENT" | "ABSENT">("PRESENT");
  const validRange = !!startDate && !!endDate && startDate <= endDate;
  const queryKey = ["workforce", "attendance", startDate, endDate];
  const data = useQuery({
    queryKey,
    enabled: validRange,
    queryFn: () => apiGet<AttendanceResponse>(`/workforce/attendance?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`),
  });
  const action = useMutation({
    mutationFn: ({ type, worker_id }: { type: Action; worker_id: string }) =>
      apiPost<Attendance>(`/workforce/attendance/${type}`, { worker_id, day: today }),
    onSuccess: async () => {
      toast.success(ar ? "تم تحديث سجل العامل" : "Pointage mis à jour");
      await qc.invalidateQueries({ queryKey: ["workforce", "attendance"] });
    },
    onError: (error) => toast.error(errMsg(error)),
  });
  const correction = useMutation({
    mutationFn: () => {
      if (!editing) throw new Error("attendance_not_selected");
      return apiPatch<Attendance>(`/workforce/attendance/${editing.id}`, {
        check_in_at: editStatus === "PRESENT" && editIn ? tunisInputToIso(editIn) : null,
        check_out_at: editStatus === "PRESENT" && editOut ? tunisInputToIso(editOut) : null,
        status: editStatus,
        reason: reason.trim(),
      });
    },
    onSuccess: async () => {
      toast.success(ar ? "تم تصحيح السجل وحفظ أثر التعديل" : "Pointage corrigé; la modification est journalisée");
      setEditing(null); setReason("");
      await qc.invalidateQueries({ queryKey: ["workforce", "attendance"] });
    },
    onError: (error) => toast.error(errMsg(error)),
  });
  const allRecords = data.data?.records ?? [];
  const workers = data.data?.workers ?? [];
  const records = useMemo(
    () => selectedWorkerId === "all" ? allRecords : allRecords.filter((record) => record.worker_id === selectedWorkerId),
    [allRecords, selectedWorkerId],
  );
  const visibleWorkers = useMemo(
    () => selectedWorkerId === "all" ? workers : workers.filter((worker) => worker.id === selectedWorkerId),
    [workers, selectedWorkerId],
  );
  const recordsToday = useMemo(() => new Map(records.filter((record) => record.day === today).map((record) => [record.worker_id, record])), [records, today]);
  const openShiftsByWorker = useMemo(
    () => new Map((data.data?.open_shifts ?? []).map((record) => [record.worker_id, record])),
    [data.data?.open_shifts],
  );
  const daily = useMemo(() => summarize(records, (record) => record.day), [records]);
  const weekly = useMemo(() => summarize(records, (record) => weekStart(record.day)), [records]);
  const monthly = useMemo(() => summarize(records, (record) => record.day.slice(0, 7)), [records]);
  const totals = useMemo(() => {
    let minutes = 0, closed = 0, open = 0, absent = 0;
    for (const record of records) {
      const value = workedMinutes(record);
      minutes += value;
      if (record.status === "ABSENT") absent++;
      else if (record.check_in_at && !record.check_out_at) open++;
      else if (value > 0) closed++;
    }
    return { minutes, closed, open, absent };
  }, [records]);


  const handlePrintReport = () => {
    const opened = printWorkforceReport({
      records, workers: visibleWorkers, startDate, endDate, ar, locale,
    });
    if (!opened) toast.error(ar ? "يرجى السماح بفتح النافذة المنبثقة لطباعة التقرير." : "Autorisez les fenêtres contextuelles pour imprimer le rapport.");
  };

  const beginEdit = (record: Attendance) => {
    setEditing(record);
    setEditIn(localDateTime(record.check_in_at));
    setEditOut(localDateTime(record.check_out_at));
    setReason("");
    setEditStatus(record.status);
  };
  const renderSummary = (title: string, rows: Summary[]) => (
    <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 font-semibold text-stone-900">{title}</h3>
      {rows.length === 0 ? <p className="text-sm text-stone-500">{ar ? "لا توجد ورديات مكتملة ضمن هذه الفترة." : "Aucun quart terminé sur cette période."}</p> :
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead><tr className="border-b bg-stone-50 text-stone-600"><th className="px-3 py-2 text-start">{ar ? "الفترة" : "Période"}</th><th className="px-3 py-2 text-end">{ar ? "الورديات المكتملة" : "Quarts terminés"}</th><th className="px-3 py-2 text-end">{ar ? "مجموع الساعات" : "Total travaillé"}</th></tr></thead>
          <tbody>{rows.map((row) => <tr key={row.key} className="border-b last:border-0"><td className="px-3 py-2 font-medium" dir="ltr">{row.key}{title === (ar ? "المجموع الأسبوعي (الاثنين إلى الأحد)" : "Totaux hebdomadaires (lundi au dimanche)") ? ` → ${new Date(new Date(row.key + "T00:00:00Z").getTime() + 6 * 86400000).toISOString().slice(0, 10)}` : ""}</td><td className="px-3 py-2 text-end tabular-nums">{row.shifts}</td><td className="px-3 py-2 text-end font-semibold tabular-nums">{durationLabel(row.minutes)}</td></tr>)}</tbody>
        </table></div>}
    </section>
  );

  return (
    <div className="space-y-5" dir={ar ? "rtl" : "ltr"} data-testid="workforce-page">
      <PageHeader title={ar ? "جدول العمال والحضور" : "Personnel et pointage"} sub={ar ? "السجلات التاريخية وحساب ساعات العمل" : "Historique du pointage et calcul des heures travaillées"} accent="bg-indigo-600" />
      <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="mb-4 flex flex-wrap items-end gap-4">
          <div className="space-y-1"><Label htmlFor="workforce-start">{ar ? "من تاريخ" : "Du"}</Label><div className="flex items-center gap-2"><CalendarDays className="size-4 text-stone-500" /><Input id="workforce-start" data-testid="workforce-start-date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} className="w-auto" /></div></div>
          <div className="space-y-1"><Label htmlFor="workforce-end">{ar ? "إلى تاريخ" : "Au"}</Label><Input id="workforce-end" data-testid="workforce-end-date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} className="w-auto" /></div>
          <div className="space-y-1"><Label htmlFor="workforce-worker">{ar ? "العامل" : "Employé"}</Label><select id="workforce-worker" data-testid="workforce-worker-filter" value={selectedWorkerId} onChange={(event) => setSelectedWorkerId(event.target.value)} className="h-10 min-w-48 rounded-md border border-stone-300 bg-white px-3 text-sm"><option value="all">{ar ? "الكل" : "Tous les employés"}</option>{workers.map((worker) => <option key={worker.id} value={worker.id}>{worker.full_name}</option>)}</select></div>
          {!validRange && <p className="text-sm text-red-700">{ar ? "تاريخ البداية يجب أن يسبق تاريخ النهاية أو يساويه." : "La date de début doit précéder ou égaler la date de fin."}</p>}
          <Button type="button" variant="outline" disabled={!validRange || data.isLoading || data.isError} onClick={handlePrintReport} className="gap-2"><Printer className="size-4" />{ar ? "استخراج PDF / طباعة" : "Exporter PDF / Imprimer"}</Button>
          <div className="ms-auto text-sm text-stone-500">{ar ? "كل الأوقات بتوقيت تونس. لا يتم خصم الاستراحة." : "Heure de Tunisie. Aucune pause n’est déduite."}</div>
        </div>
      </section>
      {data.isLoading ? <p className="py-8 text-center text-sm text-stone-500">{ar ? "جارٍ تحميل السجلات..." : "Chargement des pointages…"}</p> :
       data.isError ? <p className="py-8 text-center text-sm text-red-700">{ar ? "تعذر تحميل سجلات العمال." : "Impossible de charger les pointages."}</p> : <>
        <section className="grid gap-3 sm:grid-cols-4">
          {[
            { label: ar ? "إجمالي ساعات العمل" : "Total des heures", value: durationLabel(totals.minutes), tone: "bg-indigo-50 text-indigo-800" },
            { label: ar ? "ورديات مكتملة" : "Quarts terminés", value: totals.closed, tone: "bg-emerald-50 text-emerald-800" },
            { label: ar ? "ورديات مفتوحة (غير محسوبة)" : "Quarts ouverts (exclus)", value: totals.open, tone: "bg-amber-50 text-amber-800" },
            { label: ar ? "غياب مسجل يدوياً" : "Absences confirmées", value: totals.absent, tone: "bg-rose-50 text-rose-800" },
          ].map((item) => <div key={item.label} className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm"><div className="text-sm text-stone-600">{item.label}</div><div className={`mt-2 inline-flex rounded-lg px-3 py-1 text-2xl font-bold tabular-nums ${item.tone}`}>{item.value}</div></div>)}
        </section>
        <div className="grid gap-4 xl:grid-cols-3">
          {renderSummary(ar ? "المجموع اليومي" : "Totaux journaliers", daily)}
          {renderSummary(ar ? "المجموع الأسبوعي (الاثنين إلى الأحد)" : "Totaux hebdomadaires (lundi au dimanche)", weekly)}
          {renderSummary(ar ? "المجموع الشهري" : "Totaux mensuels", monthly)}
        </div>
        <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 font-semibold text-stone-900">{ar ? "سجلات الحضور والانصراف للفترة" : "Historique des arrivées et départs"}</h3>
          {records.length === 0 ? <p className="py-8 text-center text-sm text-stone-500">{ar ? "لا توجد سجلات في الفترة المختارة. عدم وجود سجل لا يعني الغياب." : "Aucun pointage sur la période. L’absence d’un enregistrement ne signifie pas une absence confirmée."}</p> :
          <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-sm">
            <thead><tr className="border-b bg-stone-50 text-stone-600"><th className="px-3 py-3 text-start">{ar ? "التاريخ" : "Date"}</th><th className="px-3 py-3 text-start">{ar ? "العامل" : "Employé"}</th><th className="px-3 py-3 text-start">{ar ? "الحالة" : "Statut"}</th><th className="px-3 py-3 text-start">{ar ? "الحضور" : "Arrivée"}</th><th className="px-3 py-3 text-start">{ar ? "الانصراف" : "Départ"}</th><th className="px-3 py-3 text-end">{ar ? "المدة" : "Durée"}</th><th className="px-3 py-3 text-end">{ar ? "إجراء" : "Action"}</th></tr></thead>
            <tbody>{records.map((record) => {
              const minutes = workedMinutes(record);
              const open = record.status === "PRESENT" && !!record.check_in_at && !record.check_out_at;
              const invalid = record.status === "PRESENT" && !!record.check_in_at && !!record.check_out_at && minutes === 0;
              return <tr key={record.id} className="border-b last:border-0">
                <td className="px-3 py-3 font-mono" dir="ltr">{record.day}</td><td className="px-3 py-3 font-semibold">{record.worker_name}</td>
                <td className="px-3 py-3"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${record.status === "ABSENT" ? "bg-rose-100 text-rose-800" : open ? "bg-amber-100 text-amber-800" : invalid ? "bg-orange-100 text-orange-800" : "bg-emerald-100 text-emerald-800"}`}>{record.status === "ABSENT" ? (ar ? "غياب مؤكد" : "Absent confirmé") : open ? (ar ? "وردية مفتوحة" : "Quart ouvert") : invalid ? (ar ? "تتطلب مراجعة" : "À vérifier") : (ar ? "مكتمل" : "Terminé")}</span></td>
                <td className="px-3 py-3 font-mono">{displayTime(record.check_in_at, locale)}</td><td className="px-3 py-3 font-mono">{displayTime(record.check_out_at, locale)}</td>
                <td className="px-3 py-3 text-end font-semibold tabular-nums">{minutes ? durationLabel(minutes) : "—"}</td>
                <td className="px-3 py-3 text-end"><Button size="sm" variant="outline" onClick={() => beginEdit(record)}><Pencil className="me-1 size-4" />{ar ? "تصحيح" : "Corriger"}</Button></td>
              </tr>;
            })}</tbody>
          </table></div>}
        </section>
        {startDate <= today && endDate >= today && <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 font-semibold text-stone-900">{ar ? "تسجيل حضور اليوم" : "Pointage du jour"} <span className="text-sm font-normal text-stone-500" dir="ltr">{today}</span></h3>
          <div className="overflow-x-auto"><table className="w-full min-w-[680px] text-sm">
            <thead><tr className="border-b bg-stone-50 text-stone-600"><th className="px-3 py-3 text-start">{ar ? "العامل" : "Employé"}</th><th className="px-3 py-3 text-start">{ar ? "الحالة" : "Statut"}</th><th className="px-3 py-3 text-start">{ar ? "الحضور" : "Arrivée"}</th><th className="px-3 py-3 text-start">{ar ? "الانصراف" : "Départ"}</th><th className="px-3 py-3 text-end">{ar ? "الإجراءات" : "Actions"}</th></tr></thead>
            <tbody>{visibleWorkers.map((worker) => {
              // Include an overnight shift whose check-in date is outside the selected range.
              const record = recordsToday.get(worker.id) ?? openShiftsByWorker.get(worker.id);
              const checkedIn = record?.status === "PRESENT" && !!record.check_in_at;
              const checkedOut = !!record?.check_out_at;
              return <tr key={worker.id} className="border-b last:border-0"><td className="px-3 py-3"><div className="font-semibold">{record?.worker_name || worker.full_name}</div><div className="text-xs text-stone-500">{worker.username}</div>{record && record.day !== today && <div className="text-xs text-amber-700">{ar ? `بدأت الوردية في ${record.day}` : `Quart commencé le ${record.day}`}</div>}</td>
                <td className="px-3 py-3">{record?.status === "ABSENT" ? (ar ? "غياب مؤكد" : "Absent confirmé") : checkedOut ? (ar ? "انصرف" : "Parti") : checkedIn ? (ar ? "حاضر" : "Présent") : (ar ? "لم يسجل — ليس غياباً" : "Non pointé — pas une absence")}</td>
                <td className="px-3 py-3 font-mono">{displayTime(record?.check_in_at, locale)}</td><td className="px-3 py-3 font-mono">{displayTime(record?.check_out_at, locale)}</td>
                <td className="px-3 py-3"><div className="flex justify-end gap-2">
                  {worker.active !== false && !checkedIn && !checkedOut && <Button size="sm" disabled={action.isPending} onClick={() => action.mutate({ type: "check-in", worker_id: worker.id })} className="bg-emerald-700 hover:bg-emerald-800"><LogIn className="me-1 size-4" />{ar ? "حضور" : "Arrivée"}</Button>}
                  {checkedIn && !checkedOut && <Button size="sm" disabled={action.isPending} onClick={() => action.mutate({ type: "check-out", worker_id: worker.id })} className="bg-indigo-700 hover:bg-indigo-800"><LogOut className="me-1 size-4" />{ar ? "انصراف" : "Départ"}</Button>}
                  {worker.active !== false && !record && <Button size="sm" variant="outline" disabled={action.isPending} onClick={() => { if (window.confirm(ar ? "تأكيد تسجيل غياب هذا العامل؟" : "Confirmer l’absence de cet employé ?")) action.mutate({ type: "mark-absent", worker_id: worker.id }); }} className="border-rose-200 text-rose-700 hover:bg-rose-50"><UserX className="me-1 size-4" />{ar ? "غياب" : "Absent"}</Button>}
                  {record && <Button size="sm" variant="outline" onClick={() => beginEdit(record)}><Pencil className="me-1 size-4" />{ar ? "تصحيح" : "Corriger"}</Button>}
                </div></td></tr>;
            })}</tbody>
          </table></div>
        </section>}
      </>}
      <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950"><Clock3 className="mt-0.5 size-4 shrink-0" /><p>{ar ? "الحساب لا يخصم الاستراحة. الوردية المفتوحة لا تدخل في المجموع، والوردية التي تتجاوز 24 ساعة أو بياناتها غير صحيحة تستوجب مراجعة المدير. لا يُسجل الغياب إلا بتأكيد يدوي." : "Aucune pause n’est déduite. Les quarts ouverts sont exclus du total. Un quart de plus de 24 heures ou des heures incohérentes nécessite une vérification. Une absence doit être confirmée manuellement."}</p></div>
      <Dialog open={!!editing} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent data-testid="workforce-correction-dialog">
          <DialogHeader><DialogTitle>{ar ? "تصحيح سجل الحضور" : "Corriger le pointage"} — {editing?.worker_name}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1"><Label>{ar ? "الحالة" : "Statut"}</Label><select value={editStatus} onChange={(event) => { const value = event.target.value as "PRESENT" | "ABSENT"; setEditStatus(value); if (value === "ABSENT") { setEditIn(""); setEditOut(""); } }} className="h-10 w-full rounded-md border border-stone-300 bg-white px-3 text-sm"><option value="PRESENT">{ar ? "حاضر" : "Présent"}</option><option value="ABSENT">{ar ? "غائب" : "Absent"}</option></select></div>
            <div className="space-y-1"><Label>{ar ? "وقت الحضور" : "Heure d’arrivée"}</Label><Input type="datetime-local" disabled={editStatus === "ABSENT"} value={editIn} onChange={(event) => setEditIn(event.target.value)} /></div>
            <div className="space-y-1"><Label>{ar ? "وقت الانصراف" : "Heure de départ"}</Label><Input type="datetime-local" disabled={editStatus === "ABSENT"} value={editOut} onChange={(event) => setEditOut(event.target.value)} /></div>
            <div className="space-y-1"><Label>{ar ? "سبب التصحيح (إجباري)" : "Motif de correction (obligatoire)"}</Label><Input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} placeholder={ar ? "مثال: تم إدخال وقت خاطئ" : "Ex. : heure saisie incorrectement"} /></div>
          </div>
          <DialogFooter><Button type="button" variant="outline" onClick={() => setEditing(null)}>{ar ? "إلغاء" : "Annuler"}</Button><Button type="button" disabled={reason.trim().length < 5 || correction.isPending} onClick={() => correction.mutate()} className="bg-indigo-700 hover:bg-indigo-800">{ar ? "حفظ التصحيح" : "Enregistrer la correction"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
