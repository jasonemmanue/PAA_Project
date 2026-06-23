/**
 * Parseur GPX côté navigateur — pas de dépendance externe (utilise DOMParser).
 *
 * Lit un fichier `.gpx` et extrait la liste des points `<trkpt>` qui possèdent
 * un horodatage `<time>`. Les autres balises (waypoints, métadonnées) sont
 * ignorées.
 *
 * Utilisé par le composant `<CarteApercu>` de la page Fiabilité pour afficher
 * la trace sur la carte Leaflet AVANT de connaître la réponse du backend.
 */

export interface PointGpx {
  lat: number;
  lon: number;
  /** Horodatage ISO 8601 — peut être null si le `<time>` manquait. */
  horodatage: string | null;
}

export interface TraceGpx {
  nomFichier: string;
  points: PointGpx[];
}

/**
 * Parse un objet `File` (issu d'un `<input type="file">`) → `TraceGpx`.
 *
 * Lève une `Error` si :
 *  - Le contenu n'est pas du XML valide
 *  - Aucun `<trkpt>` n'a été trouvé
 */
/** Parse un texte GPX déjà chargé (depuis un fetch par exemple). */
export function parserGpxTexte(texte: string, nomFichier: string): TraceGpx {
  const parser = new DOMParser();
  const doc = parser.parseFromString(texte, "application/xml");
  const erreur = doc.querySelector("parsererror");
  if (erreur) throw new Error(`GPX invalide : ${erreur.textContent ?? "XML mal formé"}`);
  const trkpts = Array.from(doc.getElementsByTagNameNS("*", "trkpt"));
  if (trkpts.length === 0) throw new Error("Aucun point <trkpt>.");
  const points: PointGpx[] = trkpts.map((node) => ({
    lat: Number(node.getAttribute("lat")),
    lon: Number(node.getAttribute("lon")),
    horodatage: node.getElementsByTagNameNS("*", "time")[0]?.textContent ?? null,
  })).filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon));
  return { nomFichier, points };
}

export async function parserGpxFichier(fichier: File): Promise<TraceGpx> {
  const texte = await fichier.text();
  const parser = new DOMParser();
  const doc = parser.parseFromString(texte, "application/xml");
  const erreur = doc.querySelector("parsererror");
  if (erreur) {
    throw new Error(`GPX invalide : ${erreur.textContent ?? "XML mal formé"}`);
  }
  // On utilise `getElementsByTagNameNS("*", "trkpt")` pour rester
  // **agnostique au namespace** : les GPX produits par notre script Python
  // déclarent `xmlns="http://www.topografix.com/GPX/1/1"`, et
  // `getElementsByTagName("trkpt")` ne matcherait alors AUCUN élément.
  const trkpts = Array.from(doc.getElementsByTagNameNS("*", "trkpt"));
  if (trkpts.length === 0) {
    throw new Error("Le GPX ne contient aucun point <trkpt>.");
  }
  const points: PointGpx[] = trkpts.map((node) => {
    const lat = Number(node.getAttribute("lat"));
    const lon = Number(node.getAttribute("lon"));
    const timeNode = node.getElementsByTagNameNS("*", "time")[0];
    return {
      lat,
      lon,
      horodatage: timeNode?.textContent ?? null,
    };
  }).filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon));

  return {
    nomFichier: fichier.name,
    points,
  };
}
