# ============================================================
# Préparation de l'extrait OSRM (Côte d'Ivoire, profil voiture)
# ------------------------------------------------------------
# Equivalent PowerShell de prepare.sh pour les postes Windows.
# A exécuter UNE SEULE FOIS avant le premier `docker compose up`.
# ============================================================

$ErrorActionPreference = 'Stop'

$DataDir   = $PSScriptRoot
$PbfUrl    = 'https://download.geofabrik.de/africa/ivory-coast-latest.osm.pbf'
$PbfFile   = 'ivory-coast-latest.osm.pbf'
$OsrmImage = 'osrm/osrm-backend:latest'

Write-Host ">>> Dossier de données : $DataDir"

# 1. Téléchargement de l'extrait OSM s'il est absent
$PbfPath = Join-Path $DataDir $PbfFile
if (-not (Test-Path $PbfPath)) {
    Write-Host ">>> Téléchargement de l'extrait Côte d'Ivoire depuis Geofabrik"
    Invoke-WebRequest -Uri $PbfUrl -OutFile $PbfPath
} else {
    Write-Host ">>> Extrait déjà présent, étape de téléchargement ignorée."
}

# Sous Windows, Docker Desktop monte les chemins via /host_mnt ou directement.
# La forme `${DataDir}:/data` fonctionne dans PowerShell avec Docker Desktop.
$VolumeMount = "$($DataDir):/data"

# 2. osrm-extract avec le profil voiture
Write-Host ">>> Étape 1/3 : osrm-extract (profil car)"
docker run --rm -t -v $VolumeMount $OsrmImage `
    osrm-extract -p /opt/car.lua "/data/$PbfFile"
if ($LASTEXITCODE -ne 0) { throw "osrm-extract a échoué." }

# 3. osrm-partition
Write-Host ">>> Étape 2/3 : osrm-partition"
docker run --rm -t -v $VolumeMount $OsrmImage `
    osrm-partition "/data/ivory-coast-latest.osrm"
if ($LASTEXITCODE -ne 0) { throw "osrm-partition a échoué." }

# 4. osrm-customize
Write-Host ">>> Étape 3/3 : osrm-customize"
docker run --rm -t -v $VolumeMount $OsrmImage `
    osrm-customize "/data/ivory-coast-latest.osrm"
if ($LASTEXITCODE -ne 0) { throw "osrm-customize a échoué." }

Write-Host ">>> Préparation OSRM terminée. Vous pouvez lancer : docker compose up"
