/**
 * Décodeur du format Google Polyline (précision 5), utilisé par OSRM
 * et par notre backend pour stocker la géométrie des tronçons.
 *
 * Algorithme officiel :
 *   https://developers.google.com/maps/documentation/utilities/polylinealgorithm
 *
 * Retour : tableau de couples `[lat, lon]` (ordre lat-lon, cohérent avec Leaflet).
 */

export function decoderPolyline(encoded: string, precision = 5): [number, number][] {
  const facteur = Math.pow(10, precision);
  const coordonnees: [number, number][] = [];
  let index = 0;
  let lat = 0;
  let lon = 0;

  while (index < encoded.length) {
    // ---- Décodage delta latitude
    let resultat = 0;
    let decalage = 0;
    let octet: number;
    do {
      if (index >= encoded.length) return coordonnees;
      octet = encoded.charCodeAt(index++) - 63;
      resultat |= (octet & 0x1f) << decalage;
      decalage += 5;
    } while (octet >= 0x20);
    const deltaLat = resultat & 1 ? ~(resultat >> 1) : resultat >> 1;
    lat += deltaLat;

    // ---- Décodage delta longitude
    resultat = 0;
    decalage = 0;
    do {
      if (index >= encoded.length) return coordonnees;
      octet = encoded.charCodeAt(index++) - 63;
      resultat |= (octet & 0x1f) << decalage;
      decalage += 5;
    } while (octet >= 0x20);
    const deltaLon = resultat & 1 ? ~(resultat >> 1) : resultat >> 1;
    lon += deltaLon;

    coordonnees.push([lat / facteur, lon / facteur]);
  }

  return coordonnees;
}
