/**
 * Déclaration ambiante du module `leaflet.heat` (pas de @types officiels).
 *
 * Ce fichier ne doit pas avoir d'`import`/`export` au top-level — sinon
 * TypeScript le considère comme un module et `declare module` cesse
 * d'être une déclaration ambiante.
 */
declare module "leaflet.heat" {
  // Pas d'export : le plugin s'enregistre par effet de bord sur L.
}
