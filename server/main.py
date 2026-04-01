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
        nombreDeJours = 30 
        
        rootTest = "C:\\Users\\pebec\\Documents\\Projets perso\\Scrap edt\\server\\"
        pathIcs = "app" + "/partage"
        pathJson = "app" + "/jsonAPI"

        os.makedirs(pathIcs, exist_ok=True)
        os.makedirs(pathJson, exist_ok=True)

        print(f"\n[LOG] Execution started: {datetime.datetime.now()}")

        # Step 1: Authentication
        r2 = authenticationSSO(email)
        if r2 is None: raise Exception("Failed at SSO/WAYF step")

        r3 = authenticationADFS(r2, email, mdp)
        if r3 is None: raise Exception("Failed at ADFS step")

        authenticationSAML(r3)

        # Step 2: Data retrieval and conversion
        recupererDonnees(nombreDeJours, pathJson)
        mainCon(pathIcs, pathJson)

        print(f"[LOG] Execution completed successfully at {datetime.datetime.now()}")

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Network error detected: {e}")
    except Exception as e:
        # Handle all other errors (Logic, files, etc.)
        print(f"[ERROR] An unexpected error occurred: {e}")



if __name__ == "__main__":
    schedule.every().day.at("22:30").do(execution)

    execution()

    while True:
            try:
                schedule.run_pending()
            except Exception as e:
                print(f"[WARNING] Error in schedule loop: {e}")
            
            time.sleep(60)