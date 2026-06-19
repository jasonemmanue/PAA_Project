"use client";

import { Card, Placeholder } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { useI18n } from "@/lib/i18n";

export default function PageAdministration() {
  const { t } = useI18n();

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre={t("administration.title")}
        sousTitre={t("administration.subtitle")}
      />

      <div className="grid gap-fluid-4 md:grid-cols-2">
        <Card titre={t("administration.collecteStatus")}>
          <Placeholder message={t("administration.placeholder")} />
        </Card>
        <Card titre={t("administration.addTroncon")}>
          <Placeholder message={t("administration.placeholder")} />
        </Card>
      </div>

      <Card titre={t("administration.exportData")}>
        <Placeholder message={t("administration.placeholder")} />
      </Card>
    </div>
  );
}
