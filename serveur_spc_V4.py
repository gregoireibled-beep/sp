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
        # Si c'est l'exécutable compilé
        return os.path.dirname(sys.executable)
    else:
        # Si c'est le script de développement .py
        return os.path.dirname(os.path.abspath(__file__))

DOSSIER_APP = obtenir_dossier_application()
DB_PATH = os.path.join(DOSSIER_APP, "base_donnees_spc.db")

app = Flask(__name__)
CORS(app)

# =====================================================================
# 1B. INITIALISATION DE LA BASE DE DONNÉES SQLITE
# =====================================================================

def initialiser_bdd():
    """Crée la base de données et la table principale si elles n'existent pas"""
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
            lot_matiere_broye_str TEXT, -- Évite le conflit d'accent
            longueur_mm TEXT,
            poids_kg TEXT,
            colorimetrie_L TEXT,
            colorimetrie_A TEXT,
            colorimetrie_B TEXT,
            observations TEXT,
            filiere TEXT,
            annee_liaison INTEGER,
            cotes_gabarits TEXT -- Contient toutes les cotes dynamiques en format JSON
        )
    """)
    # Création d'un index pour accélérer instantanément l'affichage de l'historique
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_filiere_annee ON mesures_spc (filiere, annee_liaison);")
    conn.commit()
    conn.close()
    print(f"✅ Base de données SQLite initialisée avec succès au chemin : {DB_PATH}")

initialiser_bdd()

# =====================================================================
# 2. ROUTES DE NAVIGATION (Sert les pages HTML directement)
# =====================================================================

@app.route('/')
def page_principale():
    """Affiche la page de saisie SPC.html principale"""
    chemin_page = os.path.join(DOSSIER_APP, "SPC.html")
    if not os.path.exists(chemin_page):
        return f"Erreur 404 : Le fichier de saisie [SPC.html] est introuvable à : {chemin_page}", 404
    with open(chemin_page, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/historique')
def page_historique():
    """Affiche la page historique_SPC.html"""
    chemin_page = os.path.join(DOSSIER_APP, "historique_SPC.html")
    if not os.path.exists(chemin_page):
        return f"Erreur 404 : Le fichier historique [historique_SPC.html] est introuvable à : {chemin_page}", 404
    with open(chemin_page, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/articles.js')
def servir_articles_js():
    """Sert le fichier de configuration des articles et filières au format JavaScript"""
    chemin_script = os.path.join(DOSSIER_APP, "articles.js")
    if not os.path.exists(chemin_script):
        print(f"❌ Fichier [articles.js] introuvable au chemin : {chemin_script}")
        return "Erreur 404 : Le fichier articles.js est introuvable sur le serveur.", 404
    
    with open(chemin_script, 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'application/javascript'}
        
# =====================================================================
# 3. ROUTES API (Enregistrement et Lecture SQLite)
# =====================================================================

@app.route('/enregistrer-spc', methods=['POST'])
def enregistrer_spc():
    """Reçoit les données du formulaire SPC.html et les insère en BDD"""
    try:
        donnees_recues = request.get_json()
        if not donnees_recues or 'mesures' not in donnees_recues:
            return jsonify({"status": "error", "message": "Données manquantes"}), 400
            
        mesures = donnees_recues['mesures']
        
        # Liste des colonnes fixes standards de la BDD
        colonnes_standards = [
            "code_article", "designation", "of", "operateur", "machine", "date",
            "lot_matiere_vierge", "longueur_mm", "poids_kg", "colorimetrie_L",
            "colorimetrie_A", "colorimetrie_B", "observations", "filiere"
        ]
        
        donnees_fixes = {}
        donnees_dynamiques = {}
        
        # Tri des données reçues du JavaScript
        for k, v in mesures.items():
            cle_propre = k.replace(" ", "_").replace("°", "")
            valeur_str = str(v) if v is not None else ""
            
            if cle_propre.lower() == "lot_matiere_broye":
                donnees_fixes["lot_matiere_broye_str"] = valeur_str
            elif cle_propre in colonnes_standards:
                donnees_fixes[cle_propre] = valeur_str
            else:
                # Tout ce qui concerne les cotes ou gabarits dynamiques va dans le JSON
                if valeur_str != "":
                    donnees_dynamiques[cle_propre] = valeur_str

        # Déterminer l'année à partir de la date saisie (Format DD/MM/YYYY)
        annee_controle = datetime.now().year
        date_saisie = donnees_fixes.get('date', '')
        if date_saisie and '/' in date_saisie:
            try:
                annee_controle = int(date_saisie.split('/')[2].split(' ')[0])
            except Exception:
                pass
                
        donnees_fixes['annee_liaison'] = annee_controle
        donnees_fixes['cotes_gabarits'] = json.dumps(donnees_dynamiques)

        # Construction dynamique de la requête d'insertion SQL
        colonnes = ", ".join(donnees_fixes.keys())
        placeholders = ", ".join(["?" for _ in donnees_fixes])
        valeurs = list(donnees_fixes.values())

        requete = f"INSERT INTO mesures_spc ({colonnes}) VALUES ({placeholders})"
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(requete, valeurs)
        conn.commit()
        conn.close()

        print(f"💾 Contrôle enregistré en BDD avec succès pour l'OF {donnees_fixes.get('of')}")
        return jsonify({"status": "success", "message": "Données enregistrées en BDD."})

    except Exception as e:
        print(f"❌ Erreur lors de l'enregistrement : {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/recuperer-historique', methods=['POST'])
def recuperer_historique():
    """Filtre la table SQLite et convertit à la volée les mesures à slashes en nombres pour les graphiques"""
    try:
        criteres = request.get_json()
        filiere = criteres.get('filiere', 'TOUS')
        annee = criteres.get('annee', 'TOUS')

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Récupération sous forme de dictionnaire
        cursor = conn.cursor()

        # Construction dynamique des clauses WHERE
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

        # Conversion et nettoyage de chaque ligne pour le JSON
        liste_donnees = []
        for l in lignes:
            d = dict(l)
            
            # Traitement des cotes et gabarits dynamiques stockés en JSON
            if "cotes_gabarits" in d and d["cotes_gabarits"]:
                try:
                    cotes_extraites = json.loads(d["cotes_gabarits"])
                    
                    # Parcours des cotes pour nettoyer les multi-saisies (ex: "270 / 270 / 270")
                    for cle, valeur in list(cotes_extraites.items()):
                        valeur_str = str(valeur)
                        if "/" in valeur_str:
                            try:
                                # On découpe chaque valeur et on convertit en float
                                valeurs_numeriques = [float(x.strip()) for x in valeur_str.split("/") if x.strip()]
                                if valeurs_numeriques:
                                    # Calcul de la moyenne des cotes pour le graphique SPC
                                    cotes_extraites[cle] = round(sum(valeurs_numeriques) / len(valeurs_numeriques), 2)
                            except Exception:
                                # Si ce n'est pas convertible (ex: Gabarit "C"), on garde la valeur d'origine
                                pass
                                
                    # Fusionne les cotes nettoyées dans l'objet principal renvoyé au JS
                    d.update(cotes_extraites)
                except Exception:
                    pass
                
                # Suppression de la colonne brute JSON pour alléger la réponse
                del d["cotes_gabarits"]

            # Rétrocompatibilité pour la clé lot_matiere_broye
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
    """Va chercher l'image de la filière directement sur le réseau d'usine W:"""
    dossier_images = "W:/Consignes/DFN/Extrusion/SPC/Image"
    nom_base = os.path.splitext(nom_image)[0]
    
    chemin_image = os.path.join(dossier_images, f"{nom_base}.jpg")
    if not os.path.exists(chemin_image):
        chemin_image = os.path.join(dossier_images, f"{nom_base}.jpeg")
        
    if os.path.exists(chemin_image):
        with open(chemin_image, 'rb') as f:
            return f.read(), 200, {'Content-Type': 'image/jpeg'}
            
    print(f"❌ Image de filière introuvable sur le réseau W: {nom_base}.jpg (ou .jpeg)")
    return f"Image introuvable dans le dossier {dossier_images}", 404


# =====================================================================
# 5. SCRIPT DE DÉMARRAGE
# =====================================================================

def ouvrir_navigateur():
    webbrowser.open("http://127.0.0.1:5000/")

if __name__ == "__main__":
    # Ouvre automatiquement la page après un délai d'une seconde
    Timer(1, ouvrir_navigateur).start()
    
    # Lancement de l'application Flask ouverte au réseau (0.0.0.0) et multi-threadée
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
