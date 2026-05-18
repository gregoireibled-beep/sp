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
        mesures = data.get('mesures') # Attend un dictionnaire ex: {"A": 1, "B": 2}

        if not os.path.exists(dossier):
            os.makedirs(dossier)

        # --- ÉCRITURE EXCEL SANS PANDAS ---
        wb = Workbook()
        ws = wb.active

        # Écriture des en-têtes (les clés du dictionnaire)
        colonnes = list(mesures.keys())
        ws.append(colonnes)
        
        # Écriture des valeurs
        valeurs = list(mesures.values())
        ws.append(valeurs)

        chemin_complet = os.path.join(dossier, nom_fichier)
        wb.save(chemin_complet)
        # ----------------------------------

        print(f"✅ Enregistré : {nom_fichier}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"❌ Erreur : {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

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
