from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests
import html
import json
import os
import time

def authenticationSSO():
    """
    SSO authentication via SAML protocol.
    Handles WAYF redirection and SAML form auto-submission.
    """
    session = requests.Session()

    # Intégration du certificat local si présent
    cert_path = "/app/cesi-fr-chain.pem"
    if os.path.exists(cert_path):
        session.verify = cert_path
        print("[INFO] Certificat SSL CESI chargé avec succès.")
    else:
        session.verify = True

    # Ajout d'un User-Agent standard pour éviter d'être catégorisé comme robot brut
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    print("\n-------------- Starting scraping process --------------")
    print("1. INITIALIZATION (WAYF)")
    
    urlWayf = f"https://wayf.cesi.fr/login?client_name=ClientIdpViaCesiFr&needs_client_redirection=true&UserName={os.getenv('EMAIL')}"
    r1 = session.get(urlWayf)
    if r1.status_code != 200:
        print("[ERROR] Failed to connect to WAYF.")
        return None
    
    print(f"[SUCCESS] Connected to WAYF -> Status: {r1.status_code}")

    soup = BeautifulSoup(r1.text, "html.parser")
    form = soup.find("form")
    if form and form.get("action"):
        actionUrl = html.unescape(form["action"])
        relayState = html.unescape(form.find("input", {"name": "RelayState"})["value"])
        samlRequest = html.unescape(form.find("input", {"name": "SAMLRequest"})["value"])
        r2 = session.post(actionUrl, data={"RelayState": relayState, "SAMLRequest": samlRequest})
    else:
        r2 = r1

    print("[SUCCESS] SAML auto-submission form completed")
    return session, r2


def authenticationADFS(session, r2, email, mdp):
    print("\n2. ADFS AUTHENTICATION (Login/Password)")
    
    soupAdfs = BeautifulSoup(r2.text, "html.parser")
    formAdfs = soupAdfs.find("form")
    if formAdfs is None:
        print("[ERROR] Failed to retrieve ADFS form.")
        return None
    
    print("[SUCCESS] ADFS form retrieved successfully")

    actionAdfs = html.unescape(formAdfs["action"])
    actionAdfsAbsolute = urljoin(r2.url, actionAdfs)
    dataAdfs = {i.get("name"): i.get("value", "") 
                 for i in formAdfs.find_all("input") if i.get("name")}

    dataAdfs["UserName"] = email
    dataAdfs["Password"] = mdp
    
    r3 = session.post(actionAdfsAbsolute, data=dataAdfs)
    if r3.status_code != 200:
        print("[ERROR] ADFS authentication failed.")
        return None
    print(f"[SUCCESS] ADFS Login successful -> Status: {r3.status_code}")
    
    if "Opération en cours..." not in r3.text:
         print("[ERROR] ADFS authentication error (invalid password or ADFS has changed).")
         return None
    return r3


def authenticationSAML(session, r3):
    print("\n3. SAML FEDERATION (Token Transfer)")
    
    soupSaml = BeautifulSoup(r3.text, "html.parser")
    samlForm = soupSaml.find("form")
    if samlForm is None:
        print("[ERROR] SAML response form not found after ADFS login.")
        return None
    print("[SUCCESS] SAML response form retrieved successfully.")

    actionSaml = html.unescape(samlForm["action"])
    samlData = {i.get("name"): i.get("value", "") 
                 for i in samlForm.find_all("input") if i.get("name")}

    # --- CORRECTION 1 : Suivre agressivement les redirections de l'échange de jetons ---
    r4 = session.post(actionSaml, data=samlData, allow_redirects=True)
    if r4.status_code != 200:
        print("[ERROR] Final SAML submission failed.")
        return None
    print(f"[SUCCESS] SAML POST successful -> Final URL: {r4.url}")

    # Si la redirection nous laisse sur le WAYF, on force le retour vers l'ENT racine pour valider la session
    if "wayf.cesi.fr" in r4.url:
        print("[INFO] Redirection manuelle vers l'ENT pour forcer l'écriture des cookies applicatifs...")
        r4 = session.get("https://ent.cesi.fr/", allow_redirects=True)

    entUrl = "https://ent.cesi.fr/mon-emploi-du-temps"
    r5 = session.get(entUrl, allow_redirects=True)

    if "mon-emploi-du-temps" in r5.url or r5.status_code == 200:
        print("[SUCCESS] Connected to ENT successfully.")
        return r5
    else:
        print("[ERROR] Failed to connect to ENT. (Incorrect redirection)")
        return None
    

def recupererDonnees(session, nombreDeJours, pathJson):
    dataJson = [] 
    
    entreprise_template = {
        "title": "Période en entreprise",
        "allDay": True,
        "nightly": True,
        "nomModule": "ENTREPRISE",
        "matiere": "Période en entreprise",
        "salles": [{"nomSalle": "ENTREPRISE"}],
        "intervenants": [],
        "participants": [{"libelleGroupe": "FISA INFO 25 28 Rouen"}]
    }

    for i in range(nombreDeJours):
        dateObjet = date.today() + timedelta(days=i)
        dateCible = dateObjet.strftime("%Y-%m-%d")
        estWeekEnd = dateObjet.weekday() >= 5
        
        timestamp_actuel = int(time.time() * 1000)
        apiUrl = f"https://ent.cesi.fr/api/seance/all?start={dateCible}&end={dateCible}&codePersonne=2660723&_={timestamp_actuel}"
        print(f"[INFO] API URL : {apiUrl}")

        try:
            # --- CORRECTION 2 : Ajout du Referer et de l'origine (anti-CSRF/403 de Kportal) ---
            headers_api = {
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://ent.cesi.fr/mon-emploi-du-temps",
                "Accept": "application/json, text/javascript, */*; q=0.01"
            }
            response = session.get(apiUrl, headers=headers_api, timeout=10)
            response.raise_for_status() 
            
            if not response.text.strip():
                print(f"[INFO] Jour {dateCible} : Réponse vide reçue, ajout entreprise.")
                seances = []
            else:
                try:
                    seances = response.json()
                except ValueError:
                    print(f"[WARNING] Réponse non-JSON reçue pour le {dateCible}")
                    seances = []
            
            if seances and len(seances) > 0:
                dataJson.extend(seances)
            else:
                if not estWeekEnd:
                    print(f"[INFO] Jour {dateCible} : Pas de cours école, ajout entreprise.")
                    entJour = entreprise_template.copy()
                    entJour.update({
                        "start": f"{dateCible}T08:30:00+01",
                        "end": f"{dateCible}T17:30:00+01",
                        "code": f"ENT-{dateCible}"
                    })
                    dataJson.append(entJour)

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Impossible de vérifier le jour {dateCible} (Erreur réseau) : {e}")
            continue 

    timestamp = datetime.now().strftime("%d-%m-%Y_%Hh%M")
    nomFichierFinal = os.path.join(pathJson, f"{timestamp}.json")
    nomFichierTemp = nomFichierFinal + ".tmp"
    
    try:
        with open(nomFichierTemp, 'w', encoding='utf-8') as f:
            json.dump(dataJson, f, ensure_ascii=False, indent=4)
        os.replace(nomFichierTemp, nomFichierFinal)
        print(f"[SUCCESS] {len(dataJson)} séances enregistrées dans : {nomFichierFinal}")
    except Exception as e:
        print(f"[ERROR] Échec de l'écriture du fichier JSON : {e}")
        if os.path.exists(nomFichierTemp):
            os.remove(nomFichierTemp)

    return None