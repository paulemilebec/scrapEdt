from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests
import html
import json
import os

global session


def authenticationSSO(email):
    global session
    """
    SSO authentication via SAML protocol.
    Handles WAYF redirection and SAML form auto-submission.
    """

    session = requests.Session()

    print("\n-------------- Starting scraping process --------------")

    print("1. INITIALIZATION (WAYF)")
    
    # Step 1: Initial GET request to WAYF service with email to obtain ADFS redirection.
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
        # Sends the SAML ticket to the identity server (ADFS).
        r2 = session.post(actionUrl, data={"RelayState": relayState, "SAMLRequest": samlRequest})
    else:
        r2 = r1  # If no auto-submit, r2 is r1

    print("[SUCCESS] SAML auto-submission form completed")
    return r2


def authenticationADFS(r2, email, mdp):
    global session
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


def authenticationSAML(r3):
    global session
    print("\n3. SAML FEDERATION (Token Transfer)")
    
    # Step 4: Parse the SAML response form (identity token).
    soupSaml = BeautifulSoup(r3.text, "html.parser")
    samlForm = soupSaml.find("form")
    if samlForm is None:
        print("[ERROR] SAML response form not found after ADFS login.")
        return None
    print("[SUCCESS] SAML response form retrieved successfully.")

    # Extract action URL and SAML fields (SAMLResponse, RelayState).
    actionSaml = html.unescape(samlForm["action"])
    samlData = {i.get("name"): i.get("value", "") 
                 for i in samlForm.find_all("input") if i.get("name")}

    # Step 5: POST SAML token to ENT/WAYF to finalize connection.
    r4 = session.post(actionSaml, data=samlData, allow_redirects=True)
    if r4.status_code != 200:
        print("[ERROR] Final SAML submission failed.")
        return None
    print(f"[SUCCESS] SAML POST successful -> Final URL: {r4.url}")

    # Step 6: Final verification of ENT access.
    entUrl = "https://ent.cesi.fr/mon-emploi-du-temps"
    r5 = session.get(entUrl)  # GET to ensure cookies are properly set

    if "mon-emploi-du-temps" in r5.url:
        print("[SUCCESS] Connected to ENT successfully.")
    else:
        print("[ERROR] Failed to connect to ENT. (Incorrect redirection)")
        return None
    

def recupererDonnees(nombreDeJours, pathJson):
    global session
    dataJson = [] 
    
    # Template de base pour l'entreprise
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
        
        apiUrl = f"https://ent.cesi.fr/api/seance/all?start={dateCible}&end={dateCible}&codePersonne=2660723&_=1764341401797"

        try:
            response = session.get(apiUrl, timeout=10)
            response.raise_for_status() # Lève une erreur si HTTP 4xx ou 5xx
            seances = response.json()
            
            if seances and len(seances) > 0:
                # CAS 1 : Il y a des cours à l'école
                dataJson.extend(seances)
            else:
                # CAS 2 : Réponse OK (200) mais liste vide -> C'est une période entreprise
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
            # CAS 3 : Erreur réseau réelle (Timeout, DNS, 500)
            # On ne déduit rien pour ne pas polluer le calendrier avec des fausses infos
            print(f"[ERROR] Impossible de vérifier le jour {dateCible} (Erreur réseau) : {e}")
            continue 

    # --- SAUVEGARDE SÉCURISÉE (Écriture atomique) ---
    timestamp = datetime.now().strftime("%d-%m-%Y_%Hh%M")
    nomFichierFinal = os.path.join(pathJson, f"{timestamp}.json")
    nomFichierTemp = nomFichierFinal + ".tmp"
    
    try:
        # 1. Écrire dans un fichier temporaire
        with open(nomFichierTemp, 'w', encoding='utf-8') as f:
            json.dump(dataJson, f, ensure_ascii=False, indent=4)
        
        # 2. Renommer le fichier (Opération atomique)
        os.replace(nomFichierTemp, nomFichierFinal)
        print(f"[SUCCESS] {len(dataJson)} séances enregistrées dans : {nomFichierFinal}")
    except Exception as e:
        print(f"[ERROR] Échec de l'écriture du fichier JSON : {e}")
        if os.path.exists(nomFichierTemp):
            os.remove(nomFichierTemp)

    return None