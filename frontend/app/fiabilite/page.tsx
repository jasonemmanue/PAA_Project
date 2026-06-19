"use client";

import { Card, Placeholder } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { useI18n } from "@/lib/i18n";

export default function PageFiabilite() {
  const { t } = useI18n();

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre={t("fiabilite.title")}
        sousTitre={t("fiabilite.subtitle")}
      />

      <div className="grid gap-fluid-4 md:grid-cols-3">
        <Card titre={t("fiabilite.lastSession")}>
          <p className="text-fluid-xl font-semibold app-text-muted">—</p>
        </Card>
        <Card titre={t("fiabilite.ecartMoyen")}>
          <p className="text-fluid-xl font-semibold app-text-muted">—</p>
        </Card>
        <Card titre={t("fiabilite.tronconsValides")}>
          <p className="text-fluid-xl font-semibold app-text-muted">— / 6</p>
        </Card>
      </div>

      <Card>
        <Placeholder message={t("fiabilite.placeholder")} />
      </Card>
    </div>
  );
}
