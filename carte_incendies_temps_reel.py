"""
Carte mondiale des incendies en temps reel - NASA FIRMS
==========================================================

Ce script telecharge les detections satellite de feux actifs des
dernieres 24h et genere une carte interactive HTML (Leaflet via Folium)
avec des cercles dont la taille et la couleur dependent de l'intensite
du feu (FRP - Fire Radiative Power, en megawatts).

INSTALLATION
------------
pip install requests pandas folium

UTILISATION
-----------
1. Recupere une cle gratuite sur https://firms.modaps.eosdis.nasa.gov/api/area/
2. Remplace MAP_KEY ci-dessous par ta cle
3. Lance : python carte_incendies_temps_reel.py
4. Ouvre le fichier carte_incendies.html genere dans ton navigateur

Pour automatiser une mise a jour reguliere, tu peux planifier ce script
avec cron (Linux/Mac) ou le planificateur de taches (Windows).
"""

import os
import requests
import pandas as pd
import folium
from folium.plugins import MarkerCluster

# ---------------------------------------------------------------------
# CONFIGURATION - a personnaliser
# ---------------------------------------------------------------------
# La cle est lue depuis la variable d'environnement MAP_KEY (definie comme
# secret GitHub Actions) - jamais ecrite en clair ici, car ce fichier est
# destine a un depot public.
MAP_KEY = os.environ.get("MAP_KEY", "TA_CLE_API_ICI")
AREA = "-180,-90,180,90"            # zone couverte : monde entier (min_lon,min_lat,max_lon,max_lat)
DAY_RANGE = 1                       # 1 = dernieres 24h (max 10)
OUTPUT_FILE = "docs/index.html"     # dossier lu par GitHub Pages

# On interroge plusieurs capteurs plutot qu'un seul : selon l'heure, un
# satellite peut ne pas encore avoir de donnees traitees pour aujourd'hui
# (decalage de quelques heures), un autre si. Combiner les sources evite
# de se retrouver avec une carte vide a cause d'un seul capteur en retard.
SOURCES = ["VIIRS_NOAA20_NRT", "VIIRS_SNPP_NRT", "MODIS_NRT"]


def telecharger_une_source(source):
    """Recupere le CSV d'une source donnee. Renvoie un DataFrame vide si rien."""
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{source}/{AREA}/{DAY_RANGE}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    if response.text.lower().startswith(("invalid", "error")):
        print(f"  {source} : reponse d'erreur -> {response.text[:120]}")
        return pd.DataFrame()

    from io import StringIO
    df = pd.read_csv(StringIO(response.text))
    print(f"  {source} : {len(df)} point(s) chaud(s)")
    df["source"] = source
    return df


def telecharger_donnees():
    """Recupere et fusionne le CSV des detections de feux pour toutes les SOURCES."""
    print("Telechargement des donnees NASA FIRMS...")
    frames = [telecharger_une_source(s) for s in SOURCES]
    frames = [f for f in frames if not f.empty]
    df = pd.concat(frames, ignore_index=True)

    if df.empty:
        raise ValueError(
            "Aucune donnee recuperee sur aucune source. Verifie ta cle MAP_KEY "
            "et ton quota (5000 requetes / 10 min max)."
        )

    print(f"Total : {len(df)} points chauds detectes (avant deduplication).")
    return df


def couleur_et_rayon(frp, confidence):
    """Determine la couleur et le rayon du cercle selon l'intensite du feu."""
    # FRP en MW : on definit des seuils empiriques
    if frp >= 100:
        couleur = "#A32D2D"   # rouge fonce - tres intense
        rayon = 10
    elif frp >= 30:
        couleur = "#E24B4A"   # rouge - intense
        rayon = 7
    elif frp >= 10:
        couleur = "#EF9F27"   # orange - modere
        rayon = 5
    else:
        couleur = "#FAC775"   # jaune - faible
        rayon = 3
    return couleur, rayon


def construire_carte(df):
    """Construit la carte Folium avec un cercle par detection."""
    carte = folium.Map(location=[20, 0], zoom_start=2, tiles="CartoDB positron")
    cluster = MarkerCluster(name="Incendies actifs").add_to(carte)

    for _, row in df.iterrows():
        frp = row.get("frp", 0) or 0
        confidence = row.get("confidence", "n")
        couleur, rayon = couleur_et_rayon(frp, confidence)

        popup_html = (
            f"<b>FRP :</b> {frp} MW<br>"
            f"<b>Confiance :</b> {confidence}<br>"
            f"<b>Date :</b> {row.get('acq_date', 'n/a')} {row.get('acq_time', '')}<br>"
            f"<b>Lat/Lon :</b> {row['latitude']:.2f}, {row['longitude']:.2f}"
        )

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=rayon,
            color=couleur,
            fill=True,
            fill_color=couleur,
            fill_opacity=0.7,
            weight=0.5,
            popup=folium.Popup(popup_html, max_width=250),
        ).add_to(cluster)

    folium.LayerControl().add_to(carte)
    return carte


def main():
    if MAP_KEY == "TA_CLE_API_ICI" or not MAP_KEY.strip():
        print("!! N'oublie pas de remplacer MAP_KEY par ta propre cle API !!")
        print("   Obtiens-la gratuitement sur https://firms.modaps.eosdis.nasa.gov/api/area/")
        return

    df = telecharger_donnees()
    carte = construire_carte(df)
    os.makedirs(os.path.dirname(OUTPUT_FILE) or ".", exist_ok=True)
    carte.save(OUTPUT_FILE)
    print(f"Carte generee : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
