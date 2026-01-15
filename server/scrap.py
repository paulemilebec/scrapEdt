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
    # autentification SSO via le protocole SAML
    # WAYF
    # SAML (formulaire automatique)

    session = requests.Session()

    print("\n-------------- Début du scraping --------------")

    print("1. INITIALISATION (WAYF)")
    
    # 1️. Requête GET initiale vers le service WAYF avec l'email pour obtenir la redirection ADFS.
    urlWayf = f"https://wayf.cesi.fr/login?client_name=ClientIdpViaCesiFr&needs_client_redirection=true&UserName={email}"
    r1 = session.get(urlWayf)
    if r1.status_code != 200:
        print("❌ Échec de la connexion au WAYF.")
        return None
    
    print(f"✅ Connexion au WAYF réussie -> Status: {r1.status_code}")

    # --- Étape intermédiaire d'auto-soumission SAML ---
    soup = BeautifulSoup(r1.text, "html.parser")
    form = soup.find("form")
    if form and form.get("action"):
        actionUrl = html.unescape(form["action"])
        relayState = html.unescape(form.find("input", {"name": "RelayState"})["value"])
        samlRequest = html.unescape(form.find("input", {"name": "SAMLRequest"})["value"])
        # POST de l'auto-soumission pour arriver à la vraie page de login ADFS.
        # envoie le ticket SAML au serveur d'identité (ADFS).
        r2 = session.post(actionUrl, data={"RelayState": relayState, "SAMLRequest": samlRequest})
    else:
        r2 = r1 # Si pas d'auto-submit, r2 est r1

    print("✅ Formulaire auto-soumission SAML complété")
    return r2


def authenticationADFS(r2, email, mdp):
    global session
    print("\n2. AUTHENTIFICATION ADFS (Login/Mdp)")
    
    # 2️. Analyse du formulaire de login ADFS.
    soupAdfs = BeautifulSoup(r2.text, "html.parser")
    formAdfs = soupAdfs.find("form")
    if formAdfs is None:
        print("❌ Échec de la récupération du formulaire ADFS.")
        return None
    
    print("✅ Le formulaire ADFS a été récupéré correctement")


    # Extraction des champs cachés et de l'URL d'action.
    actionAdfs = html.unescape(formAdfs["action"])
    actionAdfsAbsolute = urljoin(r2.url, actionAdfs)
    dataAdfs = {i.get("name"): i.get("value", "") 
                 for i in formAdfs.find_all("input") if i.get("name")}

    # Ajout des identifiants (mot de passe et email).
    dataAdfs["UserName"] = email
    dataAdfs["Password"] = mdp
    
    # 3️. POST des identifiants vers ADFS.
    r3 = session.post(actionAdfsAbsolute, data=dataAdfs)
    if r3.status_code != 200:
        print("❌ Échec de l'authentification ADFS.")
        return None
    print(f"✅ ADFS Login réussi -> Status: {r3.status_code}")
    
    if "Opération en cours..." not in r3.text:
         print("❌ Erreur d'authentification ADFS (mauvais mot de passe ou ADFS a changé).")
         return None
    return r3


def authenticationSAML(r3):
    global session
    print("\n3. FÉDÉRATION SAML (Transfert de Jeton)")
    
    # 4️. Analyse du formulaire de réponse SAML (jeton d'identité).
    soupSaml = BeautifulSoup(r3.text, "html.parser")
    samlForm = soupSaml.find("form")
    if samlForm is None:
        print("❌ Formulaire SAML (réponse) introuvable après login ADFS.")
        return None
    print("✅ Formulaire SAML (réponse) récupéré avec succès.")

    # Extraction de l'action URL et des champs SAML (SAMLResponse, RelayState).
    actionSaml = html.unescape(samlForm["action"])
    samlData = {i.get("name"): i.get("value", "") 
                 for i in samlForm.find_all("input") if i.get("name")}

    # 5️. POST du jeton SAML vers l'ENT/WAYF pour finaliser la connexion.
    r4 = session.post(actionSaml, data=samlData, allow_redirects=True)
    if r4.status_code != 200:
        print("❌ Échec de la soumission SAML finale.")
        return None
    print(f"✅ SAML POST réussi -> URL finale: {r4.url}")

    # 6️. Vérification finale de l'accès à l'ENT.
    entUrl = "https://ent.cesi.fr/mon-emploi-du-temps"
    r5 = session.get(entUrl) # GET pour s'assurer que les cookies sont bien positionnés

    if "mon-emploi-du-temps" in r5.url:
        print("✅ CONNEXION RÉUSSIE à l'ENT.")
    else:
        print("❌ ÉCHEC de la connexion à l'ENT. (Redirection incorrecte)")
        return None
    

def recupererDonnees(nombreDeJours, pathJson):
    global session
    # requete GET final avec session
    dataJson = [] 
    jsonPeriodeEntreprise = [{
        "code": "ENT-2026",
        "title": "Période en entreprise",
        "allDay": True,
        "nightly": True,
        "start": "modif",
        "end": "modif",
        "nomModule": "ENTREPRISE",
        "matiere": "Période en entreprise",
        "salles": [{"nomSalle": "ENTREPRISE"}],
        "intervenants": [],
        "participants": [{"libelleGroupe": "FISA INFO 25 28 Rouen"}]
    }]

    for i in range(nombreDeJours):
        dateObjet = date.today() + timedelta(days=i)
        dateCible = dateObjet.strftime("%Y-%m-%d")
        
        #  booleen : 5 = Samedi 6 = Dimanche
        estWeekEnd = dateObjet.weekday() >= 5

        apiUrl = f"https://ent.cesi.fr/api/seance/all?start={dateCible}&end={dateCible}&codePersonne=2660723&_=1764341401797"

        try:
            response = session.get(apiUrl, timeout=10)
            response.raise_for_status()
            seances = response.json()
            
            if not seances:
                raise ValueError("Aucune séance école trouvée")
            
            dataJson.extend(seances)

        except Exception as e:
            # ne pas ajouter de periode entreprise le we
            if not estWeekEnd:
                print(f"⚠️ Jour {dateCible} : Période entreprise détectée.")
                entJour = jsonPeriodeEntreprise[0].copy()
                entJour["start"] = f"{dateCible}T08:30:00+01"
                entJour["end"] = f"{dateCible}T17:30:00+01"
                entJour["code"] = f"ENT-{dateCible}"
                dataJson.append(entJour)
            else:
                print(f"⚠️ Jour {dateCible} : Week-end, rien à ajouter.")

    # enregistrement du fichier
    timestamp = datetime.now().strftime("%d-%m-%Y_%Hh%M")
    
    # Docker : CHEMIN VERS VOLUME !!!!!
    nomFichier = os.path.join(pathJson, f"{timestamp}.json")
    
    with open(nomFichier, 'w', encoding='utf-8') as f:
        json.dump(dataJson, f, ensure_ascii=False, indent=4)
        
    print(f"✅ {len(dataJson)} séances/jours enregistrés dans : {nomFichier}")
    return None