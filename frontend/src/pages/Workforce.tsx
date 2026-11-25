import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Clock3, LogIn, LogOut, Pencil, Printer, UserX, Timer, CheckCircle2, Hourglass, CalendarCheck2, CalendarRange, CalendarClock, Coffee } from "lucide-react";
import { toast } from "sonner";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { PageHeader } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

type Worker = { id: string; full_name: string; first_name?: string; last_name?: string; phone?: string; address?: string; salary_amount?: number | null; salary_type?: "monthly" | "daily" | "hourly"; active?: boolean; archived?: boolean };
type Attendance = {
  id: string; worker_id: string; worker_name: string; day: string;
  status: "PRESENT" | "ABSENT"; check_in_at: string | null; check_out_at: string | null;
  marked_absent_at?: string | null;
  breaks?: Array<{ start_at: string; end_at: string }>;
  break_started_at?: string | null;
};
type AttendanceResponse = { day: string | null; start_date: string; end_date: string; workers: Worker[]; records: Attendance[]; open_shifts: Attendance[] };
type EmployeeDraft = { first_name: string; last_name: string; phone: string; address: string; salary_amount: string; salary_type: "monthly" | "daily" | "hourly" };
type WorkersResponse = { workers: Worker[]; total: number };
type PayrollRow = { worker: Worker; period: string; worked_minutes: number; incomplete_shifts: number; montant_du_travail: string; total_paid: string; total_advances: string; reste_a_payer: string; supported: boolean; final_paid: boolean };
type PayrollResponse = { period: string; workers: PayrollRow[]; payments: Array<{ id: string; worker_name_snapshot: string; payment_kind: string; amount_tnd: string | number; payment_method: string; account_name_snapshot: string; paid_at: string }>; accounts: Array<{ id: string; name: string; account_type: "CASH" | "BANK" }> };
type Action = "check-in" | "check-out" | "break-start" | "break-end" | "mark-absent";
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
function lastDayOfMonth(day: string) { const [year, month] = day.slice(0, 7).split("-").map(Number); return new Date(Date.UTC(year, month, 0)).toISOString().slice(0, 10); }
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
function displayShiftRange(record: Attendance, locale: string) {
  const checkIn = record.check_in_at ? new Date(record.check_in_at) : null;
  const checkOut = record.check_out_at ? new Date(record.check_out_at) : null;
  if (!checkIn) return "—";
  const checkInDay = tunisParts(checkIn).year + "-" + tunisParts(checkIn).month + "-" + tunisParts(checkIn).day;
  const checkOutParts = checkOut ? tunisParts(checkOut) : null;
  const checkOutDay = checkOutParts ? checkOutParts.year + "-" + checkOutParts.month + "-" + checkOutParts.day : "";
  const nextDayLabel = checkOut && checkOutDay !== checkInDay
    ? new Intl.DateTimeFormat(locale, { timeZone: "Africa/Tunis", day: "2-digit", month: "2-digit" }).format(checkOut) + " "
    : "";
  return displayTime(record.check_in_at, locale) + " – " + (checkOut ? nextDayLabel + displayTime(record.check_out_at, locale) : "—");
}
function workedMinutes(record: Attendance): number {
  if (record.status !== "PRESENT" || !record.check_in_at || !record.check_out_at) return 0;
  const elapsed = new Date(record.check_out_at).getTime() - new Date(record.check_in_at).getTime();
  // Invalid, reversed, or over-24-hour shifts are excluded pending manager review.
  if (!Number.isFinite(elapsed) || elapsed <= 0 || elapsed > 24 * 60 * 60 * 1000) return 0;
  const recordedBreakMinutes = (record.breaks ?? []).reduce((total, interval) => {
    const start = new Date(interval.start_at).getTime();
    const end = new Date(interval.end_at).getTime();
    return Number.isFinite(start) && Number.isFinite(end) && end > start
      ? total + Math.floor((end - start) / 60000) : total;
  }, 0);
  return Math.max(0, Math.floor(elapsed / 60000) - recordedBreakMinutes);
}
function workedAmount(worker: Worker, record: Attendance): number | null {
  if (worker.salary_amount == null || !Number.isFinite(worker.salary_amount) || worker.salary_amount < 0) return null;
  if (worker.salary_type !== "daily" && worker.salary_type !== "hourly") return null;
  if (record.status === "ABSENT") return 0;
  const minutes = workedMinutes(record);
  if (minutes <= 0) return null;
  const amount = worker.salary_type === "daily"
    ? worker.salary_amount * (minutes / (8 * 60))
    : worker.salary_amount * (minutes / 60);
  return Math.round((amount + Number.EPSILON) * 1000) / 1000;
}
function formatWorkAmount(amount: number, locale: string): string {
  return `${new Intl.NumberFormat(locale, { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(amount)} TND`;
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
function printHtmlInHiddenFrame(html: string, ar: boolean) {
  // Open synchronously from the click handler so the browser does not block the new tab.
  const printWindow = window.open("", "_blank");
  if (!printWindow) return false;

  const toolbar = `
    <style>
      .print-toolbar{position:sticky;top:0;z-index:9999;display:flex;justify-content:center;gap:12px;padding:12px;background:#fff;border-bottom:1px solid #ddd;font-family:Arial,Tahoma,sans-serif}
      .print-toolbar button{border:0;border-radius:8px;padding:10px 22px;font-size:14px;font-weight:600;cursor:pointer}
      .print-action{background:#34451f;color:#fff}.close-action{background:#eee;color:#222}
      @media print{.print-toolbar{display:none!important}}
    </style>
    <div class="print-toolbar" dir="${ar ? "rtl" : "ltr"}">
      <button class="print-action" type="button" onclick="window.print()">${ar ? "طباعة / PDF" : "Imprimer / PDF"}</button>
      <button class="close-action" type="button" onclick="window.close()">${ar ? "إغلاق" : "Fermer"}</button>
    </div>`;
  const htmlEnd = html.toLowerCase().lastIndexOf("</html>");
  const printableHtml = htmlEnd >= 0 ? `${html.slice(0, htmlEnd)}${toolbar}${html.slice(htmlEnd)}` : `${html}${toolbar}`;

  try {
    printWindow.document.open();
    printWindow.document.write(printableHtml);
    printWindow.document.close();
    printWindow.focus();
    return true;
  } catch {
    printWindow.close();
    return false;
  }
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


function printEmployeeRegistry(workers: Worker[], ar: boolean) {
  const escape = (value: string) => value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const labels = ar
    ? ["سجل العمال", "الاسم واللقب", "الهاتف", "العنوان", "الأجر", "نوع الأجر", "الحالة", "نشط", "مؤرشف"]
    : ["Registre des employés", "Nom et prénom", "Téléphone", "Adresse", "Salaire", "Type", "Statut", "Actif", "Archivé"];
  const salaryType = (type?: string) => type === "hourly" ? (ar ? "بالساعة" : "Horaire") : type === "daily" ? (ar ? "باليوم" : "Journalier") : (ar ? "شهري" : "Mensuel");
  const rows = workers.map((w) => `<tr><td>${escape(w.full_name)}</td><td>${escape(w.phone || "—")}</td><td>${escape(w.address || "—")}</td><td>${w.salary_amount == null ? "—" : Number(w.salary_amount).toFixed(3)}</td><td>${salaryType(w.salary_type)}</td><td>${w.active === false ? labels[8] : labels[7]}</td></tr>`).join("");
  const html = `<!doctype html><html lang="${ar ? "ar" : "fr"}" dir="${ar ? "rtl" : "ltr"}"><meta charset="utf-8"><title>${labels[0]}</title><style>body{font-family:Arial,Tahoma,sans-serif;padding:24px;color:#222}h1{color:#34451f}table{width:100%;border-collapse:collapse}th{background:#34451f;color:white}td,th{border:1px solid #ddd;padding:9px;text-align:start}tr:nth-child(even){background:#f5f6f2}@page{size:A4 landscape;margin:12mm}</style><h1>ORO VERDE</h1><h2>${labels[0]}</h2><p>${new Date().toLocaleDateString(ar ? "ar-TN" : "fr-FR")}</p><table><thead><tr>${labels.slice(1,6).map(x=>`<th>${x}</th>`).join("")}<th>${labels[6]}</th></tr></thead><tbody>${rows}</tbody></table></html>`;
  return printHtmlInHiddenFrame(html, ar);
}

function escapeReportHtml(value: string) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#39;");
}

function printWorkforceReport({ records, workers, startDate, endDate, ar, locale }: { records: Attendance[]; workers: Worker[]; startDate: string; endDate: string; ar: boolean; locale: string }) {
  const days: string[] = []; const cursor = new Date(startDate + "T00:00:00Z"); const last = new Date(endDate + "T00:00:00Z");
  while (cursor <= last) { days.push(cursor.toISOString().slice(0, 10)); cursor.setUTCDate(cursor.getUTCDate() + 1); }
  const labels = ar ? { title: "تقرير الحضور والانصراف", employee: "العامل", total: "الإجمالي", days: "أيام العمل", hours: "ساعات العمل", absent: "غياب", period: "الفترة", note: "يُحتسب يوم الحضور حتى إن كانت الوردية مفتوحة. تُخصم فترات الراحة المسجلة يدوياً فقط، ولا يُخصم أي وقت تلقائياً. عدم وجود سجل لا يعني الغياب." } : { title: "Rapport des arrivées et départs", employee: "Employé", total: "Total", days: "Jours travaillés", hours: "Heures travaillées", absent: "Absent", period: "Période", note: "Un jour est compté dès qu’un pointage de présence existe, même si le quart est ouvert. Seules les pauses enregistrées manuellement sont déduites; aucune pause automatique. Aucun pointage ne signifie pas une absence." };
  const grouped = new Map<string, Map<string, Attendance>>();
  records.forEach((record) => { const row = grouped.get(record.worker_id) || new Map<string, Attendance>(); row.set(record.day, record); grouped.set(record.worker_id, row); });
  const head = days.map((day) => "<th title=\"" + day + "\">" + Number(day.slice(8, 10)) + "</th>").join("");
  const body = workers.map((worker) => {
    const entries = grouped.get(worker.id) || new Map<string, Attendance>(); const values = Array.from(entries.values());
    const workedDays = values.filter((r) => r.status === "PRESENT").length;
    const minutes = values.reduce((sum, r) => sum + workedMinutes(r), 0);
    const cells = days.map((day) => { const r = entries.get(day); if (!r) return "<td class=\"empty\">—</td>"; if (r.status === "ABSENT") return "<td class=\"absent\">" + labels.absent + "</td>"; return "<td class=\"present\"><b>" + displayShiftRange(r, locale) + "</b></td>"; }).join("");
    return "<tr><th class=\"worker\">" + escapeReportHtml(worker.full_name) + "</th>" + cells + "<td class=\"total\"><b>" + workedDays + "</b> " + labels.days + "<br><b>" + durationLabel(minutes) + "</b> " + labels.hours + "</td></tr>";
  }).join("");
  const html = "<!doctype html><html lang=\"" + (ar ? "ar" : "fr") + "\" dir=\"" + (ar ? "rtl" : "ltr") + "\"><meta charset=\"utf-8\"><title>" + labels.title + "</title>" +
    "<style>@page{size:A3 landscape;margin:8mm}html,body{width:100%;margin:0}body{font-family:Tahoma,Arial,sans-serif;font-size:8px;color:#222;-webkit-print-color-adjust:exact;print-color-adjust:exact}h1{color:#34451f}table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{border:1px solid #ddd;padding:4px 2px;text-align:center;overflow-wrap:anywhere;font-size:" + (days.length > 24 ? "6px" : "8px") + "}thead th{background:#34451f;color:white}.worker{text-align:start;background:#f3f5ef}.present{background:#e9f4eb;color:#245c37}.absent{background:#fde8e8;color:#a12b2b}.empty{color:#999}.total{background:#f3f5ef;color:#34451f}</style>" +
    "<h1>ORO VERDE — " + labels.title + "</h1><p>" + labels.period + ": " + startDate + " — " + endDate + "</p>" +
    "<table><thead><tr><th class=\"worker\">" + labels.employee + "</th>" + head + "<th class=\"total\">" + labels.total + "</th></tr></thead><tbody>" + body + "</tbody></table><p>" + labels.note + "</p>" +
    "</html>";
  return printHtmlInHiddenFrame(html, ar);
}
export default function Workforce() {
  const { lang, errMsg } = useI18n();
  const ar = lang === "ar";
  const locale = ar ? "ar-TN" : "fr-FR";
  const qc = useQueryClient();
  const today = localDay();
  const [payrollPeriod, setPayrollPeriod] = useState(today.slice(0, 7));
  const [payrollWorkerId, setPayrollWorkerId] = useState("");
  const [payrollKind, setPayrollKind] = useState<"ADVANCE" | "FINAL">("ADVANCE");
  const [payrollAmount, setPayrollAmount] = useState("");
  const [payrollMethod, setPayrollMethod] = useState<"CASH" | "CHEQUE" | "BANK_TRANSFER">("CASH");
  const [payrollAccountId, setPayrollAccountId] = useState("");
  const [payrollReference, setPayrollReference] = useState("");
  const [payrollRequestId, setPayrollRequestId] = useState(() => crypto.randomUUID());
  const [startDate, setStartDate] = useState(firstDayOfMonth(today));
  const [endDate, setEndDate] = useState(lastDayOfMonth(today));
  const [selectedWorkerId, setSelectedWorkerId] = useState("all");
  const [editing, setEditing] = useState<Attendance | null>(null);
  const [editIn, setEditIn] = useState("");
  const [editOut, setEditOut] = useState("");
  const [reason, setReason] = useState("");
  const [editStatus, setEditStatus] = useState<"PRESENT" | "ABSENT">("PRESENT");
  const emptyEmployee: EmployeeDraft = { first_name: "", last_name: "", phone: "", address: "", salary_amount: "", salary_type: "monthly" };
  const [employeeDraft, setEmployeeDraft] = useState<EmployeeDraft>(emptyEmployee);
  const [editingEmployee, setEditingEmployee] = useState<string | null>(null);
  const [employeeDialogOpen, setEmployeeDialogOpen] = useState(false);
  const [deletingEmployee, setDeletingEmployee] = useState<Worker | null>(null);
  const employeesQuery = useQuery({
    queryKey: ["workforce", "employees"],
    queryFn: () => apiGet<WorkersResponse>("/workforce/workers"),
  });
  const payrollQuery = useQuery({
    queryKey: ["workforce", "payroll", payrollPeriod, payrollWorkerId],
    enabled: !!payrollPeriod && !!payrollWorkerId,
    queryFn: () => apiGet<PayrollResponse>(`/workforce/payroll?period=${encodeURIComponent(payrollPeriod)}&worker_id=${encodeURIComponent(payrollWorkerId)}`),
  });
  useEffect(() => {
    if (payrollMethod !== "CASH" || !payrollWorkerId) return;
    const cashAccounts = (payrollQuery.data?.accounts ?? []).filter(account => account.account_type === "CASH");
    const principal = cashAccounts.find(account =>
      account.name.trim().toLocaleLowerCase("fr-FR") === "caisse principale"
    );
    setPayrollAccountId(principal?.id ?? "");
  }, [payrollMethod, payrollWorkerId, payrollPeriod, payrollQuery.data?.accounts]);
  const workerPayment = useMutation({
    mutationFn: () => apiPost<{ payment: unknown; reste_a_payer: string }>("/workforce/payments", {
      worker_id: payrollWorkerId, idempotency_key: payrollRequestId, period: payrollPeriod, payment_kind: payrollKind,
      amount_tnd: payrollKind === "ADVANCE" ? Number(payrollAmount) : null,
      payment_method: payrollMethod, account_id: payrollAccountId, reference: payrollReference,
    }),
    onSuccess: async () => {
      toast.success(ar ? "تم تسجيل الدفعة وربطها بالخزينة" : "Paiement enregistré et lié à la trésorerie");
      setPayrollAmount(""); setPayrollReference(""); setPayrollRequestId(crypto.randomUUID());
      await qc.invalidateQueries({ queryKey: ["workforce", "payroll"] });
      await qc.invalidateQueries({ queryKey: ["accounting-treasury-movement-register"] });
      await qc.invalidateQueries({ queryKey: ["accounting-treasury-accounts"] });
    },
    onError: (error) => toast.error(errMsg(error)),
  });
  const saveEmployee = useMutation({
    mutationFn: () => {
      const salaryText = employeeDraft.salary_amount.trim().replace(",", ".");
      const salaryValue = salaryText ? Number(salaryText) : null;
      if (salaryValue !== null && (!Number.isFinite(salaryValue) || salaryValue < 0)) {
        throw new Error(ar ? "أدخل مبلغ أجر صحيحًا." : "Saisissez un montant de salaire valide.");
      }
      const payload = { ...employeeDraft, salary_amount: salaryValue === null ? null : Math.round((salaryValue + Number.EPSILON) * 1000) / 1000 };
      return editingEmployee
        ? apiPatch<Worker>(`/workforce/workers/${editingEmployee}`, payload)
        : apiPost<Worker>("/workforce/workers", payload);
    },
    onSuccess: async () => {
      toast.success(ar ? "تم حفظ بيانات العامل" : "Employé enregistré");
      setEmployeeDraft(emptyEmployee); setEditingEmployee(null); setEmployeeDialogOpen(false);
      await qc.invalidateQueries({ queryKey: ["workforce", "employees"] });
      await qc.invalidateQueries({ queryKey: ["workforce", "attendance"] });
    },
    onError: (error) => toast.error(errMsg(error)),
  });
  const removeEmployee = useMutation({
    mutationFn: (id: string) => apiDelete<{ ok: boolean; deleted: boolean; attendance_deleted: number; events_deleted: number }>(`/workforce/workers/${id}`),
    onSuccess: async () => {
      setDeletingEmployee(null);
      toast.success(ar ? "تم حذف العامل وجميع سجلاته نهائياً" : "Employé et historique supprimés définitivement");
      await qc.invalidateQueries({ queryKey: ["workforce", "employees"] });
      await qc.invalidateQueries({ queryKey: ["workforce", "attendance"] });
    },
    onError: (error) => toast.error(errMsg(error)),
  });
  const restoreEmployee = useMutation({
    mutationFn: (id: string) => apiPatch<Worker>(`/workforce/workers/${id}`, { active: true }),
    onSuccess: async () => {
      toast.success(ar ? "تمت إعادة تنشيط العامل" : "Employé réactivé");
      await qc.invalidateQueries({ queryKey: ["workforce", "employees"] });
      await qc.invalidateQueries({ queryKey: ["workforce", "attendance"] });
    },
    onError: (error) => toast.error(errMsg(error)),
  });
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
  const historyDays = useMemo(() => {
    const days: string[] = []; if (!validRange) return days;
    const cursor = new Date(startDate + "T00:00:00Z"), last = new Date(endDate + "T00:00:00Z");
    while (cursor <= last) { days.push(cursor.toISOString().slice(0, 10)); cursor.setUTCDate(cursor.getUTCDate() + 1); }
    return days;
  }, [startDate, endDate, validRange]);
  const historyByWorker = useMemo(() => {
    const grouped = new Map<string, Map<string, Attendance>>();
    records.forEach((record) => { const row = grouped.get(record.worker_id) || new Map<string, Attendance>(); row.set(record.day, record); grouped.set(record.worker_id, row); });
    return grouped;
  }, [records]);

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
  const renderSummary = (title: string, rows: Summary[]) => {
    const SummaryIcon = title.includes(ar ? "اليومي" : "journaliers") ? CalendarCheck2
      : title.includes(ar ? "الأسبوعي" : "hebdomadaires") ? CalendarRange : CalendarClock;
    const summaryTone = title.includes(ar ? "اليومي" : "journaliers") ? "border-sky-200 bg-gradient-to-br from-sky-50 to-white"
      : title.includes(ar ? "الأسبوعي" : "hebdomadaires") ? "border-violet-200 bg-gradient-to-br from-violet-50 to-white"
      : "border-teal-200 bg-gradient-to-br from-teal-50 to-white";
    return (
    <section className={`rounded-2xl border p-4 shadow-sm ${summaryTone}`}>
      <div className="mb-3 flex items-center gap-2"><span className="grid size-9 place-items-center rounded-xl bg-white/90 shadow-sm"><SummaryIcon className="size-5 text-slate-700" /></span><h3 className="font-semibold text-stone-900">{title}</h3></div>
      {rows.length === 0 ? <p className="text-sm text-stone-500">{ar ? "لا توجد ورديات مكتملة ضمن هذه الفترة." : "Aucun quart terminé sur cette période."}</p> :
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead><tr className="border-b bg-stone-50 text-stone-600"><th className="px-3 py-2 text-start">{ar ? "الفترة" : "Période"}</th><th className="px-3 py-2 text-end">{ar ? "الورديات المكتملة" : "Quarts terminés"}</th><th className="px-3 py-2 text-end">{ar ? "مجموع الساعات" : "Total travaillé"}</th></tr></thead>
          <tbody>{rows.map((row) => <tr key={row.key} className="border-b last:border-0"><td className="px-3 py-2 font-medium" dir="ltr">{row.key}{title === (ar ? "المجموع الأسبوعي (الاثنين إلى الأحد)" : "Totaux hebdomadaires (lundi au dimanche)") ? ` → ${new Date(new Date(row.key + "T00:00:00Z").getTime() + 6 * 86400000).toISOString().slice(0, 10)}` : ""}</td><td className="px-3 py-2 text-end tabular-nums">{row.shifts}</td><td className="px-3 py-2 text-end font-semibold tabular-nums">{durationLabel(row.minutes)}</td></tr>)}</tbody>
        </table></div>}
    </section>
    );
  };

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
          <div className="ms-auto text-sm text-stone-500">{ar ? "كل الأوقات بتوقيت تونس. تُخصم فترات الراحة المسجلة يدوياً فقط." : "Heure de Tunisie. Seules les pauses enregistrées manuellement sont déduites."}</div>
        </div>
      </section>
      {data.isLoading ? <p className="py-8 text-center text-sm text-stone-500">{ar ? "جارٍ تحميل السجلات..." : "Chargement des pointages…"}</p> :
       data.isError ? <p className="py-8 text-center text-sm text-red-700">{ar ? "تعذر تحميل سجلات العمال." : "Impossible de charger les pointages."}</p> : <>
        <section className="grid gap-3 sm:grid-cols-4">
          {[
            { label: ar ? "إجمالي ساعات العمل" : "Total des heures", value: durationLabel(totals.minutes), icon: Timer, tone: "border-blue-200 bg-gradient-to-br from-blue-100 via-sky-50 to-white text-blue-950", iconTone: "bg-blue-600 text-white" },
            { label: ar ? "ورديات مكتملة" : "Quarts terminés", value: totals.closed, icon: CheckCircle2, tone: "border-emerald-200 bg-gradient-to-br from-emerald-100 via-green-50 to-white text-emerald-950", iconTone: "bg-emerald-600 text-white" },
            { label: ar ? "ورديات مفتوحة (غير محسوبة)" : "Quarts ouverts (exclus)", value: totals.open, icon: Hourglass, tone: "border-amber-200 bg-gradient-to-br from-amber-100 via-yellow-50 to-white text-amber-950", iconTone: "bg-amber-500 text-white" },
            { label: ar ? "غياب مسجل يدوياً" : "Absences confirmées", value: totals.absent, icon: UserX, tone: "border-rose-200 bg-gradient-to-br from-rose-100 via-pink-50 to-white text-rose-950", iconTone: "bg-rose-600 text-white" },
          ].map((item) => <div key={item.label} className={`relative overflow-hidden rounded-2xl border p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md ${item.tone}`}><div className="flex items-start justify-between gap-3"><div className="text-sm font-semibold opacity-80">{item.label}</div><span className={`grid size-11 shrink-0 place-items-center rounded-xl shadow-sm ${item.iconTone}`}><item.icon className="size-6" /></span></div><div className="mt-3 text-3xl font-extrabold tracking-tight tabular-nums" dir="ltr">{item.value}</div></div>)}
        </section>
        <div className="grid gap-4 xl:grid-cols-3">
          {renderSummary(ar ? "المجموع اليومي" : "Totaux journaliers", daily)}
          {renderSummary(ar ? "المجموع الأسبوعي (الاثنين إلى الأحد)" : "Totaux hebdomadaires (lundi au dimanche)", weekly)}
          {renderSummary(ar ? "المجموع الشهري" : "Totaux mensuels", monthly)}
        </div>
        {startDate <= today && endDate >= today && <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 font-semibold text-stone-900">{ar ? "تسجيل حضور اليوم" : "Pointage du jour"} <span className="text-sm font-normal text-stone-500" dir="ltr">{today}</span></h3>
          <div className="overflow-x-auto"><table className="w-full min-w-[680px] text-sm">
            <thead><tr className="border-b bg-stone-50 text-stone-600"><th className="px-3 py-3 text-start">{ar ? "العامل" : "Employé"}</th><th className="px-3 py-3 text-start">{ar ? "الحالة" : "Statut"}</th><th className="px-3 py-3 text-start">{ar ? "الحضور" : "Arrivée"}</th><th className="px-3 py-3 text-start">{ar ? "الانصراف" : "Départ"}</th><th className="px-3 py-3 text-end">{ar ? "الإجراءات" : "Actions"}</th></tr></thead>
            <tbody>{visibleWorkers.map((worker) => {
              // Include an overnight shift whose check-in date is outside the selected range.
              const record = recordsToday.get(worker.id) ?? openShiftsByWorker.get(worker.id);
              const checkedIn = record?.status === "PRESENT" && !!record.check_in_at;
              const checkedOut = !!record?.check_out_at;
              const onBreak = !!record?.break_started_at;
              return <tr key={worker.id} className="border-b last:border-0"><td className="px-3 py-3"><div className="font-semibold">{record?.worker_name || worker.full_name}</div><div className="text-xs text-stone-500">{worker.salary_amount == null ? (ar ? "الأجر غير محدد" : "Salaire non renseigné") : `${worker.salary_amount} — ${worker.salary_type === "hourly" ? (ar ? "بالساعة" : "par heure") : worker.salary_type === "daily" ? (ar ? "باليوم" : "par jour") : (ar ? "شهري" : "mensuel")}`}</div>{record && record.day !== today && <div className="text-xs text-amber-700">{ar ? `بدأت الوردية في ${record.day}` : `Quart commencé le ${record.day}`}</div>}</td>
                <td className="px-3 py-3">{record?.status === "ABSENT" ? (ar ? "غياب مؤكد" : "Absent confirmé") : checkedOut ? (ar ? "انصرف" : "Parti") : onBreak ? (ar ? "في راحة" : "En pause") : checkedIn ? (ar ? "حاضر" : "Présent") : (ar ? "لم يسجل — ليس غياباً" : "Non pointé — pas une absence")}</td>
                <td className="px-3 py-3 font-mono">{displayTime(record?.check_in_at, locale)}</td><td className="px-3 py-3 font-mono">{displayTime(record?.check_out_at, locale)}</td>
                <td className="px-3 py-3"><div className="flex justify-end gap-2">
                  {worker.active !== false && !checkedIn && !checkedOut && <Button size="sm" disabled={action.isPending} onClick={() => action.mutate({ type: "check-in", worker_id: worker.id })} className="bg-emerald-700 hover:bg-emerald-800"><LogIn className="me-1 size-4" />{ar ? "حضور" : "Arrivée"}</Button>}
                  {checkedIn && !checkedOut && !onBreak && <Button size="sm" disabled={action.isPending} onClick={() => action.mutate({ type: "break-start", worker_id: worker.id })} className="bg-amber-600 hover:bg-amber-700"><Coffee className="me-1 size-4" />{ar ? "راحة" : "Pause"}</Button>}
                  {checkedIn && !checkedOut && onBreak && <Button size="sm" disabled={action.isPending} onClick={() => action.mutate({ type: "break-end", worker_id: worker.id })} className="bg-emerald-700 hover:bg-emerald-800"><LogIn className="me-1 size-4" />{ar ? "عودة للعمل" : "Reprendre le travail"}</Button>}
                  {checkedIn && !checkedOut && !onBreak && <Button size="sm" disabled={action.isPending} onClick={() => action.mutate({ type: "check-out", worker_id: worker.id })} className="bg-indigo-700 hover:bg-indigo-800"><LogOut className="me-1 size-4" />{ar ? "انصراف" : "Départ"}</Button>}
                  {worker.active !== false && !record && <Button size="sm" variant="outline" disabled={action.isPending} onClick={() => { if (window.confirm(ar ? "تأكيد تسجيل غياب هذا العامل؟" : "Confirmer l’absence de cet employé ?")) action.mutate({ type: "mark-absent", worker_id: worker.id }); }} className="border-rose-200 text-rose-700 hover:bg-rose-50"><UserX className="me-1 size-4" />{ar ? "غياب" : "Absent"}</Button>}
                  {record && <Button size="sm" variant="outline" onClick={() => beginEdit(record)}><Pencil className="me-1 size-4" />{ar ? "تصحيح" : "Corriger"}</Button>}
                </div></td></tr>;
            })}</tbody>
          </table></div>
        </section>}
      </>}
      <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm space-y-4" data-testid="employee-registry">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h3 className="font-semibold text-stone-900">{ar ? "السجل المستقل للعمال" : "Registre indépendant des employés"}</h3><p className="text-sm text-stone-500">{ar ? "لا يرتبط بحسابات الدخول إلى التطبيق" : "Indépendant des comptes de connexion à l’application"}</p></div>
          <div className="flex flex-wrap items-center gap-2"><Button type="button" onClick={() => { setEditingEmployee(null); setEmployeeDraft(emptyEmployee); setEmployeeDialogOpen(true); }}><span className="me-2 text-lg leading-none">+</span>{ar ? "إضافة عامل" : "Ajouter un employé"}</Button><Button type="button" variant="outline" onClick={() => { if (!printEmployeeRegistry(employeesQuery.data?.workers ?? [], ar)) toast.error(ar ? "اسمح بفتح النوافذ المنبثقة للطباعة" : "Autorisez les fenêtres contextuelles pour imprimer"); }}><Printer className="me-2 size-4" />{ar ? "طباعة سجل العمال" : "Imprimer le registre"}</Button></div>
        </div>
        {employeesQuery.isLoading ? <p className="text-sm text-stone-500">{ar ? "جارٍ تحميل سجل العمال..." : "Chargement du registre…"}</p> : employeesQuery.isError ? <p className="text-sm text-red-700">{ar ? "تعذر تحميل سجل العمال" : "Impossible de charger le registre"}</p> :
          <div className="overflow-x-auto"><table className="w-full min-w-[850px] text-sm"><thead><tr className="border-b bg-stone-50 text-stone-600"><th className="p-2 text-start">{ar ? "العامل" : "Employé"}</th><th className="p-2 text-start">{ar ? "الهاتف" : "Téléphone"}</th><th className="p-2 text-start">{ar ? "العنوان" : "Adresse"}</th><th className="p-2 text-end">{ar ? "الأجر" : "Salaire"}</th><th className="p-2 text-start">{ar ? "نوع الأجر" : "Type"}</th><th className="p-2 text-start">{ar ? "الحالة" : "Statut"}</th><th className="p-2 text-end">{ar ? "إجراءات" : "Actions"}</th></tr></thead><tbody>{(employeesQuery.data?.workers ?? []).map(worker=><tr key={worker.id} className="border-b"><td className="p-2 font-semibold">{worker.full_name}</td><td className="p-2">{worker.phone || "—"}</td><td className="p-2">{worker.address || "—"}</td><td className="p-2 text-end tabular-nums" dir="ltr">{worker.salary_amount == null ? "—" : Number(worker.salary_amount).toFixed(3)}</td><td className="p-2">{worker.salary_type === "hourly" ? (ar ? "بالساعة" : "Horaire") : worker.salary_type === "daily" ? (ar ? "يومي" : "Journalier") : (ar ? "شهري" : "Mensuel")}</td><td className="p-2">{worker.active === false ? (ar ? "مؤرشف" : "Archivé") : (ar ? "نشط" : "Actif")}</td><td className="p-2"><div className="flex justify-end gap-2">{worker.active === false && <Button type="button" size="sm" variant="outline" disabled={restoreEmployee.isPending} onClick={()=>{if(window.confirm(ar ? "إعادة تنشيط هذا العامل؟" : "Réactiver cet employé ?")) restoreEmployee.mutate(worker.id);}} className="text-emerald-700">{ar ? "إعادة تنشيط" : "Réactiver"}</Button>}<Button type="button" size="sm" variant="outline" onClick={()=>{setEditingEmployee(worker.id);setEmployeeDraft({first_name:worker.first_name || worker.full_name,last_name:worker.last_name || "",phone:worker.phone || "",address:worker.address || "",salary_amount:worker.salary_amount == null ? "" : Number(worker.salary_amount).toFixed(3),salary_type:worker.salary_type || "monthly"});setEmployeeDialogOpen(true);}}><Pencil className="me-1 size-3" />{ar ? "تعديل" : "Modifier"}</Button><Button type="button" size="sm" variant="outline" disabled={removeEmployee.isPending} onClick={()=>setDeletingEmployee(worker)} className="text-rose-700">{ar ? "حذف" : "Supprimer"}</Button></div></td></tr>)}</tbody></table></div>}
        <p className="text-xs text-stone-500">{ar ? "يُحسب أجر العامل اليومي أو بالساعة من الورديات المغلقة. لا يُحسب الأجر الشهري لعدم تحديد قاعدة تحويله. العامل الذي لديه دفعات مسجلة لا يمكن حذفه نهائياً؛ يجب أرشفته للحفاظ على سجل الأجر والخزينة." : "Les salaires journaliers et horaires sont calculés à partir des quarts clôturés; le salaire mensuel reste non calculé faute de règle définie. Un employé ayant des paiements ne peut plus être supprimé définitivement : archivez-le pour préserver l’historique de paie et de trésorerie."}</p>
      </section>
      <section className="space-y-4 rounded-2xl border border-emerald-200 bg-white p-4 shadow-sm" data-testid="workforce-advances-payments">
        <div>
          <h3 className="font-semibold text-stone-900">{ar ? "التسبيقات واستخلاص الأجور" : "Avances et paiements"}</h3>
          <p className="text-sm text-stone-500">{ar ? "لا تُسجّل الدفعة في الخزينة إلا عند دفعها فعلياً. الحساب مبني على الورديات المغلقة." : "Seuls les paiements réellement effectués sont inscrits en trésorerie. Le calcul repose sur les quarts clôturés."}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="space-y-1"><Label>{ar ? "الشهر" : "Mois"}</Label><Input type="month" value={payrollPeriod} onChange={e=>setPayrollPeriod(e.target.value)} /></div>
          <div className="space-y-1"><Label>{ar ? "العامل" : "Employé"}</Label><select value={payrollWorkerId} onChange={e=>{setPayrollWorkerId(e.target.value);setPayrollAccountId("");}} className="h-10 w-full rounded-md border border-stone-300 bg-white px-3 text-sm"><option value="">{ar ? "اختر العامل" : "Choisir un employé"}</option>{(employeesQuery.data?.workers ?? []).map(w=><option key={w.id} value={w.id}>{w.full_name}</option>)}</select></div>
          <div className="space-y-1"><Label>{ar ? "نوع الدفعة" : "Type de paiement"}</Label><select value={payrollKind} onChange={e=>setPayrollKind(e.target.value as "ADVANCE" | "FINAL")} className="h-10 w-full rounded-md border border-stone-300 bg-white px-3 text-sm"><option value="ADVANCE">{ar ? "تسبيق / دفعة" : "Avance"}</option><option value="FINAL">{ar ? "الاستخلاص النهائي" : "Solde final"}</option></select></div>
        </div>
        {payrollWorkerId && payrollQuery.data?.workers?.[0] && (() => {
          const row = payrollQuery.data.workers[0];
          const accounts = (payrollQuery.data.accounts ?? []).filter(a => a.account_type === (payrollMethod === "CASH" ? "CASH" : "BANK"));
          return <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-sky-200 bg-sky-50 p-3"><div className="text-xs text-sky-800">{ar ? "مبلغ العمل المستحق" : "Montant du travail"}</div><div className="mt-1 text-xl font-bold text-sky-950" dir="ltr">{row.supported ? row.montant_du_travail + " TND" : "—"}</div></div>
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3"><div className="text-xs text-amber-800">{ar ? "مجموع التسبيقات" : "Total des avances"}</div><div className="mt-1 text-xl font-bold text-amber-950" dir="ltr">{row.total_advances} TND</div></div>
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3"><div className="text-xs text-emerald-800">{ar ? "الباقي للاستخلاص" : "Reste à payer"}</div><div className="mt-1 text-xl font-bold text-emerald-950" dir="ltr">{row.reste_a_payer} TND</div></div>
            </div>
            {row.incomplete_shifts > 0 ? <p className="text-sm text-rose-700">{ar ? "يوجد حضور دون انصراف أو وردية بتوقيت غير صالح. أكمل التصحيح قبل تسجيل أي دفعة." : "Un pointage est ouvert ou invalide. Clôturez ou corrigez les quarts avant tout paiement."}</p> : null}
            {!row.supported ? <p className="text-sm text-amber-800">{ar ? "لا يمكن احتساب الأجر الشهري: طريقة تحويله إلى أجر يومي أو ساعي غير محددة." : "Salaire mensuel non payable : aucune règle de conversion en taux journalier ou horaire n’est définie."}</p> :
            <form className="grid gap-3 rounded-xl border border-stone-200 bg-stone-50 p-3 sm:grid-cols-2" onSubmit={e=>{e.preventDefault();workerPayment.mutate();}}>
              {payrollKind === "ADVANCE" && <div className="space-y-1"><Label>{ar ? "مبلغ التسبيق (TND)" : "Montant de l’avance (TND)"}</Label><Input required type="number" min="0.001" max={row.reste_a_payer} step="0.001" value={payrollAmount} onChange={e=>setPayrollAmount(e.target.value)} /></div>}
              <div className="space-y-1"><Label>{ar ? "طريقة الدفع" : "Mode de paiement"}</Label><select value={payrollMethod} onChange={e=>{setPayrollMethod(e.target.value as typeof payrollMethod);setPayrollAccountId("");setPayrollReference("");}} className="h-10 w-full rounded-md border border-stone-300 bg-white px-3 text-sm"><option value="CASH">Espèces</option><option value="CHEQUE">Chèque</option><option value="BANK_TRANSFER">Virement</option></select></div>
              <div className="space-y-1"><Label>{ar ? (payrollMethod === "CASH" ? "حساب الصندوق" : "الحساب البنكي") : (payrollMethod === "CASH" ? "Compte de caisse" : "Compte bancaire")}</Label><select required value={payrollAccountId} onChange={e=>setPayrollAccountId(e.target.value)} className="h-10 w-full rounded-md border border-stone-300 bg-white px-3 text-sm"><option value="">{ar ? "اختر الحساب" : "Choisir le compte"}</option>{accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select>{accounts.length===0 && <p className="text-xs text-rose-700">{ar ? "لا يوجد حساب نشط مناسب لهذه الطريقة." : "Aucun compte actif compatible."}</p>}{payrollMethod === "CASH" && !accounts.some(a => a.id === payrollAccountId) && accounts.length>0 && <p className="text-xs text-rose-700">{ar ? "لم يتم العثور على حساب Caisse principale. تحقق من اسم الحساب أو حالته." : "Le compte « Caisse principale » est introuvable parmi les caisses actives."}</p>}</div>
              {payrollMethod !== "CASH" && <div className="space-y-1"><Label>{ar ? (payrollMethod === "CHEQUE" ? "مرجع الشيك (اختياري)" : "مرجع التحويل (اختياري)") : (payrollMethod === "CHEQUE" ? "Référence chèque (facultatif)" : "Référence virement (facultatif)")}</Label><Input value={payrollReference} onChange={e=>setPayrollReference(e.target.value)} maxLength={120} /></div>}
              <div className="sm:col-span-2 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-stone-500">{payrollKind === "FINAL" ? (ar ? "سيتم دفع كامل الأجر المكتسب وغير المدفوع حتى الآن." : "Tout le salaire acquis et non payé sera réglé, sans dépasser le dû.") : (ar ? "لا يمكن أن يتجاوز التسبيق الأجر المكتسب وغير المدفوع حتى الآن." : "L’avance ne peut pas dépasser les salaires acquis et non encore payés.")}</p>
                <Button type="submit" disabled={workerPayment.isPending || row.incomplete_shifts>0 || !accounts.some(a=>a.id===payrollAccountId) || Number(row.reste_a_payer)<=0 || (payrollKind==="ADVANCE" && (!payrollAmount || Number(payrollAmount)<=0 || Number(payrollAmount)>Number(row.reste_a_payer)))}>{payrollKind==="FINAL" ? (ar ? "دفع الباقي النهائي" : "Payer le solde final") : (ar ? "تسجيل التسبيق" : "Enregistrer l’avance")}</Button>
              </div>
              {(() => {
                const reason = workerPayment.isPending
                  ? (ar ? "جارٍ تسجيل الدفعة..." : "Enregistrement du paiement en cours…")
                  : row.incomplete_shifts > 0
                    ? (ar ? "أكمل أو صحح الورديات المفتوحة أولاً." : "Clôturez ou corrigez les pointages ouverts.")
                    : !accounts.some(a=>a.id===payrollAccountId)
                      ? (ar ? (payrollMethod === "CASH" ? "تعذر تحديد Caisse principale تلقائياً." : "اختر حساب الدفع المناسب.") : (payrollMethod === "CASH" ? "Le compte Caisse principale n’est pas sélectionné." : "Sélectionnez un compte de paiement."))
                      : Number(row.reste_a_payer) <= 0
                        ? (ar ? "لا يوجد أجر متبقٍ غير مدفوع." : "Aucun salaire restant à payer.")
                        : payrollKind === "ADVANCE" && (!payrollAmount || Number(payrollAmount)<=0 || Number(payrollAmount)>Number(row.reste_a_payer))
                              ? (ar ? "أدخل تسبيقًا صحيحًا لا يتجاوز الباقي." : "Saisissez une avance valide ne dépassant pas le solde.")
                              : "";
                return reason ? <p className="sm:col-span-2 text-xs text-amber-800" role="status">{reason}</p> : null;
              })()}
            </form>}
            <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-sm"><thead><tr className="border-b bg-stone-50"><th className="p-2 text-start">{ar ? "التاريخ" : "Date"}</th><th className="p-2 text-start">{ar ? "النوع" : "Type"}</th><th className="p-2 text-start">{ar ? "الطريقة / الحساب" : "Mode / compte"}</th><th className="p-2 text-end">{ar ? "المبلغ" : "Montant"}</th><th className="p-2 text-start">{ar ? "المطابقة" : "Rapprochement"}</th></tr></thead><tbody>{(payrollQuery.data?.payments ?? []).map(p=><tr key={p.id} className="border-b"><td className="p-2" dir="ltr">{new Date(p.paid_at).toLocaleDateString(locale)}</td><td className="p-2">{p.payment_kind==="FINAL" ? (ar ? "نهائي" : "Solde final") : (ar ? "تسبيق" : "Avance")}</td><td className="p-2">{p.payment_method} — {p.account_name_snapshot}</td><td className="p-2 text-end font-semibold" dir="ltr">{Number(p.amount_tnd).toFixed(3)} TND</td><td className="p-2 text-emerald-700">{ar ? "مطابق إدارياً" : "Rapproché (administratif)"}</td></tr>)}</tbody></table></div>
          </div>;
        })()}
        {payrollWorkerId && payrollQuery.isLoading && <p className="text-sm text-stone-500">{ar ? "جارٍ حساب المستحقات..." : "Calcul des montants…"}</p>}
        {payrollWorkerId && payrollQuery.isError && <p className="text-sm text-rose-700">{ar ? "تعذر تحميل مستحقات العامل." : "Impossible de charger la paie."}</p>}
      </section>
      <Dialog open={employeeDialogOpen} onOpenChange={(open) => { setEmployeeDialogOpen(open); if (!open && !saveEmployee.isPending) { setEditingEmployee(null); setEmployeeDraft(emptyEmployee); } }}>
        <DialogContent data-testid="employee-form-dialog" className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader><DialogTitle>{editingEmployee ? (ar ? "تعديل بيانات العامل" : "Modifier l’employé") : (ar ? "إضافة عامل جديد" : "Ajouter un employé")}</DialogTitle></DialogHeader>
          <form className="grid gap-3 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); if (!employeeDraft.first_name.trim()) return; saveEmployee.mutate(); }}>
            <div className="space-y-1"><Label>{ar ? "الاسم" : "Prénom"}</Label><Input required value={employeeDraft.first_name} onChange={e=>setEmployeeDraft(v=>({...v,first_name:e.target.value}))} /></div>
            <div className="space-y-1"><Label>{ar ? "اللقب" : "Nom"}</Label><Input value={employeeDraft.last_name} onChange={e=>setEmployeeDraft(v=>({...v,last_name:e.target.value}))} /></div>
            <div className="space-y-1"><Label>{ar ? "الهاتف" : "Téléphone"}</Label><Input value={employeeDraft.phone} onChange={e=>setEmployeeDraft(v=>({...v,phone:e.target.value}))} /></div>
            <div className="space-y-1"><Label>{ar ? "العنوان" : "Adresse"}</Label><Input value={employeeDraft.address} onChange={e=>setEmployeeDraft(v=>({...v,address:e.target.value}))} /></div>
            <div className="space-y-1"><Label>{ar ? "مبلغ الأجر" : "Montant du salaire"}</Label><Input type="text" inputMode="decimal" autoComplete="off" placeholder="0.000" value={employeeDraft.salary_amount} onChange={e=>setEmployeeDraft(v=>({...v,salary_amount:e.target.value.replace(/[^0-9.,]/g, "")}))} /></div>
            <div className="space-y-1"><Label>{ar ? "نوع الأجر" : "Type de salaire"}</Label><select value={employeeDraft.salary_type} onChange={e=>setEmployeeDraft(v=>({...v,salary_type:e.target.value as EmployeeDraft["salary_type"]}))} className="h-10 w-full rounded-md border border-stone-300 bg-white px-3 text-sm"><option value="monthly">{ar ? "شهري" : "Mensuel"}</option><option value="daily">{ar ? "يومي" : "Journalier"}</option><option value="hourly">{ar ? "بالساعة" : "Horaire"}</option></select></div>
            <DialogFooter className="sm:col-span-2"><Button type="button" variant="outline" disabled={saveEmployee.isPending} onClick={() => { setEmployeeDialogOpen(false); setEditingEmployee(null); setEmployeeDraft(emptyEmployee); }}>{ar ? "إلغاء" : "Annuler"}</Button><Button type="submit" disabled={saveEmployee.isPending}>{editingEmployee ? (ar ? "حفظ التعديل" : "Enregistrer") : (ar ? "إضافة عامل" : "Ajouter un employé")}</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
      <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950"><Clock3 className="mt-0.5 size-4 shrink-0" /><p>{ar ? "تُخصم فترات الراحة المسجلة يدوياً فقط. يمكن أن ينتهي العمل في اليوم التالي؛ تُحسب الساعات بين تاريخي الدخول والخروج وتُسجل على يوم الدخول. الوردية المفتوحة لا تدخل في المجموع، والوردية التي تتجاوز 24 ساعة أو بياناتها غير صحيحة تستوجب مراجعة المدير. لا يُسجل الغياب إلا بتأكيد يدوي." : "Seules les pauses enregistrées manuellement sont déduites. Les quarts ouverts sont exclus du total. Un quart peut se terminer le lendemain : les heures sont calculées entre les deux dates et rattachées au jour d’arrivée. Un quart de plus de 24 heures ou des heures incohérentes nécessite une vérification. Une absence doit être confirmée manuellement."}</p></div>
        <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm" data-testid="workforce-monthly-history">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-semibold text-stone-900">{ar ? "سجل الحضور والانصراف حسب الأيام" : "Historique des arrivées et départs — vue par jour"}</h3>
            <span className="text-xs text-stone-500" dir="ltr">{startDate} — {endDate}</span>
          </div>
          {visibleWorkers.length === 0 ? <p className="py-8 text-center text-sm text-stone-500">{ar ? "لا يوجد عمال لعرضهم." : "Aucun employé à afficher."}</p> :
          <div className="overflow-x-auto"><table className="w-full min-w-max border-collapse text-xs">
            <thead><tr className="bg-stone-50 text-stone-600">
              <th className="sticky start-0 z-10 min-w-44 border-b px-3 py-3 text-start">{ar ? "العامل" : "Employé"}</th>
              {historyDays.map((day) => <th key={day} title={day} className="min-w-[92px] border-b px-2 py-3 text-center"><span dir="ltr">{Number(day.slice(8, 10))}</span></th>)}
              <th className="min-w-40 border-b bg-emerald-50 px-3 py-3 text-center">{ar ? "الإجمالي" : "Total"}</th>
              <th className="min-w-36 border-b bg-amber-50 px-3 py-3 text-center">{ar ? "مبلغ العمل" : "Montant du travail"}</th>
            </tr></thead>
            <tbody>{visibleWorkers.map((worker) => {
              const entries = historyByWorker.get(worker.id);
              const values = entries ? Array.from(entries.values()) : [];
              const workedDays = values.filter((record) => record.status === "PRESENT").length;
              const minutes = values.reduce((sum, record) => sum + workedMinutes(record), 0);
              const hasIncompleteShift = values.some((record) => record.status === "PRESENT" && workedMinutes(record) === 0);
              const hasSupportedSalaryType = worker.salary_type === "daily" || worker.salary_type === "hourly";
              const totalWorkAmount = !hasSupportedSalaryType || worker.salary_amount == null || values.length === 0 || hasIncompleteShift
                ? null
                : values.reduce((sum, record) => sum + (workedAmount(worker, record) ?? 0), 0);
              return <tr key={worker.id} className="border-b last:border-0 hover:bg-stone-50/70">
                <th className="sticky start-0 z-[1] bg-white px-3 py-3 text-start font-semibold">{worker.full_name}</th>
                {historyDays.map((day) => {
                  const record = entries?.get(day);
                  if (!record) return <td key={day} className="px-2 py-3 text-center text-stone-300">—</td>;
                  if (record.status === "ABSENT") return <td key={day} className="px-2 py-2 text-center"><span className="inline-flex rounded-md bg-rose-100 px-2 py-1 font-semibold text-rose-800">{ar ? "غياب" : "Absent"}</span><div><Button size="sm" variant="ghost" className="h-6 px-1 text-[10px]" onClick={() => beginEdit(record)}><Pencil className="me-1 size-3" />{ar ? "تصحيح" : "Corriger"}</Button></div></td>;
                  const open = !!record.check_in_at && !record.check_out_at;
                  const invalid = !!record.check_in_at && !!record.check_out_at && workedMinutes(record) === 0;
                  return <td key={day} className="px-2 py-2 text-center">
                    <div className={"rounded-md px-1 py-1 font-mono font-semibold " + (open ? "bg-amber-50 text-amber-800" : invalid ? "bg-orange-50 text-orange-800" : "bg-emerald-50 text-emerald-800")} dir="ltr">{displayShiftRange(record, locale)}</div>
                    <div className="mt-1 text-[11px] font-semibold text-emerald-800" dir="ltr">{workedAmount(worker, record) == null ? "—" : formatWorkAmount(workedAmount(worker, record)!, locale)}</div>
                    <Button size="sm" variant="ghost" className="mt-1 h-6 px-1 text-[10px]" onClick={() => beginEdit(record)}><Pencil className="me-1 size-3" />{ar ? "تصحيح" : "Corriger"}</Button>
                  </td>;
                })}
                <td className="bg-emerald-50/60 px-3 py-2 text-center font-semibold text-emerald-900"><div>{workedDays} {ar ? "أيام" : "jours"}</div><div className="mt-1 font-mono" dir="ltr">{durationLabel(minutes)}</div></td>
                <td className="bg-amber-50/70 px-3 py-2 text-center font-semibold text-amber-900" dir="ltr">{totalWorkAmount == null ? "—" : formatWorkAmount(totalWorkAmount, locale)}</td>
              </tr>;
            })}</tbody>
          </table></div>}
          <p className="mt-3 text-xs text-stone-500">{ar ? "يُحتسب الأجر اليومي بنسبة ساعات العمل من 8 ساعات، والأجر بالساعة حسب الساعات الفعلية. لا يُحسب الأجر الشهري لعدم تحديد طريقة تحويله إلى أجر يومي. الوردية المفتوحة أو ذات التوقيت غير الصحيح لا يظهر لها مبلغ حتى تصحيح الانصراف. لا يُخصم وقت الاستراحة. لا توجد سجلات في الفترة المختارة. عدم وجود سجل لا يعني الغياب." : "Le salaire journalier est proratisé sur une base de 8 heures; le salaire horaire suit les heures réellement travaillées. Le salaire mensuel n’est pas calculé faute de règle de conversion journalière. Les quarts ouverts ou invalides restent sans montant jusqu’à correction. Seules les pauses enregistrées manuellement sont déduites."}</p>
        </section>
      <Dialog open={!!deletingEmployee} onOpenChange={(open) => !open && !removeEmployee.isPending && setDeletingEmployee(null)}>
        <DialogContent data-testid="delete-employee-confirmation">
          <DialogHeader><DialogTitle>{ar ? "تأكيد الحذف النهائي" : "Confirmer la suppression définitive"}</DialogTitle></DialogHeader>
          <div className="space-y-2 text-sm">
            <p>{ar ? `هل تريد حذف العامل «${deletingEmployee?.full_name ?? ""}» نهائياً؟` : `Voulez-vous supprimer définitivement «${deletingEmployee?.full_name ?? ""}» ?`}</p>
            <p className="font-semibold text-rose-700">{ar ? "سيتم حذف بيانات العامل وجميع سجلات حضوره وانصرافه وتصحيحاتها. لا يمكن التراجع عن هذه العملية." : "Les données de l’employé, tous ses pointages et leur historique de corrections seront effacés. Cette action est irréversible."}</p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" disabled={removeEmployee.isPending} onClick={() => setDeletingEmployee(null)}>{ar ? "إلغاء" : "Annuler"}</Button>
            <Button type="button" variant="destructive" disabled={removeEmployee.isPending || !deletingEmployee} onClick={() => deletingEmployee && removeEmployee.mutate(deletingEmployee.id)}>{ar ? "Supprimer" : "Supprimer"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
