from asyncio import exceptions

from scrap import authenticationSSO, authenticationADFS, recupererDonnees, authenticationSAML
from convertissor import mainCon
from dotenv import load_dotenv
import requests
import datetime
import schedule
import time
import os


def execution():
    try:
        # Environment variables
        load_dotenv()
        email = os.getenv("EMAIL")
        mdp = os.getenv("MDP")
        nombreDeJours = 3 
        
        pathIcs = "/app/ics"
        pathJson = "/app/jsonAPI"

        os.makedirs(pathIcs, exist_ok=True)
        os.makedirs(pathJson, exist_ok=True)

        print(f"\n[LOG] Execution started: {datetime.datetime.now()}")

        # Step 1: Authentication
        # CORRECTION : On récupère la session ET la réponse r2 séparément
        result_sso = authenticationSSO()
        if result_sso is None: 
            raise Exception("Failed at SSO/WAYF step")
        
        session, r2 = result_sso # Déstructuration du tuple

        # CORRECTION : On passe bien la session en premier argument
        r3 = authenticationADFS(session, r2, email, mdp)
        if r3 is None: 
            raise Exception("Failed at ADFS step")

        # CORRECTION : On passe la session
        auth_saml_ok = authenticationSAML(session, r3)
        if not auth_saml_ok:
            raise Exception("Failed at SAML step")

        # Step 2: Data retrieval and conversion
        # CORRECTION : On passe la session
        recupererDonnees(session, nombreDeJours, pathJson)
        mainCon(pathIcs, pathJson)

        print(f"[LOG] Execution completed successfully at {datetime.datetime.now()}")

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Network error detected: {e}")
    except Exception as e:
        # Pratique pour le debug : affiche la pile d'erreur complète (traceback)
        import traceback
        print(f"[ERROR] An unexpected error occurred: {e}")
        traceback.print_exc()



if __name__ == "__main__":
    schedule.every().day.at("22:30").do(execution)

    execution()

    while True:
            try:
                schedule.run_pending()
            except Exception as e:
                print(f"[WARNING] Error in schedule loop: {e}")
            
            time.sleep(60)