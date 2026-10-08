import os
import sys
import json
import socket
import webbrowser
import sqlite3
from datetime import datetime
from threading import Timer
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

# ================================================================
# CONFIGURATION
# ================================================================

def obtenir_dossier_application():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

DOSSIER_APP = obtenir_dossier_application()
DB_PATH = os.path.join(DOSSIER_APP, "base_donnees_spc.db")

# Remplacez ce chemin par le chemin UNC réel si possible.
# Exemple : r"\\serveur\partage\Consignes\DFN\Extrusion\SPC\Image"
DOSSIER_IMAGES_RESEAU = r"W:\Consignes\DFN\Extrusion\SPC\Image"

app = Flask(__name__)
CORS(app)


def initialiser_bdd():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mesures_spc (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_saisie TEXT,
            num_filiere TEXT,
            of TEXT,
            donnees_json TEXT
        )
    """)
    conn.commit()
    conn.close()


def valeur(mesures, *noms, defaut=""):
    """Récupère une valeur quelle que soit la casse du nom reçu."""
    for nom in noms:
        if nom in mesures and mesures[nom] is not None:
            return str(mesures[nom]).strip()
    return defaut


@app.route("/enregistrer-spc", methods=["POST"])
def enregistrer_spc():
    try:
        data = request.get_json(silent=True) or {}
        mesures = data.get("mesures", {})
        if not isinstance(mesures, dict) or not mesures:
            return jsonify({"status": "error", "message": "Aucune mesure reçue."}), 400

        num_filiere = valeur(mesures, "filiere", "Filiere", defaut="Inconnu")
        of = valeur(mesures, "of", "OF", defaut="Inconnu")
        date_saisie = valeur(
            mesures,
            "date",
            "Date_Heure",
            defaut=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        )

        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO mesures_spc (date_saisie, num_filiere, of, donnees_json)
            VALUES (?, ?, ?, ?)
        """, (
            date_saisie,
            num_filiere,
            of,
            json.dumps(mesures, ensure_ascii=False)
        ))
        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Données enregistrées !"})
    except Exception as exc:
        print(f"Erreur d'enregistrement : {exc}")
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/")
def index():
    return send_from_directory(DOSSIER_APP, "SPC.html")


@app.route("/historique")
@app.route("/historique_SPC.html")
def historique():
    return send_from_directory(DOSSIER_APP, "historique_SPC.html")


@app.route("/articles.js")
def articles():
    # Cette route manquait dans votre fichier actuel.
    # Sans elle, articleMapping et cotesControle ne sont pas chargés.
    return send_from_directory(DOSSIER_APP, "articles.js", mimetype="application/javascript")


@app.route("/images/<path:nom_image>")
def servir_images(nom_image):
    """Recherche l'image par numéro de filière dans plusieurs dossiers."""
    # On ne conserve que le nom de fichier, jamais un chemin transmis par le navigateur.
    nom_base = os.path.splitext(os.path.basename(nom_image))[0].strip()
    extensions = [".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"]

    dossiers = [
        DOSSIER_IMAGES_RESEAU,
        os.path.join(DOSSIER_APP, "Image"),
        os.path.join(DOSSIER_APP, "images")
    ]

    for dossier in dossiers:
        if not os.path.isdir(dossier):
            continue
        for extension in extensions:
            chemin = os.path.join(dossier, nom_base + extension)
            if os.path.isfile(chemin):
                return send_file(chemin)

    return (
        f"Image introuvable pour la filière '{nom_base}'. "
        f"Dossiers testés : {dossiers}",
        404
    )


@app.route("/api/diagnostic-images")
def diagnostic_images():
    """Route de diagnostic pour vérifier les droits et le chemin image."""
    resultats = []
    for dossier in [
        DOSSIER_IMAGES_RESEAU,
        os.path.join(DOSSIER_APP, "Image"),
        os.path.join(DOSSIER_APP, "images")
    ]:
        resultats.append({
            "dossier": dossier,
            "existe": os.path.isdir(dossier),
            "fichiers": sorted(os.listdir(dossier))[:20] if os.path.isdir(dossier) else []
        })
    return jsonify({"status": "success", "dossiers": resultats})


def obtenir_ip_locale():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        ip = sock.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        sock.close()
    return ip


if __name__ == "__main__":
    initialiser_bdd()
    ip_saisisseur = obtenir_ip_locale()
    url_base = f"http://{ip_saisisseur}:5000"

    print("=" * 65)
    print("SERVEUR SPC EXTRUSION")
    print(f"Saisie : {url_base}")
    print(f"Historique : {url_base}/historique")
    print(f"Diagnostic images : {url_base}/api/diagnostic-images")
    print(f"Dossier images réseau : {DOSSIER_IMAGES_RESEAU}")
    print("=" * 65)

    Timer(1, lambda: webbrowser.open(url_base)).start()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
