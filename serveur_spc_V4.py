import os
import sys
import json
import webbrowser
import sqlite3
import socket
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

# Remplacer par un chemin UNC si le lecteur W: n'est pas visible
# dans le contexte de lancement de l'executable.
DOSSIER_IMAGES_RESEAU = r"W:\Consignes\DFN\Extrusion\SPC\Image"

app = Flask(__name__)
CORS(app)


def initialiser_bdd():
    """Utilise le schéma de base existant dans base_donnees_spc.db."""
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


def get_value(mesures, *noms, default=""):
    """Accepte les noms minuscules du SPC.html et les anciens noms majuscules."""
    for nom in noms:
        if nom in mesures and mesures[nom] is not None:
            return str(mesures[nom]).strip()
    return default


@app.route("/enregistrer-spc", methods=["POST"])
def enregistrer_spc():
    try:
        payload = request.get_json(silent=True) or {}
        mesures = payload.get("mesures", {})
        if not isinstance(mesures, dict) or not mesures:
            return jsonify({"status": "error", "message": "Aucune mesure reçue."}), 400

        filiere = get_value(mesures, "filiere", "Filiere", default="Inconnu")
        of = get_value(mesures, "of", "OF", default="Inconnu")
        date_saisie = get_value(
            mesures,
            "date",
            "Date_Heure",
            default=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        )

        conn = sqlite3.connect(DB_PATH, timeout=15)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO mesures_spc (date_saisie, num_filiere, of, donnees_json)
            VALUES (?, ?, ?, ?)
        """, (
            date_saisie,
            filiere,
            of,
            json.dumps(mesures, ensure_ascii=False)
        ))
        conn.commit()
        nouvel_id = cursor.lastrowid
        conn.close()

        print(f"Mesure enregistrée : id={nouvel_id}, filière={filiere}, OF={of}")
        return jsonify({"status": "success", "message": "Données enregistrées !", "id": nouvel_id})

    except Exception as exc:
        print(f"Erreur enregistrement : {exc}")
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/recuperer-historique", methods=["POST"])
def recuperer_historique():
    """Retourne les données au format attendu par historique_SPC.html."""
    try:
        filtres = request.get_json(silent=True) or {}
        filiere_filtre = str(filtres.get("filiere", "TOUS")).strip()
        annee_filtre = str(filtres.get("annee", "TOUS")).strip()

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        conditions = []
        params = []

        if filiere_filtre and filiere_filtre != "TOUS":
            conditions.append("num_filiere = ?")
            params.append(filiere_filtre)

        query = "SELECT * FROM mesures_spc"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY id ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        resultats = []

        for row in rows:
            try:
                donnees = json.loads(row["donnees_json"] or "{}")
            except Exception:
                donnees = {}

            # Normalisation des champs pour historique_SPC.html
            resultat = {
                "id": row["id"],
                "date": get_value(donnees, "date", "Date_Heure", default=row["date_saisie"] or ""),
                "filiere": get_value(donnees, "filiere", "Filiere", default=row["num_filiere"] or ""),
                "of": get_value(donnees, "of", "OF", default=row["of"] or ""),
                "code_article": get_value(donnees, "code_article", "Code_Article"),
                "designation": get_value(donnees, "designation", "Designation"),
                "operateur": get_value(donnees, "operateur", "Operateur"),
                "machine": get_value(donnees, "machine", "Machine"),
                "lot_matiere_vierge": get_value(donnees, "lot_matiere_vierge", "Lot_Vierge"),
                "lot_matiere_broye": get_value(donnees, "lot_matiere_broye", "Lot_Broye"),
                "longueur_mm": get_value(donnees, "longueur_mm", "Longueur_mm"),
                "poids_kg": get_value(donnees, "poids_kg", "Poids_kg"),
                "colorimetrie_L": get_value(donnees, "colorimetrie_L", "Colorimetrie_L"),
                "colorimetrie_A": get_value(donnees, "colorimetrie_A", "Colorimetrie_A"),
                "colorimetrie_B": get_value(donnees, "colorimetrie_B", "Colorimetrie_B"),
                "observations": get_value(donnees, "observations", "Observations"),
            }

            # Année appliquée après décodage de la vraie date
            if annee_filtre and annee_filtre != "TOUS":
                annee = resultat["date"].split(" ")[0].split("/")
                if len(annee) != 3 or annee[2] != annee_filtre:
                    continue

            # Les cotes et gabarits sont stockés directement dans le JSON.
            for cle, valeur in donnees.items():
                if cle.startswith("Cote_") or cle.startswith("Gabarit_"):
                    resultat[cle] = valeur

            # Les résumés restent également disponibles si présents.
            if "resume_cotes" in donnees:
                resultat["resume_cotes"] = donnees["resume_cotes"]
            if "resume_gabarits" in donnees:
                resultat["resume_gabarits"] = donnees["resume_gabarits"]

            resultats.append(resultat)

        conn.close()
        return jsonify({"status": "success", "data": resultats})

    except Exception as exc:
        print(f"Erreur récupération historique : {exc}")
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
    return send_from_directory(DOSSIER_APP, "articles.js", mimetype="application/javascript")


@app.route("/images/<path:nom_image>")
def servir_images(nom_image):
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

    return f"Image introuvable pour la filière {nom_base}", 404


@app.route("/api/diagnostic")
def diagnostic():
    return jsonify({
        "status": "success",
        "db_path": DB_PATH,
        "db_exists": os.path.isfile(DB_PATH),
        "images": [
            {
                "dossier": dossier,
                "existe": os.path.isdir(dossier),
                "fichiers": sorted(os.listdir(dossier))[:20] if os.path.isdir(dossier) else []
            }
            for dossier in [
                DOSSIER_IMAGES_RESEAU,
                os.path.join(DOSSIER_APP, "Image"),
                os.path.join(DOSSIER_APP, "images")
            ]
        ]
    })


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
    ip = obtenir_ip_locale()
    url = f"http://{ip}:5000"

    print("=" * 65)
    print("SERVEUR SPC SQLITE CORRIGE")
    print(f"Saisie : {url}")
    print(f"Historique : {url}/historique")
    print(f"Diagnostic : {url}/api/diagnostic")
    print(f"Base : {DB_PATH}")
    print("=" * 65)

    Timer(1, lambda: webbrowser.open(url)).start()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
