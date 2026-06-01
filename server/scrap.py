import os
import json
import html
from datetime import datetime, date, timedelta
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def initialiserSession():
    """Crée et configure la session de manière globale."""
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return session


def authenticationSSO(session):
    """
    SSO authentication via SAML protocol.
    Handles WAYF redirection and SAML form auto-submission.
    """
    print("\n-------------- Starting scraping process --------------")
    print("1. INITIALIZATION (WAYF)")
    
    # Step 1: Initial GET request to WAYF service with email to obtain ADFS redirection.
    email = os.getenv("EMAIL")
    urlWayf = f"https://wayf.cesi.fr/login?client_name=ClientIdpViaCesiFr&needs_client_redirection=true&UserName={email}"
    r1 = session.get(urlWayf)
    if r1.status_code != 200:
        print("[ERROR] Failed to connect to WAYF.")
        return None
    
    print(f"[SUCCESS] Connected to WAYF -> Status: {r1.status_code}")

    # Intermediate SAML auto-submission step
    soup = BeautifulSoup(r1.text, "html.parser")
    form = soup.find("form")
    if form and form.get("action"):
        actionUrl = html.unescape(form["action"])
        relayState = html.unescape(form.find("input", {"name": "RelayState"})["value"])
        samlRequest = html.unescape(form.find("input", {"name": "SAMLRequest"})["value"])
        
        # POST auto-submission to reach the actual ADFS login page.
        r2 = session.post(actionUrl, data={"RelayState": relayState, "SAMLRequest": samlRequest})
    else:
        r2 = r1  # If no auto-submit, r2 is r1

    print("[SUCCESS] SAML auto-submission form completed")
    return r2


def authenticationADFS(session, r2, email, mdp):
    print("\n2. ADFS AUTHENTICATION (Login/Password)")
    
    # Step 2: Parse the ADFS login form.
    soupAdfs = BeautifulSoup(r2.text, "html.parser")
    formAdfs = soupAdfs.find("form")
    if formAdfs is None:
        print("[ERROR] Failed to retrieve ADFS form.")
        return None
    
    print("[SUCCESS] ADFS form retrieved successfully")

    # Extract hidden fields and action URL.
    actionAdfs = html.unescape(formAdfs["action"])
    actionAdfsAbsolute = urljoin(r2.url, actionAdfs)
    dataAdfs = {i.get("name"): i.get("value", "") 
                 for i in formAdfs.find_all("input") if i.get("name")}

    # Add credentials (email and password).
    dataAdfs["UserName"] = email
    dataAdfs["Password"] = mdp
    
    # Step 3: POST credentials to ADFS.
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
    
    # Step 4: Parse the SAML response form (identity token).
    soupSaml = BeautifulSoup(r3.text, "html.parser")
    samlForm = soupSaml.find("form")
    if samlForm is None:
        print("[ERROR] SAML response form not found after ADFS login.")
        return False
    print("[SUCCESS] SAML response form retrieved successfully.")

    # Extract action URL and SAML fields (SAMLResponse, RelayState).
    actionSaml = html.unescape(samlForm["action"])
    samlData = {i.get("name"): i.get("value", "") 
                 for i in samlForm.find_all("input") if i.get("name")}

    # Step 5: POST SAML token to ENT/WAYF to finalize connection.
    r4 = session.post(actionSaml, data=samlData, allow_redirects=True)
    if r4.status_code != 200:
        print("[ERROR] Final SAML submission failed.")
        return False
    print(f"[SUCCESS] SAML POST successful -> Final URL: {r4.url}")

    # Step 6: Final verification of ENT access.
    entUrl = "https://ent.cesi.fr/mon-emploi-du-temps"
    r5 = session.get(entUrl)  # GET to ensure cookies are properly set

    if "mon-emploi-du-temps" in r5.url:
        print("[SUCCESS] Connected to ENT successfully.")
        return True
    else:
        print("[ERROR] Failed to connect to ENT. (Incorrect redirection)")
        return False
    

def recupererDonnees(session, nombreDeJours, pathJson):
    dataJson = [] 
    
    # Template de base pour l'entreprise
    entrepriseTemplate = {
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
        
        apiUrl = f"https://ent.cesi.fr/api/seance/all?start={dateCible}&end={dateCible}&codePersonne=2660723&_=1764341401797"

        try:
            response = session.get(apiUrl, timeout=10)
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
                    entJour = entrepriseTemplate.copy()
                    entJour.update({
                        "start": f"{dateCible}T08:30:00+01",
                        "end": f"{dateCible}T17:30:00+01",
                        "code": f"ENT-{dateCible}"
                    })
                    dataJson.append(entJour)

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Impossible de vérifier le jour {dateCible} (Erreur réseau) : {e}")
            continue 

    # --- SAUVEGARDE SÉCURISÉE (Écriture atomique) ---
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