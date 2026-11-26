import { useNavigate } from "react-router-dom";
import { ArrowLeft, BookOpen, CircleHelp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";

const sections = [
  {
    ar: "تطبيق Oro Verde الأساسي", fr: "Application Oro Verde — gestion de la maâsra",
    arDescription: "إدارة العمل اليومي للمعصرة ومتابعة الحرفاء والحمولات والعصر.",
    frDescription: "Gérer l’activité quotidienne de la maâsra, les clients, les réceptions d’olives et le pressage.",
    items: [
      ["الرئيسية", "Accueil", "لوحة متابعة مختصرة تعرض نشاط المعصرة ومؤشرات العمل اليومية.", "Tableau de bord présentant l’activité de la maâsra et les principaux indicateurs du jour."],
      ["إضافة حمولة", "Ajouter une réception", "تسجيل وصول حمولة زيتون جديدة وربطها بالحريف وبياناتها قبل بدء العصر.", "Enregistrer l’arrivée d’une nouvelle charge d’olives et l’associer au client avant le pressage."],
      ["البحث", "Recherche", "العثور على حمولة أو سجل سابق باستعمال المعلومات أو الرمز المتاح.", "Retrouver une réception ou un ancien dossier à l’aide des informations ou du code disponible."],
      ["الحمولات", "Réceptions", "متابعة الحمولات المسجلة وحالة كل حمولة ومراحل مرورها بالمعصرة.", "Consulter les réceptions enregistrées, leur statut et les étapes de leur traitement."],
      ["المخبر", "Laboratoire", "تسجيل نتائج التحاليل ومتابعة تحاليل الزيتون أو الزيت.", "Saisir les résultats et suivre les analyses des olives ou de l’huile."],
      ["الحرفاء", "Clients", "إدارة بيانات الحرفاء والرجوع إلى معلوماتهم.", "Gérer les fiches clients et consulter leurs informations."],
      ["التقارير", "Rapports", "عرض تقارير نشاط المعصرة. يمكن تحديد الفترة والعامل، ثم تصدير التقرير بصيغة PDF أو Excel حسب التقرير المتاح.", "Consulter les rapports d’activité de la maâsra. Sélectionnez la période et, selon le rapport, l’employé, puis exportez en PDF ou Excel."],
      ["الفواتير", "Factures", "عرض فواتير خدمات العصر ومتابعة المبالغ المسجلة.", "Consulter les factures des prestations de pressage et suivre les montants."],
      ["الرسائل", "Messages", "متابعة سجل الرسائل والإشعارات المرسلة.", "Consulter l’historique des messages et notifications envoyés."],
      ["الإلغاءات", "Annulations", "الاطلاع على العمليات الملغاة وأسباب الإلغاء.", "Consulter les opérations annulées et leurs motifs."],
      ["شاشة التلفاز", "Écran TV", "إدارة المحتوى المعروض على شاشة المعصرة.", "Gérer les contenus affichés sur l’écran de la maâsra."],
      ["الإعدادات", "Paramètres", "ضبط بيانات المعصرة والتعريفة والموسم والمستخدمين والإعدادات المتاحة.", "Configurer les informations de la maâsra, les tarifs, la campagne, les utilisateurs et les autres paramètres."],
    ],
  },
  {
    ar: "قسم GS — الإدارة التجارية", fr: "Module GS — Gestion commerciale",
    arDescription: "إدارة شراء الزيتون والمخزون والإنتاج والجودة والتخزين والبيع والتتبع التجاري.",
    frDescription: "Gérer les achats d’olives, les stocks, la production, la qualité, le stockage, les ventes et la traçabilité.",
    items: [
      ["نظرة عامة", "Vue générale", "ملخص المخزون والكميات وحالة الوحدة التجارية. يمكن اختيار خزان لمراجعة الحركات المرتبطة به.", "Vue synthétique des stocks, des quantités et de l’état du module. Sélectionnez une cuve pour consulter les opérations qui lui sont liées."],
      ["المزوّدون", "Fournisseurs", "تسجيل المزوّدين وإدارة بياناتهم لعمليات شراء الزيتون.", "Enregistrer les fournisseurs et gérer leurs coordonnées pour les achats d’olives."],
      ["شراء الزيتون", "Achats d’olives", "إنشاء عمليات شراء الزيتون وتسجيل الكميات والأسعار واعتماد الاستلام.", "Créer les achats d’olives, saisir les quantités et les prix, puis valider la réception."],
      ["الدفعات", "Lots", "متابعة دفعات الزيتون والزيت وأكواد التتبع والمالك والموقع والرصيد.", "Suivre les lots d’olives et d’huile, leurs codes de traçabilité, propriétaires, emplacements et soldes."],
      ["الجودة", "Qualité", "متابعة التحاليل وقرارات قبول الدفعات أو رفضها. لا تصبح دفعة الزيت جاهزة للبيع قبل اعتماد الجودة.", "Suivre les analyses et les décisions d’acceptation ou de rejet. Un lot d’huile ne devient disponible à la vente qu’après validation qualité."],
      ["الإنتاج", "Production", "تسجيل كمية الزيتون المستهلكة وكمية الزيت الناتجة والخزان الذي استقبل الإنتاج.", "Enregistrer la quantité d’olives consommée, l’huile obtenue et la cuve de réception."],
      ["الحركات", "Mouvements", "عرض حركات دخول المخزون وخروجه وتغيّر كمياته ومواقعه.", "Consulter les entrées, sorties et changements de quantités ou d’emplacements du stock."],
      ["التحويلات", "Transferts", "تسجيل نقل المخزون بين المواقع أو تغيير مالكه مع الاحتفاظ بسجل الحركة.", "Enregistrer le déplacement du stock entre emplacements ou un changement de propriétaire, avec conservation de l’historique."],
      ["المشترون", "Acheteurs", "إدارة المشترين وبياناتهم ومتابعة حساباتهم التجارية.", "Gérer les acheteurs, leurs coordonnées et leurs comptes commerciaux."],
      ["التقارير", "Rapport", "عرض تقرير الحركات والعمليات التجارية لمراجعة ما حدث في المخزون.", "Consulter les mouvements et opérations commerciales pour vérifier l’historique du stock."],
      ["أمانة الحرفاء", "Garde des clients", "تسجيل زيتون يملكه الحريف ويضعه لدى المعصرة، ثم تسجيل الزيت الناتج الذي يبقى ملكًا له. تتيح متابعة الاستلام والتسليم وكشف رصيد الأمانة. ليست عملية شراء ولا بيع ولا تنشئ فاتورة بيع.", "Enregistrer les olives appartenant au client et confiées à la maâsra, puis l’huile obtenue qui reste sa propriété. Suivre les réceptions, les restitutions et le solde en garde. Ce n’est ni un achat ni une vente et aucune facture de vente n’est créée."],
      ["المبيعات", "Ventes", "تسجيل بيع الزيت للمشتري من مخزون المعصرة ومتابعة الكميات والفواتير والمدفوعات والمرتجعات.", "Enregistrer la vente d’huile issue du stock de la maâsra et suivre les quantités, factures, paiements et retours."],
      ["الفواتير", "Factures", "عرض فواتير GS ومتابعة المبالغ المدفوعة والمتبقية وكشوف حساب المشترين.", "Consulter les factures GS, les montants payés ou restants et les relevés des acheteurs."],
      ["الخزانات", "Cuves", "متابعة الخزانات وسعاتها ومخزون الزيت الموجود في كل خزان.", "Suivre les cuves, leurs capacités et les quantités d’huile stockées dans chacune."],
      ["سجل التدقيق", "Audit", "مراجعة سجل العمليات والتعديلات والإلغاءات لمعرفة من قام بالعملية ومتى.", "Consulter l’historique des opérations, modifications et annulations pour savoir qui a effectué chaque action et à quel moment."],
      ["صلاحيات العمال", "Droits des employés", "تحديد ما يمكن لكل عامل الاطلاع عليه أو تسجيله أو تعديله أو اعتماده.", "Définir les informations que chaque employé peut consulter, saisir, modifier ou valider."],
      ["شراء الزيتون من الحرفاء", "Achat auprès des Clients", "تسجيل شراء حمولة زيتون من حريف وتحويل ملكيتها إلى المعصرة. هذا يختلف عن أمانة الحرفاء: الشراء ينقل الملكية، أما الأمانة فتبقي الملكية للحريف.", "Enregistrer l’achat d’une charge d’olives à un client et transférer sa propriété à la huilerie. À distinguer de la garde des clients, où le produit reste la propriété du client."],
      ["شراء الزيت الجاهز من المزوّدين", "Achat d’huile", "تسجيل شراء زيت جاهز من المزوّد في المشتريات. تسجيل الشراء لا يضيف الكمية تلقائياً إلى الخزان؛ إدخال الزيت إلى الخزان عملية مستقلة لاحقة.", "Enregistrer l’achat d’huile déjà prête auprès d’un fournisseur. L’achat ne crée pas automatiquement une entrée en cuve : la réception en cuve est une opération distincte à saisir ensuite."],
    ],
  },
  {
    ar: "العمال والحضور والأجور", fr: "Personnel, pointage et paie",
    arDescription: "إدارة سجل العمال والحضور اليومي وحساب الأجور والتسبيقات.",
    frDescription: "Gérer le registre des employés, les pointages quotidiens et le calcul des salaires et avances.",
    items: [
      ["سجل العمال", "Registre des employés", "إضافة العامل وتعديل بياناته مثل الاسم والهاتف والعنوان والأجر ونوعه. سجل العمال مستقل عن حسابات الدخول إلى التطبيق. إذا كانت للعامل دفعات مسجلة، استعمل الأرشفة بدلاً من الحذف النهائي للحفاظ على سجل الأجر والخزينة.", "Ajouter ou modifier un employé : nom, téléphone, adresse, salaire et type de salaire. Le registre du personnel est indépendant des comptes de connexion. Si des paiements existent, archivez l’employé au lieu de le supprimer afin de préserver l’historique de paie et de trésorerie."],
      ["Pointage du jour", "Pointage du jour", "سجّل الدخول عند بداية العمل، ثم الخروج عند انتهائه. زر «Pause» يضع العامل في حالة راحة، ويجب تسجيل العودة عند استئناف العمل. يمكن أن تمتد الوردية بعد منتصف الليل؛ تُحسب المدة بين تاريخي الدخول والخروج وتُنسب إلى يوم الدخول.", "Enregistrez l’arrivée au début du travail, puis le départ à la fin. Le bouton « Pause » met l’employé en pause; enregistrez sa reprise lorsqu’il revient. Un quart peut traverser minuit : sa durée est calculée entre les deux dates et rattachée au jour d’entrée."],
      ["حساب ساعات العمل", "Calcul des heures", "تُخصم فترات الراحة المسجلة يدوياً فقط. الوردية التي لم يُسجل خروجها لا تدخل في مجموع الساعات أو الأجر حتى تُغلق. عدم وجود تسجيل حضور لا يعني غياباً؛ الغياب يحتاج إلى تأكيد يدوي.", "Seules les pauses enregistrées manuellement sont déduites. Un quart sans heure de départ n’entre pas dans le total des heures ni dans le calcul du salaire tant qu’il n’est pas clôturé. L’absence de pointage ne signifie pas une absence : celle-ci doit être confirmée manuellement."],
      ["التسبيقات والاستخلاص", "Avances et paiements", "يمكن دفع تسبيق أو استخلاص العامل في أي وقت، حتى وسط الشهر. يظهر مجموع التسبيقات و«Reste à payer». لا يجوز أن يتجاوز التسبيق الأجر المكتسب غير المدفوع. طرق الدفع: Espèces وChèque وVirement. لا تُسجل حركة خروج في الخزينة إلا عند الدفع الفعلي.", "Vous pouvez verser une avance ou régler le salarié à tout moment, y compris en milieu de mois. Le total des avances et le « Reste à payer » sont affichés. Une avance ne peut pas dépasser le salaire acquis et non payé. Modes : Espèces, Chèque et Virement. La sortie de trésorerie n’est enregistrée qu’au moment du paiement réel."],
      ["قاعدة احتساب الأجر", "Règles de calcul du salaire", "الأجر اليومي يُحسب بنسبة ساعات العمل على أساس 8 ساعات لليوم، والأجر بالساعة حسب الساعات الفعلية. الأجر الشهري لا يُحتسب حالياً لعدم تحديد قاعدة تحويله إلى أجر يومي أو ساعي. راجع الورديات غير المكتملة قبل تسجيل أي دفعة.", "Le salaire journalier est proratisé sur une base de 8 heures; le salaire horaire est calculé selon les heures réelles. Le salaire mensuel n’est pas calculé actuellement, faute de règle de conversion en taux journalier ou horaire. Vérifiez les quarts incomplets avant tout paiement."],
      ["تقرير الحضور", "Rapport de pointage", "اختر فترة من تاريخ إلى تاريخ، ويمكن تصفية النتائج حسب العامل. التقرير يعرض أيام وساعات العمل ويمكن طباعته أو حفظه PDF.", "Choisissez une période de début à fin et, au besoin, filtrez par employé. Le rapport présente les jours et heures travaillés et peut être imprimé ou enregistré en PDF."]
    ],
  },
  {
    ar: "المحاسبة والخزينة", fr: "Comptabilité et trésorerie",
    arDescription: "متابعة المداخيل والمصاريف والمقبوضات والمدفوعات وأرصدة الصندوق والبنوك.",
    frDescription: "Suivre les revenus, dépenses, encaissements, paiements et soldes de caisse et de banque.",
    items: [
      ["Trésorerie/Caisse", "Trésorerie/Caisse", "متابعة الحركات المالية الداخلة والخارجة وربط كل حركة بحساب الصندوق أو البنك المناسب. راجع الحساب والتاريخ وطريقة الدفع قبل تسجيل العملية.", "Consulter les mouvements financiers entrants et sortants et les associer au compte de caisse ou bancaire approprié. Vérifiez le compte, la date et le mode de paiement avant l’enregistrement."],
      ["Comptes de trésorerie/caisse et banques", "Comptes de trésorerie/caisse et banques", "إضافة حسابات الصندوق والبنوك ومراجعة أرصدتها. يجب إعداد الرصيد الافتتاحي يدوياً للحساب الجديد؛ لا تعتبر عبارة «Non configuré» رصيداً صفرياً مؤكداً.", "Ajouter les comptes de caisse et les comptes bancaires, puis consulter leurs soldes. Le solde initial d’un nouveau compte doit être configuré manuellement; « Non configuré » ne signifie pas qu’un solde nul a été confirmé."],
      ["مطابقة الشيكات", "Rapprochement des chèques", "في العمليات التجارية العادية، قد يبقى الشيك في انتظار المطابقة إلى حين تأكيد تحصيله من البنك. أما شيكات أجور العمال فتُعامل وفق إجراء الأجور المعتمد عند تسجيلها. لا تخلط بين الحالتين.", "Pour les opérations commerciales ordinaires, un chèque peut rester en attente de rapprochement jusqu’à confirmation de son encaissement bancaire. Les chèques de paie suivent le traitement prévu dans le module du personnel. Ne confondez pas ces deux cas."],
      ["المصاريف والمداخيل", "Dépenses et revenus", "سجّل المصروف أو المقبوض مع المبلغ والتاريخ وطريقة الدفع والحساب المرتبط. يجب أن تعكس حركة الخزينة ما دُفع أو قُبض فعلياً، لا مجرد مبلغ متوقع.", "Enregistrez chaque dépense ou encaissement avec son montant, sa date, son mode de paiement et le compte associé. Le mouvement de trésorerie doit refléter un montant réellement payé ou reçu, et non une simple somme prévue."]
    ],
  },
];

export default function Help() {
  const navigate = useNavigate();
  const { lang } = useI18n();
  const ar = lang === "ar";
  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid size-12 place-items-center rounded-2xl bg-emerald-100 text-emerald-800"><CircleHelp className="size-7" /></div>
          <div>
            <h1 className="text-3xl font-bold text-stone-900">{ar ? "مركز المساعدة" : "Centre d’aide"}</h1>
            <p className="mt-1 text-sm text-stone-600">{ar ? "شرح وظائف التطبيق" : "Guide des fonctions de l’application"}</p>
          </div>
        </div>
        <Button type="button" variant="outline" onClick={() => navigate("/")}>
          <ArrowLeft className="size-4 rtl:rotate-180" /> {ar ? "العودة إلى التطبيق" : "Retour à l’application"}
        </Button>
      </div>
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm leading-7 text-emerald-950">
        <div className="mb-1 flex items-center gap-2 font-bold"><BookOpen className="size-5" /> {ar ? "كيف تستعمل هذه الصفحة؟" : "Comment utiliser cette page ?"}</div>
        <p dir={ar ? "rtl" : "ltr"}>{ar ? "اختر القسم الذي تريد فهمه واقرأ شرحه. أسماء الصفحات مذكورة كما تظهر في التطبيق." : "Choisissez la rubrique souhaitée et lisez son explication. Les noms des pages sont repris tels qu’ils apparaissent dans l’application."}</p>
      </div>
      {sections.map((section) => (
        <section key={section.ar} className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
          <div className="border-b border-stone-100 bg-stone-50 px-5 py-4">
            <h2 className="text-xl font-bold text-stone-900">{ar ? section.ar : section.fr}</h2>
            <p dir={ar ? "rtl" : "ltr"} className="mt-1 text-sm leading-6 text-stone-600">{ar ? section.arDescription : section.frDescription}</p>
          </div>
          <div className="divide-y divide-stone-100">
            {section.items.map(([arName, frName, arDescription, frDescription]) => (
              <div key={frName} dir={ar ? "rtl" : "ltr"} className="px-5 py-4">
                <h3 className="font-semibold text-emerald-900">{ar ? arName : frName}</h3>
                <p className="mt-1 text-sm leading-7 text-stone-700">{ar ? arDescription : frDescription}</p>
              </div>
            ))}
          </div>
        </section>
      ))}
      <p className="text-center text-xs leading-6 text-stone-500" dir={ar ? "rtl" : "ltr"}>{ar ? "إذا لم تجد وظيفة أو كان الشرح لا يطابق ما يظهر في التطبيق، فلا تنفّذ عملية غير واضحة قبل مراجعة المسؤول." : "Si une fonction n’est pas expliquée ou si le comportement affiché est différent, demandez confirmation au responsable avant d’effectuer une opération incertaine."}</p>
    </div>
  );
}
