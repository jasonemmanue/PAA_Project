/**
 * Augmentation du module `leaflet` pour exposer `L.heatLayer` typé.
 *
 * Ce fichier DOIT être un module (avoir au moins un import) pour que
 * `declare module "leaflet"` agisse comme une augmentation et non comme
 * un redéfinition (qui écraserait @types/leaflet).
 */
import "leaflet";

declare module "leaflet" {
  type HeatLatLngTuple = [number, number] | [number, number, number];

  interface HeatLayerOptions {
    minOpacity?: number;
    maxZoom?: number;
    max?: number;
    radius?: number;
    blur?: number;
    gradient?: Record<number, string>;
  }

  interface HeatLayer {
    setLatLngs(latlngs: HeatLatLngTuple[]): this;
    addLatLng(latlng: HeatLatLngTuple): this;
    setOptions(options: HeatLayerOptions): this;
    redraw(): this;
    addTo(map: Map): this;
    remove(): this;
  }

  function heatLayer(
    latlngs: HeatLatLngTuple[],
    options?: HeatLayerOptions,
  ): HeatLayer;
}
