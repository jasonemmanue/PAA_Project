"use client";

import { Card, Placeholder } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { useI18n } from "@/lib/i18n";

export default function PageIndicateurs() {
  const { t } = useI18n();

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre={t("indicateurs.title")}
        sousTitre={t("indicateurs.subtitle")}
      />

      {/* 3 cartes KPI — empilées sur mobile, en ligne sur tablette+ */}
      <div className="grid gap-fluid-4 md:grid-cols-3">
        <Card titre={t("indicateurs.tti")} description={t("indicateurs.ttiTooltip")}>
          <p className="mt-2 text-fluid-3xl font-bold text-paa-navy-700 dark:text-paa-blue-200">
            —
          </p>
        </Card>
        <Card titre={t("indicateurs.pti")} description={t("indicateurs.ptiTooltip")}>
          <p className="mt-2 text-fluid-3xl font-bold text-paa-navy-700 dark:text-paa-blue-200">
            —
          </p>
        </Card>
        <Card titre={t("indicateurs.bti")} description={t("indicateurs.btiTooltip")}>
          <p className="mt-2 text-fluid-3xl font-bold text-paa-navy-700 dark:text-paa-blue-200">
            —
          </p>
        </Card>
      </div>

      {/* Zone graphiques */}
      <Card>
        <Placeholder message={t("indicateurs.placeholder")} />
      </Card>
    </div>
  );
}
