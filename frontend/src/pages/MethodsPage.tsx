import { useI18n } from "../i18n";

export default function MethodsPage() {
  const { t } = useI18n();
  return (
    <div className="page prose">
      <h1>{t("methods.title")}</h1>
      <h2>{t("sum.proj.title")}</h2>
      <p>{t("sum.proj.body")}</p>
      <h2>{t("how.title")}</h2>
      <p>{t("how.body")}</p>
    </div>
  );
}
