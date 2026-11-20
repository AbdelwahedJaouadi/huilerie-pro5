import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Clock3, LogIn, LogOut, Pencil, UserCheck, UserX } from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { PageHeader } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

type Worker = { id: string; full_name: string; username: string };
type Attendance = {
  id: string; worker_id: string; worker_name: string; day: string;
  status: "PRESENT" | "ABSENT"; check_in_at: string | null; check_out_at: string | null;
  marked_absent_at?: string | null;
};
type AttendanceResponse = { day: string; workers: Worker[]; records: Attendance[] };
type Action = "check-in" | "check-out" | "mark-absent";

function localDay() {
  const now = new Date();
  return [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"), String(now.getDate()).padStart(2, "0")].join("-");
}
function localDateTime(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16);
}
function displayTime(value: string | null | undefined, locale: string) {
  return value ? new Date(value).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" }) : "—";
}

export default function Workforce() {
  const { lang, errMsg } = useI18n();
  const ar = lang === "ar";
  const locale = ar ? "ar-TN" : "fr-CA";
  const qc = useQueryClient();
  const [day, setDay] = useState(localDay);
  const [editing, setEditing] = useState<Attendance | null>(null);
  const [editIn, setEditIn] = useState("");
  const [editOut, setEditOut] = useState("");
  const [reason, setReason] = useState("");
  const queryKey = ["workforce", "attendance", day];
  const data = useQuery({
    queryKey,
    queryFn: () => apiGet<AttendanceResponse>(`/workforce/attendance?day=${encodeURIComponent(day)}`),
  });
  const action = useMutation({
    mutationFn: ({ type, worker_id }: { type: Action; worker_id: string }) =>
      apiPost<Attendance>(`/workforce/attendance/${type}`, { worker_id, day }),
    onSuccess: async () => {
      toast.success(ar ? "تم تحديث سجل العامل" : "Pointage mis à jour");
      await qc.invalidateQueries({ queryKey });
    },
    onError: (error) => toast.error(errMsg(error)),
  });
  const correction = useMutation({
    mutationFn: () => {
      if (!editing) throw new Error("attendance_not_selected");
      return apiPatch<Attendance>(`/workforce/attendance/${editing.id}`, {
        check_in_at: editIn ? new Date(editIn).toISOString() : null,
        check_out_at: editOut ? new Date(editOut).toISOString() : null,
        status: editing.status,
        reason: reason.trim(),
      });
    },
    onSuccess: async () => {
      toast.success(ar ? "تم تصحيح السجل وحفظ أثر التعديل" : "Pointage corrigé; la modification est journalisée");
      setEditing(null); setReason("");
      await qc.invalidateQueries({ queryKey });
    },
    onError: (error) => toast.error(errMsg(error)),
  });
  const records = useMemo(() => new Map((data.data?.records ?? []).map((record) => [record.worker_id, record])), [data.data]);
  const workers = data.data?.workers ?? [];
  const counts = useMemo(() => {
    let present = 0, absent = 0, checkedOut = 0;
    for (const record of records.values()) {
      if (record.status === "ABSENT") absent++;
      else { present++; if (record.check_out_at) checkedOut++; }
    }
    return { present, absent, checkedOut, pending: Math.max(0, workers.length - present - absent) };
  }, [records, workers.length]);

  const beginEdit = (record: Attendance) => {
    setEditing(record);
    setEditIn(localDateTime(record.check_in_at));
    setEditOut(localDateTime(record.check_out_at));
    setReason("");
  };

  return (
    <div className="space-y-5" dir={ar ? "rtl" : "ltr"} data-testid="workforce-page">
      <PageHeader
        title={ar ? "جدول العمال والحضور" : "Personnel et pointage"}
        description={ar ? "تسجيل حضور العمال وانصرافهم اليومي بواسطة المدير" : "Enregistrement quotidien des arrivées et départs par l’administrateur"}
      />
      <section className="grid gap-3 sm:grid-cols-4">
        {[
          { label: ar ? "العمال النشطون" : "Employés actifs", value: workers.length, icon: UserCheck, tone: "bg-sky-50 text-sky-800" },
          { label: ar ? "حاضرون" : "Présents", value: counts.present, icon: UserCheck, tone: "bg-emerald-50 text-emerald-800" },
          { label: ar ? "انصرفوا" : "Départs enregistrés", value: counts.checkedOut, icon: LogOut, tone: "bg-violet-50 text-violet-800" },
          { label: ar ? "غياب مسجل" : "Absences", value: counts.absent, icon: UserX, tone: "bg-rose-50 text-rose-800" },
        ].map((item) => (
          <div key={item.label} className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between gap-2"><span className="text-sm text-stone-600">{item.label}</span><span className={`grid size-9 place-items-center rounded-lg ${item.tone}`}><item.icon className="size-4" /></span></div>
            <div className="mt-2 text-2xl font-bold tabular-nums text-stone-900">{item.value}</div>
          </div>
        ))}
      </section>
      <section className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div className="space-y-1">
            <Label htmlFor="workforce-day">{ar ? "تاريخ الحضور" : "Date du pointage"}</Label>
            <div className="flex items-center gap-2">
              <CalendarDays className="size-4 text-stone-500" />
              <Input id="workforce-day" data-testid="workforce-date" type="date" value={day} onChange={(event) => setDay(event.target.value)} className="w-auto" />
            </div>
          </div>
          <div className="text-sm text-stone-500">{ar ? "التوقيت يُحفظ بتوقيت UTC ويُعرض حسب توقيت الجهاز." : "Les heures sont conservées en UTC et affichées selon le fuseau de l’appareil."}</div>
        </div>
        {data.isLoading ? <p className="py-8 text-center text-sm text-stone-500">{ar ? "جارٍ تحميل جدول العمال..." : "Chargement du pointage…"}</p> :
          data.isError ? <p className="py-8 text-center text-sm text-red-700">{ar ? "تعذر تحميل جدول العمال." : "Impossible de charger le pointage."}</p> :
          workers.length === 0 ? <p className="py-8 text-center text-sm text-stone-500">{ar ? "لا توجد حسابات عمال نشطة." : "Aucun employé actif."}</p> :
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead><tr className="border-b border-stone-200 bg-stone-50 text-start text-stone-600">
                <th className="px-3 py-3 text-start">{ar ? "العامل" : "Employé"}</th>
                <th className="px-3 py-3 text-start">{ar ? "الحالة" : "Statut"}</th>
                <th className="px-3 py-3 text-start">{ar ? "وقت الحضور" : "Arrivée"}</th>
                <th className="px-3 py-3 text-start">{ar ? "وقت الانصراف" : "Départ"}</th>
                <th className="px-3 py-3 text-end">{ar ? "الإجراءات" : "Actions"}</th>
              </tr></thead>
              <tbody>
                {workers.map((worker) => {
                  const record = records.get(worker.id);
                  const absent = record?.status === "ABSENT";
                  const checkedIn = record?.status === "PRESENT" && !!record.check_in_at;
                  const checkedOut = !!record?.check_out_at;
                  return <tr key={worker.id} data-testid={`workforce-row-${worker.id}`} className="border-b border-stone-100 last:border-0">
                    <td className="px-3 py-4"><div className="font-semibold text-stone-900">{worker.full_name}</div><div dir="ltr" className="text-xs text-stone-500">{worker.username}</div></td>
                    <td className="px-3 py-4">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${absent ? "bg-rose-100 text-rose-800" : checkedOut ? "bg-violet-100 text-violet-800" : checkedIn ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>
                        {absent ? (ar ? "غائب" : "Absent") : checkedOut ? (ar ? "انصرف" : "Parti") : checkedIn ? (ar ? "حاضر" : "Présent") : (ar ? "لم يسجل" : "Non pointé")}
                      </span>
                    </td>
                    <td className="px-3 py-4 font-mono tabular-nums">{displayTime(record?.check_in_at, locale)}</td>
                    <td className="px-3 py-4 font-mono tabular-nums">{displayTime(record?.check_out_at, locale)}</td>
                    <td className="px-3 py-4">
                      <div className="flex justify-end gap-2">
                        {!checkedIn && !checkedOut && <Button size="sm" data-testid={`workforce-checkin-${worker.id}`} disabled={action.isPending} onClick={() => action.mutate({ type: "check-in", worker_id: worker.id })} className="bg-emerald-700 hover:bg-emerald-800"><LogIn className="me-1 size-4" />{ar ? "حضور" : "Arrivée"}</Button>}
                        {checkedIn && !checkedOut && <Button size="sm" data-testid={`workforce-checkout-${worker.id}`} disabled={action.isPending} onClick={() => action.mutate({ type: "check-out", worker_id: worker.id })} className="bg-indigo-700 hover:bg-indigo-800"><LogOut className="me-1 size-4" />{ar ? "انصراف" : "Départ"}</Button>}
                        {!record && <Button size="sm" variant="outline" data-testid={`workforce-absent-${worker.id}`} disabled={action.isPending} onClick={() => { if (window.confirm(ar ? "تأكيد تسجيل غياب هذا العامل؟" : "Confirmer l’absence de cet employé ?")) action.mutate({ type: "mark-absent", worker_id: worker.id }); }} className="border-rose-200 text-rose-700 hover:bg-rose-50"><UserX className="me-1 size-4" />{ar ? "غياب" : "Absent"}</Button>}
                        {record && <Button size="sm" variant="outline" data-testid={`workforce-edit-${worker.id}`} onClick={() => beginEdit(record)}><Pencil className="me-1 size-4" />{ar ? "تصحيح" : "Corriger"}</Button>}
                      </div>
                    </td>
                  </tr>;
                })}
              </tbody>
            </table>
          </div>}
      </section>
      <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
        <Clock3 className="mt-0.5 size-4 shrink-0" />
        <p>{ar ? "هذا السجل يحفظ أوقات الحضور والانصراف والغياب فقط. لا يحسب التأخير أو الساعات الإضافية قبل تحديد أوقات الدوام الرسمية." : "Ce registre conserve les arrivées, départs et absences. Les retards et heures supplémentaires ne seront calculés qu’après définition des horaires officiels."}</p>
      </div>
      <Dialog open={!!editing} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent data-testid="workforce-correction-dialog">
          <DialogHeader><DialogTitle>{ar ? "تصحيح سجل الحضور" : "Corriger le pointage"} — {editing?.worker_name}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1"><Label>{ar ? "وقت الحضور" : "Heure d’arrivée"}</Label><Input type="datetime-local" value={editIn} onChange={(event) => setEditIn(event.target.value)} /></div>
            <div className="space-y-1"><Label>{ar ? "وقت الانصراف" : "Heure de départ"}</Label><Input type="datetime-local" value={editOut} onChange={(event) => setEditOut(event.target.value)} /></div>
            <div className="space-y-1"><Label>{ar ? "سبب التصحيح (إجباري)" : "Motif de correction (obligatoire)"}</Label><Input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} placeholder={ar ? "مثال: تم إدخال وقت خاطئ" : "Ex. : heure saisie incorrectement"} /></div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setEditing(null)}>{ar ? "إلغاء" : "Annuler"}</Button>
            <Button type="button" disabled={reason.trim().length < 5 || correction.isPending} onClick={() => correction.mutate()} className="bg-indigo-700 hover:bg-indigo-800">{ar ? "حفظ التصحيح" : "Enregistrer la correction"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
