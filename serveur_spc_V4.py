import os
import webbrowser
from threading import Timer
from flask import Flask, request, jsonify
from flask_cors import CORS
# Remplacement de pandas par openpyxl (beaucoup plus léger)
from openpyxl import Workbook 

app = Flask(__name__)
CORS(app)

CHEMIN_HTML = "SPC.html" 

@app.route('/enregistrer-spc', methods=['POST'])
def save_data():
    try:
        data = request.json
        dossier = data.get('dossier')
        nom_fichier = data.get('nomFichier')
        mesures = data.get('mesures') 

        # Votre sécurité existante (parfaite pour la gestion automatique de l'année/filière)
        if not os.path.exists(dossier):
            os.makedirs(dossier)

        # --- ÉCRITURE EXCEL SANS PANDAS (VERSION OPTIMISÉE) ---
        wb = Workbook()
        ws = wb.active

        # 1. On définit l'ordre exact des colonnes de base pour que l'Excel soit toujours propre
        colonnes_fixes = [
            "date", "machine", "designation", "code_article", "filiere", "of", 
            "operateur", "lot_matiere_vierge", "lot_matiere_broye", 
            "longueur_mm", "poids_kg", "colorimetrie_L", "colorimetrie_A", "colorimetrie_B", "observations"
        ]

        # 2. On récupère toutes les autres clés (les cotes dynamiques comme Cote_1_Point_1, etc.)
        colonnes_dynamiques = [cle for cle in mesures.keys() if cle not in colonnes_fixes]
        
        # 3. L'en-tête final fusionne les colonnes fixes et les cotes dynamiques
        toutes_les_colonnes = colonnes_fixes + colonnes_dynamiques
        ws.append(toutes_les_colonnes)
        
        # 4. On extrait les valeurs dans le MÊME ORDRE que les en-têtes
        valeurs = [mesures.get(colonne, "") for colonne in toutes_les_colonnes]
        ws.append(valeurs)

        chemin_complet = os.path.join(dossier, nom_fichier)
        wb.save(chemin_complet)
        # -----------------------------------------------------

        print(f"✅ Enregistré proprement : {nom_fichier}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"❌ Erreur : {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
        
import os
import glob
from flask import Flask, request, jsonify
from flask_cors import CORS
from openpyxl import load_workbook

app = Flask(__name__)
CORS(app) # Permet aux pages locales de communiquer avec Flask

@app.route('/recuperer-historique', methods=['POST'])
def recuperer_historique():
    try:
        data = request.json
        filiere = data.get('filiere')
        
        # Le dossier par défaut utilisé par votre fichier SPC.html
        dossier_cible = f"W:/Consignes/DFN/Extrusion/SPC/DEFAUT/"
        
        # Si vous utilisez un sous-dossier spécifique par filière, ajustez ici :
        # dossier_cible = f"W:/Consignes/DFN/Extrusion/SPC/{filiere}/"

        if not os.path.exists(dossier_cible):
            return jsonify({"status": "success", "data": []})

        # On cherche tous les fichiers générés par la filière sélectionnée
        fichiers = glob.glob(os.path.join(dossier_cible, f"SPC_{filiere}_*.xlsx"))
        
        toutes_les_mesures = []
        for fichier in fichiers:
            try:
                wb = load_workbook(fichier, data_only=True)
                ws = wb.active
                
                # Lecture de la première ligne de données (Ligne 2)
                # Structure dictée par votre fonction enregistrerFinal()
                mesure = {
                    "filiere": ws.cell(row=2, column=1).value,
                    "code_article": ws.cell(row=2, column=2).value,
                    "of": ws.cell(row=2, column=3).value,
                    "operateur": ws.cell(row=2, column=4).value,
                    "date": ws.cell(row=2, column=5).value
                }
                toutes_les_mesures.append(mesure)
            except Exception as e:
                continue # Ignore un fichier corrompu ou ouvert
                
        return jsonify({"status": "success", "data": toutes_les_mesures}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000)

def ouvrir_navigateur():
    path = os.path.abspath(CHEMIN_HTML)
    webbrowser.open(f"file:///{path}")

if __name__ == "__main__":
    print("========================================")
    print("   SYSTÈME SPC EXTRUSION DÉMARRÉ")
    print("   L'INTERFACE VA S'OUVRIR...")
    print("========================================")
    
    # Bonus : Réduit à 1 seconde au lieu de 2, Flask démarre très vite sans pandas
    Timer(1, ouvrir_navigateur).start()
    
    # Optionnel : 'threaded=True' permet à Flask d'être plus réactif au lancement
    app.run(host='127.0.0.1', port=5000, threaded=True)
