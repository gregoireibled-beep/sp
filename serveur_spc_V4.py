import os
import sys
import glob
import webbrowser
import sqlite3
import json
import socket
from datetime import datetime
from threading import Timer
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# =====================================================================
# 1. CONFIGURATION DES CHEMINS SÉCURISÉE POUR LE .EXE
# =====================================================================

def obtenir_dossier_application():
    """Détermine le dossier réel contenant les fichiers HTML et JS"""
    if getattr(sys, 'frozen', False):
        # Si c'est l'exécutable compilé via PyInstaller
        return os.path.dirname(sys.executable)
    else:
        # Si c'est le script de développement .py normal
        return os.path.dirname(os.path.abspath(__file__))

DOSSIER_APP = obtenir_dossier_application()
DB_PATH = os.path.join(DOSSIER_APP, \"base_donnees_spc.db\")

app = Flask(__name__)
CORS(app)

# =====================================================================
# 1B. INITIALISATION DE LA BASE DE DONNÉES SQLITE
# =====================================================================

def initialiser_bdd():
    """Crée la base de données et la table principale si elles n'existent pas"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mesures_spc (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_saisie TEXT,
            num_filiere TEXT,
            of TEXT,
            donnees_json TEXT
        )
    ''')
    conn.commit()
    conn.close()

# =====================================================================
# 2. ROUTES API (EXEMPLES DE VOS ANCIENNES ROUTES A CONSERVER)
# =====================================================================

@app.route('/enregistrer-spc', methods=['POST'])
def enregistrer_spc():
    try:
        data = request.json
        mesures = data.get('mesures', {})
        
        num_filiere = mesures.get('Filiere', 'Inconnu')
        of = mesures.get('OF', 'Inconnu')
        date_actuelle = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO mesures_spc (date_saisie, num_filiere, of, donnees_json)
            VALUES (?, ?, ?, ?)
        ''', (date_actuelle, num_filiere, of, json.dumps(mesures)))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "message": "Données enregistrées !"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# [NOTE : Remettez ici vos autres routes de traitement de données de votre fichier V8]

# =====================================================================
# 3. DISTRIBUTION DES FICHIERS INTERFACE (Nouveau !)
# =====================================================================

@app.route('/')
def index():
    """Envoie la page principale SPC.html au Saisisseur"""
    return send_from_directory(DOSSIER_APP, 'SPC.html')

@app.route('/historique')
def historique():
    """Envoie la page historique_SPC.html aux Consultants"""
    return send_from_directory(DOSSIER_APP, 'historique_SPC.html')

@app.route('/images/<nom_image>')
def servir_images(nom_image):
    """Va chercher l'image de la filiere directement sur le reseau d'usine W:"""
    dossier_images = "W:/Consignes/DFN/Extrusion/SPC/Image"
    nom_base = os.path.splitext(nom_image)[0]
    chemin_image = os.path.join(dossier_images, f"{nom_base}.jpg")
    if not os.path.exists(chemin_image):
        chemin_image = os.path.join(dossier_images, f"{nom_base}.jpeg")
    if os.path.exists(chemin_image):
        with open(chemin_image, 'rb') as f:
            return f.read(), 200, {'Content-Type': 'image/jpeg'}
    return f"Image introuvable dans le dossier {dossier_images}", 404

# =====================================================================
# 4. SCRIPT DE DÉMARRAGE AUTOMATIQUE ET PARTAGE D'IP
# =====================================================================

def obtenir_ip_locale():
    """Détermine l'IP réelle de ce PC Saisisseur sur le réseau de l'usine"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Permet de trouver l'IP sans envoyer de données
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

if __name__ == "__main__":
    initialiser_bdd()
    
    ip_saisisseur = obtenir_ip_locale()
    url_base = f"http://{ip_saisisseur}:5000"
    
    # Écriture de l'IP du jour dans le dossier réseau partagé
    try:
        chemin_fichier_ip = os.path.join(DOSSIER_APP, "adresse_serveur.txt")
        with open(chemin_fichier_ip, "w") as f:
            f.write(url_base)
        print(f"✅ Adresse réseau enregistrée : {url_base}")
    except Exception as e:
        print(f"⚠️ Erreur écriture adresse partagée : {e}")

    print("\n" + "="*60)
    print(f"🚀 SERVEUR SPC DÉMARRÉ SUR LE PC SAISISSEUR")
    print(f"👉 Saisie active : {url_base}")
    print(f"👉 Historique disponible pour les autres : {url_base}/historique")
    print("="*60 + "\n")
    
    def ouvrir_navigateur():
        webbrowser.open(url_base)
        
    Timer(1, ouvrir_navigateur).start()
    
    # 0.0.0.0 permet d'écouter les requêtes venant de tous les PC de l'usine
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
