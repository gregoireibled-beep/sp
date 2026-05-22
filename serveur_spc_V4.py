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
    # Création de la table avec les colonnes de base communes à tous les contrôles
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
            annee_liaison INTEGER
        )
    """)
    conn.commit()
    conn.close()
    print(f"✅ Base de données SQLite initialisée avec succès au chemin : {DB_PATH}")

initialiser_bdd()

def verifier_et_ajouter_colonnes(cles_mesures):
    """Vérifie si les colonnes dynamiques (Cotes, Gabarits) existent, sinon les ajoute"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Récupérer la liste des colonnes existantes
    cursor.execute("PRAGMA table_info(mesures_spc)")
    colonnes_existantes = [col[1] for col in cursor.fetchall()]
    
    for cle in cles_mesures:
        if cle not in colonnes_existantes:
            try:
                cursor.execute(f"ALTER TABLE mesures_spc ADD COLUMN {cle} TEXT")
                print(f"➕ Nouvelle colonne dynamique ajoutée à la BDD : {cle}")
            except Exception as e:
                print(f"❌ Impossible d'ajouter la colonne {cle} : {e}")
                
    conn.commit()
    conn.close()

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
        
        # Nettoyage des clés pour correspondre aux standards SQL
        mesures_propres = {}
        for k, v in mesures.items():
            cle_propre = k.replace(" ", "_").replace("°", "")
            # Mapping pour éviter les soucis de propriétés ou d'accents du JS
            if cle_propre.lower() == "lot_matiere_broye":
                cle_propre = "lot_matiere_broye_str"
            mesures_propres[cle_propre] = str(v) if v is not None else ""

        # S'assurer que les colonnes dynamiques de l'objet existent en BDD
        verifier_et_ajouter_colonnes(mesures_propres.keys())

        # Déterminer l'année à partir de la date saisie (Format DD/MM/YYYY HH:MM:SS ou DD/MM/YYYY)
        annee_controle = datetime.now().year
        date_saisie = mesures_propres.get('date', '')
        if date_saisie and '/' in date_saisie:
            try:
                annee_controle = int(date_saisie.split('/')[2].split(' ')[0])
            except Exception:
                pass
                
        mesures_propres['annee_liaison'] = annee_controle

        # Construction dynamique de la requête d'insertion SQL
        colonnes = ", ".join(mesures_propres.keys())
        placeholders = ", ".join(["?" for _ in mesures_propres])
        valeurs = list(mesures_propres.values())

        requete = f"INSERT INTO mesures_spc ({colonnes}) VALUES ({placeholders})"
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(requete, valeurs)
        conn.commit()
        conn.close()

        print(f"💾 Contrôle enregistré en BDD avec succès pour l'OF {mesures_propres.get('of')}")
        return jsonify({"status": "success", "message": "Données enregistrées en BDD."})

    except Exception as e:
        print(f"❌ Erreur lors de l'enregistrement : {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/recuperer-historique', methods=['POST'])
def recuperer_historique():
    """Filtre la table SQLite par filière et année et renvoie le tableau au format JSON"""
    try:
        criteres = request.get_json()
        filiere = criteres.get('filiere', 'TOUS')
        annee = criteres.get('annee', 'TOUS')

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Permet de récupérer les résultats sous forme de dictionnaire
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

        # Conversion optimisée du format SQLite Row vers une liste de dictionnaires standards
        liste_donnees = []
        for l in lignes:
            d = dict(l)
            # Réajustement de la clé pour le JavaScript de l'historique
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
    
    # Lancement de l'application Flask avec le multi-threading activé
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
