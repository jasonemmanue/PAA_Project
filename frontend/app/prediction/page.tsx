"use client";

import { Card, Placeholder } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { useI18n } from "@/lib/i18n";

export default function PagePrediction() {
  const { t } = useI18n();

  return (
    <div className="flex flex-col gap-fluid-4">
      <PageHeader
        titre={t("prediction.title")}
        sousTitre={t("prediction.subtitle")}
      />

      <Card>
        {/* Formulaire de simulation — empilé sur mobile, en ligne sur tablette+ */}
        <form className="grid gap-3 md:grid-cols-4 md:items-end">
          <label className="flex flex-col gap-1 text-fluid-sm font-medium">
            {t("prediction.selectTroncon")}
            <select
              className="rounded-md border app-border app-surface px-3 py-2
                         text-fluid-base focus:outline-none focus:ring-2 focus:ring-paa-blue-400"
              disabled
            >
              <option>—</option>
            </select>
          </label>

          <label className="flex flex-col gap-1 text-fluid-sm font-medium">
            {t("prediction.selectDate")}
            <input
              type="date"
              disabled
              className="rounded-md border app-border app-surface px-3 py-2
                         text-fluid-base focus:outline-none focus:ring-2 focus:ring-paa-blue-400"
            />
          </label>

          <label className="flex flex-col gap-1 text-fluid-sm font-medium">
            {t("prediction.selectTime")}
            <input
              type="time"
              disabled
              className="rounded-md border app-border app-surface px-3 py-2
                         text-fluid-base focus:outline-none focus:ring-2 focus:ring-paa-blue-400"
            />
          </label>

          <button type="button" disabled className="btn-primary md:h-[42px]">
            {t("prediction.estimate")}
          </button>
        </form>
      </Card>

      <Card>
        <Placeholder message={t("prediction.placeholder")} />
      </Card>
    </div>
  );
}
