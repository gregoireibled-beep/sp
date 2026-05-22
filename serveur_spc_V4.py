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

def obtenir_dossier_application():
if getattr(sys, 'frozen', False):
return os.path.dirname(sys.executable)
else:
return os.path.dirname(os.path.abspath(file))

DOSSIER_APP = obtenir_dossier_application()
DB_PATH = os.path.join(DOSSIER_APP, "base_donnees_spc.db")

app = Flask(name)
CORS(app)

def initialiser_bdd():
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
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
cotes_gabarits TEXT
)
""")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_filiere_annee ON mesures_spc (filiere, annee_liaison);")
conn.commit()
conn.close()

initialiser_bdd()

@app.route('/')
def page_principale():
chemin_page = os.path.join(DOSSIER_APP, "SPC.html")
if not os.path.exists(chemin_page):
return "Erreur 404 : Fichier SPC.html introuvable", 404
with open(chemin_page, 'r', encoding='utf-8') as f:
return f.read()

@app.route('/historique')
def page_historique():
chemin_page = os.path.join(DOSSIER_APP, "historique_SPC.html")
if not os.path.exists(chemin_page):
return "Erreur 404 : Fichier historique_SPC.html introuvable", 404
with open(chemin_page, 'r', encoding='utf-8') as f:
return f.read()

@app.route('/articles.js')
def servir_articles_js():
chemin_script = os.path.join(DOSSIER_APP, "articles.js")
if not os.path.exists(chemin_script):
return "Erreur 404 : Fichier articles.js introuvable", 404
with open(chemin_script, 'r', encoding='utf-8') as f:
return f.read(), 200, {'Content-Type': 'application/javascript'}

@app.route('/enregistrer-spc', methods=['POST'])
def enregistrer_spc():
try:
donnees_recues = request.get_json()
if not donnees_recues or 'mesures' not in donnees_recues:
return jsonify({"status": "error", "message": "Données manquantes"}), 400

    mesures = donnees_recues['mesures']
    colonnes_standards = [
        "code_article", "designation", "of", "operateur", "machine", "date",
        "lot_matiere_vierge", "longueur_mm", "poids_kg", "colorimetrie_L",
        "colorimetrie_A", "colorimetrie_B", "observations", "filiere"
    ]
    
    donnees_fixes = {}
    donnees_dynamiques = {}
    
    for k, v in mesures.items():
        cle_propre = k.replace(" ", "_").replace("°", "")
        valeur_str = str(v) if v is not None else ""
        
        if cle_propre.lower() == "lot_matiere_broye":
            donnees_fixes["lot_matiere_broye_str"] = valeur_str
        elif cle_propre in colonnes_standards:
            donnees_fixes[cle_propre] = valeur_str
        else:
            if valeur_str != "":
                donnees_dynamiques[cle_propre] = valeur_str

    annee_controle = datetime.now().year
    date_saisie = donnees_fixes.get('date', '')
    if date_saisie and '/' in date_saisie:
        try:
            annee_controle = int(date_saisie.split('/')[2].split(' ')[0])
        except Exception:
            pass
            
    donnees_fixes['annee_liaison'] = annee_controle
    donnees_fixes['cotes_gabarits'] = json.dumps(donnees_dynamiques)

    colonnes = ", ".join(donnees_fixes.keys())
    placeholders = ", ".join(["?" for _ in donnees_fixes])
    valeurs = list(donnees_fixes.values())

    requete = f"INSERT INTO mesures_spc ({colonnes}) VALUES ({placeholders})"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(requete, valeurs)
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Données enregistrées"})
except Exception as e:
    return jsonify({"status": "error", "message": str(e)}), 500
@app.route('/recuperer-historique', methods=['POST'])
def recuperer_historique():
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

    liste_donnees_brutes = []
    toutes_les_cles_dynamiques = set()

    for l in lignes:
        d = dict(l)
        cotes_extraites = {}
        if "cotes_gabarits" in d and d["cotes_gabarits"]:
            try:
                cotes_extraites = json.loads(d["cotes_gabarits"])
                for k in cotes_extraites.keys():
                    toutes_les_cles_dynamiques.add(k)
            except Exception:
                pass
        liste_donnees_brutes.append((d, cotes_extraites))

    liste_donnees_finales = []
    for d, cotes_extraites in liste_donnees_brutes:
        for cle in toutes_les_cles_dynamiques:
            d[cle] = ""
            
        for cle, valeur in cotes_extraites.items():
            d[cle] = str(valeur) if valeur is not None else ""

        if "cotes_gabarits" in d:
            del d["cotes_gabarits"]

        if "lot_matiere_broye_str" in d:
            d["lot_matiere_broye"] = d["lot_matiere_broye_str"]
            del d["lot_matiere_broye_str"]
            
        liste_donnees_finales.append(d)

    return jsonify({"status": "success", "data": liste_donnees_finales})
except Exception as e:
    return jsonify({"status": "error", "message": str(e)}), 500
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
def ouvrir_navigateur():
webbrowser.open("http://127.0.0.1:5000/")

if name == "main":
Timer(1, ouvrir_navigateur).start()
app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
