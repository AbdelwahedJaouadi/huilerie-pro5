import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Scale, Cable, Network, Usb, Save, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiGet, apiPut } from "@/lib/api";
import type { AppSettings, ScaleConfig } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

const DEFAULT_SCALE: ScaleConfig = {
  enabled: false, manufacturer: "", model: "", connection_type: "serial",
  serial_port: "", baud_rate: 9600, data_bits: 8, parity: "none", stop_bits: 1,
  host: "", port: null, protocol: "", unit: "kg", decimal_places: 3,
  stable_readings: 3, device_id: "",
};

export default function ScaleSettings() {
  const { lang, errMsg } = useI18n();
  const ar = lang === "ar";
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => apiGet<AppSettings>("/settings") });
  const [config, setConfig] = useState<ScaleConfig>(DEFAULT_SCALE);
  const [initialized, setInitialized] = useState(false);
  const text = (fr: string, arabic: string) => ar ? arabic : fr;

  useEffect(() => {
    if (!settings.data) return;
    setConfig({ ...DEFAULT_SCALE, ...(settings.data.scale_config ?? {}) });
    setInitialized(true);
  }, [settings.data]);

  const dirty = useMemo(() => {
    if (!settings.data || !initialized) return false;
    return JSON.stringify(config) !== JSON.stringify({ ...DEFAULT_SCALE, ...(settings.data.scale_config ?? {}) });
  }, [config, settings.data, initialized]);

  const save = useMutation({
    mutationFn: () => apiPut<AppSettings>("/settings", { ...settings.data!, scale_config: config }),
    onSuccess: async () => {
      toast.success(text("Configuration du pont-bascule enregistrée", "تم حفظ إعدادات الميزان"));
      await qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (error) => toast.error(errMsg(error)),
  });

  const update = <K extends keyof ScaleConfig>(key: K, value: ScaleConfig[K]) =>
    setConfig((current) => ({ ...current, [key]: value }));

  const valid = !config.enabled
    || (config.protocol.trim().length > 0
      && (config.connection_type === "serial" ? config.serial_port.trim().length > 0
        : config.connection_type === "ethernet" ? config.host.trim().length > 0 && !!config.port
          : true));

  const field = (id: string, label: string, value: string | number, onChange: (value: string) => void, placeholder = "") => (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} className="bg-white" />
    </div>
  );

  return (
    <div className="max-w-5xl space-y-5" data-testid="scale-settings">
      <section className="space-y-5 rounded-2xl border border-sky-200 bg-sky-50/60 p-5">
        <div className="flex items-center gap-3 text-sky-950">
          <div className="grid size-11 place-items-center rounded-xl bg-sky-600 text-white"><Scale className="size-6" /></div>
          <div>
            <h2 className="text-xl font-bold">{text("Balance électronique / pont-bascule", "الميزان الإلكتروني / ميزان الشاحنات")}</h2>
            <p className="text-sm text-sky-800">{text("Un profil commun pour la réception des chargements et les achats d’olives GS.", "إعداد واحد مشترك لاستقبال الحمولات وشراء الزيتون في GS.")}</p>
          </div>
        </div>

        <label className="flex cursor-pointer items-center justify-between gap-4 rounded-xl border border-sky-200 bg-white p-4">
          <span>
            <span className="block font-semibold text-stone-900">{text("Activer le profil du matériel", "تفعيل تعريف الميزان")}</span>
            <span className="text-xs text-stone-500">{text("Active la configuration, pas encore la connexion physique.", "يفعّل الإعدادات فقط، ولا يعني أن الاتصال الفعلي يعمل.")}</span>
          </span>
          <input type="checkbox" checked={config.enabled} onChange={(event) => update("enabled", event.target.checked)} className="size-5 accent-sky-700" />
        </label>

        <div className="grid gap-4 md:grid-cols-2">
          {field("scale-manufacturer", text("Fabricant", "الشركة المصنّعة"), config.manufacturer, (v) => update("manufacturer", v), "Ex. : Dini Argeo")}
          {field("scale-model", text("Modèle", "الطراز"), config.model, (v) => update("model", v), "Ex. : DFW / modèle exact")}
          {field("scale-device-id", text("Identifiant de l’appareil (optionnel)", "معرّف الجهاز (اختياري)"), config.device_id, (v) => update("device_id", v))}
          <div className="space-y-1.5">
            <Label htmlFor="scale-connection">{text("Type de connexion", "نوع الاتصال")}</Label>
            <select id="scale-connection" value={config.connection_type} onChange={(e) => update("connection_type", e.target.value as ScaleConfig["connection_type"])} className="h-10 w-full rounded-md border border-input bg-white px-3 text-sm">
              <option value="serial">Serial / RS-232</option>
              <option value="ethernet">Ethernet / TCP-IP</option>
              <option value="usb">USB</option>
            </select>
          </div>
        </div>

        {config.connection_type === "serial" && <div className="rounded-xl border border-sky-200 bg-white p-4">
          <div className="mb-3 flex items-center gap-2 font-semibold text-sky-900"><Cable className="size-4" /> Serial / RS-232</div>
          <div className="grid gap-4 md:grid-cols-3">
            {field("scale-serial-port", text("Port série", "المنفذ التسلسلي"), config.serial_port, (v) => update("serial_port", v), "COM1 ou /dev/ttyUSB0")}
            {field("scale-baud", text("Baud rate", "سرعة الاتصال"), config.baud_rate, (v) => update("baud_rate", Number(v) || 0))}
            <div className="space-y-1.5"><Label>{text("Bits de données", "بتات البيانات")}</Label><select value={config.data_bits} onChange={(e) => update("data_bits", Number(e.target.value) as 7 | 8)} className="h-10 w-full rounded-md border bg-white px-3 text-sm"><option value={7}>7</option><option value={8}>8</option></select></div>
            <div className="space-y-1.5"><Label>{text("Parité", "التكافؤ")}</Label><select value={config.parity} onChange={(e) => update("parity", e.target.value as ScaleConfig["parity"])} className="h-10 w-full rounded-md border bg-white px-3 text-sm"><option value="none">None</option><option value="even">Even</option><option value="odd">Odd</option></select></div>
            <div className="space-y-1.5"><Label>{text("Bits d’arrêt", "بتات التوقف")}</Label><select value={config.stop_bits} onChange={(e) => update("stop_bits", Number(e.target.value) as 1 | 2)} className="h-10 w-full rounded-md border bg-white px-3 text-sm"><option value={1}>1</option><option value={2}>2</option></select></div>
          </div>
        </div>}

        {config.connection_type === "ethernet" && <div className="rounded-xl border border-sky-200 bg-white p-4">
          <div className="mb-3 flex items-center gap-2 font-semibold text-sky-900"><Network className="size-4" /> Ethernet / TCP-IP</div>
          <div className="grid gap-4 md:grid-cols-2">
            {field("scale-host", text("Adresse IP / hôte", "عنوان IP / المضيف"), config.host, (v) => update("host", v), "192.168.1.100")}
            {field("scale-port", text("Port TCP", "منفذ TCP"), config.port ?? "", (v) => update("port", v ? Number(v) : null), "Ex. : 4001")}
          </div>
        </div>}

        {config.connection_type === "usb" && <div className="rounded-xl border border-sky-200 bg-white p-4 text-sm text-stone-700">
          <div className="mb-2 flex items-center gap-2 font-semibold text-sky-900"><Usb className="size-4" /> USB</div>
          {text("Le port USB et le protocole exact seront détectés par le service local de connexion, si le modèle est pris en charge.", "سيتم تحديد منفذ USB والبروتوكول بواسطة برنامج الاتصال المحلي إذا كان الطراز مدعوماً.")}
        </div>}

        <div className="grid gap-4 md:grid-cols-2">
          {field("scale-protocol", text("Protocole / pilote du fabricant", "بروتوكول / برنامج تشغيل الشركة"), config.protocol, (v) => update("protocol", v), "Ex. : protocole exact indiqué dans le manuel")}
          <div className="space-y-1.5"><Label>{text("Unité de lecture", "وحدة القراءة")}</Label><select value={config.unit} onChange={(e) => update("unit", e.target.value as ScaleConfig["unit"])} className="h-10 w-full rounded-md border bg-white px-3 text-sm"><option value="kg">kg</option><option value="g">g</option><option value="lb">lb</option></select></div>
          <div className="space-y-1.5"><Label>{text("Nombre de décimales", "عدد الأرقام العشرية")}</Label><select value={config.decimal_places} onChange={(e) => update("decimal_places", Number(e.target.value))} className="h-10 w-full rounded-md border bg-white px-3 text-sm"><option value={0}>0</option><option value={1}>1</option><option value={2}>2</option><option value={3}>3</option></select></div>
          <div className="space-y-1.5"><Label>{text("Lectures stables consécutives", "عدد القراءات المستقرة المتتالية")}</Label><Input type="number" min={1} max={20} value={config.stable_readings} onChange={(e) => update("stable_readings", Number(e.target.value))} className="bg-white" /></div>
        </div>

        <div className="flex items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
          <AlertTriangle className="mt-0.5 size-5 shrink-0" />
          <div>
            <p className="font-semibold">{text("État actuel : profil configurable, matériel non connecté", "الحالة الحالية: يمكن تعريف الميزان، لكن الجهاز غير متصل بعد")}</p>
            <p className="mt-1">{text("Enregistrer ces paramètres ne crée pas une connexion. Un service local (bridge) et un pilote testé pour le modèle exact seront nécessaires pour lire le poids réel. Aucun poids ne sera simulé.", "حفظ هذه البيانات لا ينشئ اتصالاً. نحتاج إلى برنامج اتصال محلي وتعريف مجرّب للطراز المحدد لقراءة الوزن الحقيقي. لن يتم إنشاء أي وزن افتراضي.")}</p>
          </div>
        </div>

        {!valid && <p className="text-sm font-medium text-red-700">{text("Renseignez le port ou l’adresse réseau et le protocole requis avant d’activer le profil.", "أدخل المنفذ أو عنوان الشبكة والبروتوكول المطلوب قبل تفعيل التعريف.")}</p>}
        <Button type="button" disabled={!settings.data || !dirty || save.isPending || !valid || (config.enabled && config.baud_rate < 300)} onClick={() => save.mutate()} className="h-11 rounded-xl bg-sky-700 px-7 hover:bg-sky-800">
          <Save className="me-2 size-4" />{save.isPending ? text("Enregistrement…", "جارٍ الحفظ…") : text("Enregistrer la configuration", "حفظ إعدادات الميزان")}
        </Button>
      </section>
    </div>
  );
}
