import os
import glob
import webbrowser
from threading import Timer
from flask import Flask, request, jsonify
from flask_cors import CORS
from openpyxl import Workbook, load_workbook

# --- CONFIGURATION INITIALE UNIQUE ---
app = Flask(__name__)
CORS(app)  # Permet aux pages web locales (SPC.html et historique_SPC.html) de communiquer avec Flask

CHEMIN_HTML = "SPC.html" 

# --- ROUTE 1 : ENREGISTREMENT DES ENREGISTREMENTS SPC ---
@app.route('/enregistrer-spc', methods=['POST'])
def save_data():
    try:
        data = request.json
        dossier = data.get('dossier')
        nom_fichier = data.get('nomFichier')
        mesures = data.get('mesures') 

        if not os.path.exists(dossier):
            os.makedirs(dossier)

        # ÉCRITURE EXCEL SANS PANDAS
        wb = Workbook()
        ws = wb.active

        # 1. Ordre exact des colonnes de base
        colonnes_fixes = [
            "date", "machine", "designation", "code_article", "filiere", "of", 
            "operateur", "lot_matiere_vierge", "lot_matiere_broye", 
            "longueur_mm", "poids_kg", "colorimetrie_L", "colorimetrie_A", "colorimetrie_B", "observations"
        ]

        # 2. Récupération des cotes dynamiques
        colonnes_dynamiques = [cle for cle in mesures.keys() if cle not in colonnes_fixes]
        
        # 3. Fusion des en-têtes
        toutes_les_colonnes = colonnes_fixes + colonnes_dynamiques
        ws.append(toutes_les_colonnes)
        
        # 4. Extraction des valeurs associées
        valeurs = [mesures.get(colonne, "") for colonne in toutes_les_colonnes]
        ws.append(valeurs)

        chemin_complet = os.path.join(dossier, nom_fichier)
        wb.save(chemin_complet)

        print(f"✅ Enregistré proprement : {nom_fichier}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"❌ Erreur Enregistrement : {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
        

# --- ROUTE 2 : RÉCUPÉRATION AUTOMATIQUE DE L'HISTORIQUE ---
@app.route('/recuperer-historique', methods=['POST'])
def recuperer_historique():
    try:
        data = request.json
        filiere = data.get('filiere')
        annee = maintenant.getFullYear()

        # Si vous utilisez un dossier dynamique par filière comme dans votre JS, décommentez la ligne ci-dessous :
        dossier_cible = f"W:/Consignes/DFN/Extrusion/SPC/Historique_SPC_Extrusion/{annee}/{filiere}/"

        if not os.path.exists(dossier_cible):
            return jsonify({"status": "success", "data": []})

        # Recherche de tous les fichiers Excel correspondants à la filière
        fichiers = glob.glob(os.path.join(dossier_cible, f"SPC_{filiere}_*.xlsx"))
        
        toutes_les_mesures = []
        for fichier in fichiers:
            try:
                wb = load_workbook(fichier, data_only=True)
                ws = wb.active
                
                # Lecture de la ligne de données (Ligne 2)
                # Remarque : On utilise des clés en minuscules pour correspondre à votre logique de refresh dans l'historique
                mesure = {
                    "filiere": ws.cell(row=2, column=1).value,
                    "code_article": ws.cell(row=2, column=2).value,
                    "of": ws.cell(row=2, column=3).value,
                    "operateur": ws.cell(row=2, column=4).value,
                    "date": ws.cell(row=2, column=5).value
                }
                toutes_les_mesures.append(mesure)
            except Exception:
                continue  # Ignore le fichier si quelqu'un l'a ouvert sur Excel
                
        return jsonify({"status": "success", "data": toutes_les_mesures}), 200
    except Exception as e:
        print(f"❌ Erreur Historique : {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500


    # --- SCRIPT DE DÉMARRAGE AUTOMATIQUE ---
    def ouvrir_navigateur():
    webbrowser.open("http://127.0.0.1:5000/static/SPC.html")

if __name__ == "__main__":
    print("========================================")
    print("    SYSTÈME SPC EXTRUSION DÉMARRÉ")
    print("    L'INTERFACE VA S'OUVRIR...")
    print("========================================")
    
    # Déclenche l'ouverture de l'écran de saisie SPC.html après 1 seconde
    Timer(1, ouvrir_navigateur).start()
    
    # Lancement du serveur Flask sur le port 5000 en mode multi-thread pour absorber les requêtes simultanées
    app.run(host='127.0.0.1', port=5000, threaded=True)
