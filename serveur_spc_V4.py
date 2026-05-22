import os
import sys
import glob
import webbrowser
import sqlite3
import json
from datetime import datetime
from threading import Timer
from flask import Flask, request, jsonify
from flask_cors import CORS

# =====================================================================
# 1. CONFIGURATION DES CHEMINS SÉCURISÉE POUR LE .EXE
# =====================================================================

def obtenir_dossier_application():
    """Détermine le dossier réel contenant les fichiers HTML et JS"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

DOSSIER_APP = obtenir_dossier_application()
DB_PATH = os.path.join(DOSSIER_APP, "base_donnees_spc.db")

app = Flask(__name__)
CORS(app)

# =====================================================================
# 1B. INITIALISATION DE LA BASE DE DONNÉES SQLITE (STRUCTURE FIXE)
# =====================================================================

def initialiser_bdd():
    """Crée la base de données avec une structure fixe et performante"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Création de la table avec une colonne dédiée au stockage des cotes dynamiques en JSON
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mesures_spc (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_article TEXT,
            designation TEXT,
            of TEXT,
            operateur TEXT,
            machine TEXT,
            date TEXT,
            lot_matiere_vierge TEXT,
            lot_matiere_broye_str TEXT,
            longueur_mm TEXT,
            poids_kg TEXT,
            colorimetrie_L TEXT,
            colorimetrie_A TEXT,
            colorimetrie_B TEXT,
            observations TEXT,
            filiere TEXT,
            annee_liaison INTEGER,
            cotes_gabarits TEXT -- Stockera toutes les cotes dynamiques au format JSON texto
        )
    """)
    # Création de l'index pour accélérer la lecture par les utilisateurs de l'historique
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_filiere_annee ON mesures_spc (filiere, annee_liaison);")
    conn.commit()
    conn.close()
    print(f"✅ Base de données SQLite initialisée et optimisée à : {DB_PATH}")

initialiser_bdd()

# =====================================================================
# 2. ROUTES DE NAVIGATION (Sert les pages HTML directement)
# =====================================================================

@app.route('/')
def page_principale():
    chemin_page = os.path.join(DOSSIER_APP, "SPC.html")
    if not os.path.exists(chemin_page):
        return f"Erreur 404 : Le fichier [SPC.html] est introuvable.", 404
    with open(chemin_page, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/historique')
def page_historique():
    chemin_page = os.path.join(DOSSIER_APP, "historique_SPC.html")
    if not os.path.exists(chemin_page):
        return f"Erreur 404 : Le fichier [historique_SPC.html] est introuvable.", 404
    with open(chemin_page, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/articles.js')
def servir_articles_js():
    chemin_script = os.path.join(DOSSIER_APP, "articles.js")
    if not os.path.exists(chemin_script):
        return "Erreur 404 : Le fichier articles.js est introuvable.", 404
    with open(chemin_script, 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'application/javascript'}
        
# =====================================================================
# 3. ROUTES API (Enregistrement et Lecture SQLite Optimisées)
# =====================================================================

@app.route('/enregistrer-spc', methods=['POST'])
def enregistrer_spc():
    """Reçoit les données et sépare le standard du dynamique pour le stocker proprement"""
    try:
        donnees_recues = request.get_json()
        if not donnees_recues or 'mesures' not in donnees_recues:
            return jsonify({"status": "error", "message": "Données manquantes"}), 400
            
        mesures = donnees_recues['mesures']
        
        # 1. Liste des colonnes fixes standards en BDD
        colonnes_standards = [
            "code_article", "designation", "of", "operateur", "machine", "date",
            "lot_matiere_vierge", "longueur_mm", "poids_kg", "colorimetrie_L",
            "colorimetrie_A", "colorimetrie_B", "observations", "filiere"
        ]
        
        donnees_fixes = {}
        donnees_dynamiques = {}
        
        # Triage des données reçues du JS
        for k, v in mesures.items():
            cle_propre = k.replace(" ", "_").replace("°", "")
            valeur_str = str(v) if v is not None else ""
            
            if cle_propre.lower() == "lot_matiere_broye":
                donnees_fixes["lot_matiere_broye_str"] = valeur_str
            elif cle_propre in colonnes_standards:
                donnees_fixes[cle_propre] = valeur_str
            else:
                # Tout ce qui n'est pas standard (Cotes, Gabarits...) va ici
                if valeur_str != "": 
                    donnees_dynamiques[cle_propre] = valeur_str

        # Calcul de l'année
        annee_controle = datetime.now().year
        date_saisie = donnees_fixes.get('date', '')
        if date_saisie and '/' in date_saisie:
            try:
                annee_controle = int(date_saisie.split('/')[2].split(' ')[0])
            except Exception:
                pass
        donnees_fixes['annee_liaison'] = annee_controle
        
        # On transforme le dictionnaire de cotes en une seule chaîne de texte JSON
        donnees_fixes['cotes_gabarits'] = json.dumps(donnees_dynamiques)

        # Construction de la requête SQL d'insertion
        colonnes = ", ".join(donnees_fixes.keys())
        placeholders = ", ".join(["?" for _ in donnees_fixes])
        valeurs = list(donnees_fixes.values())

        requete = f"INSERT INTO mesures_spc ({colonnes}) VALUES ({placeholders})"
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(requete, valeurs)
        conn.commit()
        conn.close()

        print(f"💾 Enregistré avec succès (Structure JSON) pour l'OF {donnees_fixes.get('of')}")
        return jsonify({"status": "success", "message": "Données enregistrées."})

    except Exception as e:
        print(f"❌ Erreur lors de l'enregistrement : {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/recuperer-historique', methods=['POST'])
def recuperer_historique():
    """Filtre la table et ré-injecte les cotes à plat pour que le JavaScript ne voie aucune différence"""
    try:
        criteres = request.get_json()
        filiere = criteres.get('filiere', 'TOUS')
        annee = criteres.get('annee', 'TOUS')

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  
        cursor = conn.cursor()

        clauses = []
        parametres = []
        if filiere != "TOUS":
            clauses.append("filiere = ?")
            parametres.append(filiere)
        if annee != "TOUS":
            clauses.append("annee_liaison = ?")
            parametres.append(int(annee))

        condition_where = ""
        if clauses:
            condition_where = "WHERE " + " AND ".join(clauses)

        requete = f"SELECT * FROM mesures_spc {condition_where}"
        cursor.execute(requete, parametres)
        lignes = cursor.fetchall()
        conn.close()

        liste_donnees = []
        for l in lignes:
            d = dict(l)
            
            # Récupération et déploiement des cotes dynamiques stockées en JSON
            if "cotes_gabarits" in d and d["cotes_gabarits"]:
                try:
                    cotes_extraites = json.loads(d["cotes_gabarits"])
                    # On fusionne les cotes directement dans l'objet pour le tableau HTML
                    d.update(cotes_extraites)
                except Exception:
                    pass
                del d["cotes_gabarits"] # On nettoie la clé technique JSON devenue inutile

            if "lot_matiere_broye_str" in d:
                d["lot_matiere_broye"] = d["lot_matiere_broye_str"]
                del d["lot_matiere_broye_str"]
                
            liste_donnees.append(d)

        return jsonify({"status": "success", "data": liste_donnees})

    except Exception as e:
        print(f"❌ Erreur récupération historique : {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# =====================================================================
# 4. GESTION DES IMAGES FILIÈRES
# =====================================================================

@app.route('/images/<nom_image>')
def servir_images(nom_image):
    dossier_images = "W:/Consignes/DFN/Extrusion/SPC/Image"
    nom_base = os.path.splitext(nom_image)[0]
    chemin_image = os.path.join(dossier_images, f"{nom_base}.jpg")
    if not os.path.exists(chemin_image):
        chemin_image = os.path.join(dossier_images, f"{nom_base}.jpeg")
    if os.path.exists(chemin_image):
        with open(chemin_image, 'rb') as f:
            return f.read(), 200, {'Content-Type': 'image/jpeg'}
    return "Image introuvable", 404

# =====================================================================
# 5. SCRIPT DE DÉMARRAGE
# =====================================================================

def ouvrir_navigateur():
    webbrowser.open("http://127.0.0.1:5000/")

if __name__ == "__main__":
    Timer(1, ouvrir_navigateur).start()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
