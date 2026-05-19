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
# 1. CONFIGURATION DES CHEMINS (Compatible Script .py et Exécutable .exe)
# =====================================================================

# Détection automatique du dossier contenant l'application
if getattr(sys, 'frozen', False):
    DOSSIER_APP = os.path.dirname(sys.executable)
else:
    DOSSIER_APP = os.path.dirname(os.path.abspath(__file__))

# Initialisation de Flask (sans dossier static, tout est lu à la racine)
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
        return f"Erreur : Le fichier '{chemin_page}' est introuvable.", 404
    
    with open(chemin_page, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/historique_SPC.html')
def page_historique():
    """Affiche la page d'analyse historique_SPC.html"""
    chemin_page = os.path.join(DOSSIER_APP, "historique_SPC.html")
    if not os.path.exists(chemin_page):
        return f"Erreur : Le fichier '{chemin_page}' est introuvable.", 404
        
    with open(chemin_page, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/articles.js')
def servir_javascript():
    """Permet aux pages HTML de charger le dictionnaire d'articles"""
    chemin_js = os.path.join(DOSSIER_APP, "articles.js")
    if not os.path.exists(chemin_js):
        return "/* Erreur : Fichier articles.js introuvable */", 404
        
    with open(chemin_js, 'r', encoding='utf-8') as f:
        return f.read(), 200, {'Content-Type': 'application/javascript'}


# =====================================================================
# 3. ROUTES REQUÊTES DONNÉES (Sauvegarde et Lecture Excel)
# =====================================================================

@app.route('/enregistrer-spc', methods=['POST'])
def save_data():
    """Enregistre les cotes saisies dans un fichier Excel individuel"""
    try:
        data = request.json
        dossier = data.get('dossier')
        nom_fichier = data.get('nomFichier')
        mesures = data.get('mesures') 

        if not os.path.exists(dossier):
            os.makedirs(dossier)

        wb = Workbook()
        ws = wb.active

        # Définition de l'ordre structurel des colonnes
        colonnes_fixes = [
            "date", "machine", "designation", "code_article", "filiere", "of", 
            "operateur", "lot_matiere_vierge", "lot_matiere_broye", 
            "longueur_mm", "poids_kg", "colorimetrie_L", "colorimetrie_A", "colorimetrie_B", "observations"
        ]
        colonnes_dynamiques = [cle for cle in mesures.keys() if cle not in colonnes_fixes]
        toutes_les_colonnes = colonnes_fixes + colonnes_dynamiques
        
        # Écriture des en-têtes (Ligne 1) et des valeurs (Ligne 2)
        ws.append(toutes_les_colonnes)
        valeurs = [mesures.get(colonne, "") for colonne in toutes_les_colonnes]
        ws.append(valeurs)

        chemin_complet = os.path.join(dossier, nom_fichier)
        wb.save(chemin_complet)

        print(f"✅ Fichier enregistré avec succès : {nom_fichier}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"❌ Erreur lors de l'enregistrement : {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/recuperer-historique', methods=['POST'])
def recuperer_historique():
    """Scanne le réseau et renvoie la liste des mesures de la filière sélectionnée"""
    try:
        data = request.json
        filiere = data.get('filiere')
        annee = datetime.now().year

        # Dossier d'usine ciblé sur le réseau W:
        dossier_cible = f"W:/Consignes/DFN/Extrusion/SPC/Historique_SPC_Extrusion/{annee}/{filiere}/"

        if not os.path.exists(dossier_cible):
            return jsonify({"status": "success", "data": []})

        # Récupération de tous les fichiers Excel de la filière en cours
        fichiers = glob.glob(os.path.join(dossier_cible, f"SPC_{filiere}_*.xlsx"))
        
        toutes_les_mesures = []
        for fichier in fichiers:
            try:
                wb = load_workbook(fichier, data_only=True)
                ws = wb.active
                
                # Correspondance stricte avec l'ordre d'écriture des colonnes fixes
                mesure = {
                    "date": ws.cell(row=2, column=1).value,
                    "code_article": ws.cell(row=2, column=4).value,
                    "filiere": ws.cell(row=2, column=5).value,
                    "of": ws.cell(row=2, column=6).value,
                    "operateur": ws.cell(row=2, column=7).value
                }
                toutes_les_mesures.append(mesure)
            except Exception:
                continue  # Ignore le fichier s'il est verrouillé par un opérateur
                
        return jsonify({"status": "success", "data": toutes_les_mesures}), 200
    except Exception as e:
        print(f"❌ Erreur lors de la lecture de l'historique : {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =====================================================================
# 4. SCRIPT DE DÉMARRAGE
# =====================================================================

def ouvrir_navigateur():
    """Ouvre l'application directement via l'adresse HTTP locale sécurisée"""
    webbrowser.open("http://127.0.0.1:5000/")

if __name__ == "__main__":
    print("==================================================")
    print("        LANCEMENT DU SYSTÈME SPC EXTRUSION        ")
    print("==================================================")
    print(f"Dossier de travail détecté : {DOSSIER_APP}")
    
    # Temporisation d'une seconde pour laisser le serveur s'initialiser
    Timer(1, ouvrir_navigateur).start()
    
    # Lancement du serveur sur le port 5000
    app.run(host='127.0.0.1', port=5000, threaded=True)
