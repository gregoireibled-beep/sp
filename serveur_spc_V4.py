import os
import sys
import glob
import webbrowser
from datetime import datetime
from threading import Timer
from flask import Flask, request, jsonify
from flask_cors import CORS
from openpyxl import Workbook, load_workbook

# =====================================================================
# 1. CONFIGURATION DES CHEMINS SECURISEE POUR LE .EXE
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

app = Flask(__name__)
CORS(app)


# =====================================================================
# 2. ROUTES DE NAVIGATION (Sert les pages HTML directement)
# =====================================================================

@app.route('/')
def page_principale():
    """Affiche la page de saisie SPC.html principale"""
    chemin_page = os.path.join(DOSSIER_APP, "SPC.html")
    
    if not os.path.exists(chemin_page):
        return f"Erreur 404 : Le fichier de saisie est introuvable au chemin : {chemin_page}", 404
    
    with open(chemin_page, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/historique_SPC.html')
def page_historique():
    """Affiche la page d'analyse historique_SPC.html"""
    chemin_page = os.path.join(DOSSIER_APP, "historique_SPC.html")
    
    if not os.path.exists(chemin_page):
        return f"Erreur 404 : Le fichier d'historique est introuvable au chemin : {chemin_page}", 404
        
    with open(chemin_page, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/articles.js')
def servir_javascript():
    """Permet aux pages HTML de charger le dictionnaire d'articles"""
    chemin_js = os.path.join(DOSSIER_APP, "articles.js")
    
    if not os.path.exists(chemin_js):
        return "/* Erreur 404 : Fichier articles.js introuvable */", 404
        
    with open(chemin_js, 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'application/javascript'}


# =====================================================================
# 3. ROUTES REQUÊTES DONNÉES (Sauvegarde et Lecture Excel)
# =====================================================================

@app.route('/enregistrer-spc', methods=['POST'])
def save_data():
    try:
        data = request.json
        dossier = data.get('dossier')
        nom_fichier = data.get('nomFichier')
        mesures = data.get('mesures') 

        if not os.path.exists(dossier):
            os.makedirs(dossier)

        wb = Workbook()
        ws = wb.active

        colonnes_fixes = [
            "date", "machine", "designation", "code_article", "filiere", "of", 
            "operateur", "lot_matiere_vierge", "lot_matiere_broye", 
            "longueur_mm", "poids_kg", "colorimetrie_L", "colorimetrie_A", "colorimetrie_B", "observations"
        ]
        colonnes_dynamiques = [cle for cle in mesures.keys() if cle not in colonnes_fixes]
        toutes_les_colonnes = colonnes_fixes + colonnes_dynamiques
        
        ws.append(toutes_les_colonnes)
        valeurs = [mesures.get(colonne, "") for colonne in toutes_les_colonnes]
        ws.append(valeurs)

        chemin_complet = os.path.join(dossier, nom_fichier)
        wb.save(chemin_complet)

        print(f"✅ Fichier enregistre : {nom_fichier}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"❌ Erreur Enregistrement : {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/recuperer-historique', methods=['POST'])
def recuperer_historique():
    try:
        data = request.json
        filiere = data.get('filiere')
        annee = datetime.now().year

        dossier_cible = f"W:/Consignes/DFN/Extrusion/SPC/Historique_SPC_Extrusion/{annee}/{filiere}/"

        if not os.path.exists(dossier_cible):
            return jsonify({"status": "success", "data": []})

        fichiers = glob.glob(os.path.join(dossier_cible, f"SPC_{filiere}_*.xlsx"))
        
        toutes_les_mesures = []
        for fichier in fichiers:
            try:
                wb = load_workbook(fichier, data_only=True)
                ws = wb.active
                mesure = {
                    "date": ws.cell(row=2, column=1).value,
                    "code_article": ws.cell(row=2, column=4).value,
                    "filiere": ws.cell(row=2, column=5).value,
                    "of": ws.cell(row=2, column=6).value,
                    "operateur": ws.cell(row=2, column=7).value
                }
                toutes_les_mesures.append(mesure)
            except Exception:
                continue
                
        return jsonify({"status": "success", "data": toutes_les_mesures}), 200
    except Exception as e:
        print(f"❌ Erreur Lecture Historique : {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
# =====================================================================
# 5. ROUTE POUR LES IMAGE
# =====================================================================

@app.route('/images/<nom_image>')
def servir_images(nom_image):
    """Va chercher l'image de la filière directement sur le réseau d'usine W:"""
    # 1. On définit le dossier source sur le réseau W:
    dossier_images = "W:/Consignes/DFN/Extrusion/SPC/Image"
    
    # 2. Sécurité : Extraction du nom sans l'extension pour tester .jpg et .jpeg
    nom_base = os.path.splitext(nom_image)[0]
    
    # On teste le chemin avec .jpg
    chemin_image = os.path.join(dossier_images, f"{nom_base}.jpg")
    
    # Si le .jpg n'existe pas, on tente le .jpeg
    if not os.path.exists(chemin_image):
        chemin_image = os.path.join(dossier_images, f"{nom_base}.jpeg")
        
    # 3. Si l'image existe enfin, on la sert au navigateur
    if os.path.exists(chemin_image):
        ext = os.path.splitext(chemin_image)[1].lower()
        mimetype = "image/jpeg" # .jpg et .jpeg utilisent le même mimetype
        
        with open(chemin_image, 'rb') as f:
            return f.read(), 200, {'Content-Type': mimetype}
            
    # 4. En cas d'échec total, on écrit l'erreur dans la console de l'exécutable pour le diagnostic
    print(f"❌ Image de filière introuvable sur le réseau W: {nom_base}.jpg (ou .jpeg)")
    return f"Image introuvable dans le dossier {dossier_images}", 404

# =====================================================================
# 4. SCRIPT DE DÉMARRAGE
# =====================================================================

def ouvrir_navigateur():
    webbrowser.open("http://127.0.0.1:5000/")

if __name__ == "__main__":
    print("==================================================")
    print("        LANCEMENT DU SYSTÈME SPC EXTRUSION        ")
    print("==================================================")
    print(f"Dossier cible verifie : {DOSSIER_APP}")
    
    Timer(1, ouvrir_navigateur).start()
    app.run(host='127.0.0.1', port=5000, threaded=True)
