import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Clock3, LogIn, LogOut, Pencil, UserX } from "lucide-react";
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

export default function Workforce() {
  const { lang, errMsg } = useI18n();
  const ar = lang === "ar";
  const locale = ar ? "ar-TN" : "fr-FR";
  const qc = useQueryClient();
  const today = localDay();
  const [startDate, setStartDate] = useState(firstDayOfMonth(today));
  const [endDate, setEndDate] = useState(today);
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
  const records = data.data?.records ?? [];
  const workers = data.data?.workers ?? [];
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
          {!validRange && <p className="text-sm text-red-700">{ar ? "تاريخ البداية يجب أن يسبق تاريخ النهاية أو يساويه." : "La date de début doit précéder ou égaler la date de fin."}</p>}
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
            <tbody>{workers.map((worker) => {
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
