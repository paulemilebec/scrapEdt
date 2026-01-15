from scrap import authenticationSSO, authenticationADFS, recupererDonnees, authenticationSAML
from convertissor import mainCon
from dotenv import load_dotenv
import datetime
import schedule
import time
import os


def execution():
    # Variables
    load_dotenv()
    email = os.getenv("EMAIL")
    mdp = os.getenv("MDP")
    nombreDeJours = 30 # taille du calendrier en j

    #pathIcs = os.path.join("server", "ics")
    #pathJson = os.path.join("server", "jsonAPI")
    
    pathIcs = "/app/partage" #os.path.join("app", "partage")
    pathJson = "/app/jsonAPI" #os.path.join("app", "jsonAPI")

    os.makedirs(pathIcs, exist_ok=True)
    os.makedirs(pathJson, exist_ok=True)

    #########################################################
    #########################################################

    print(f"Exécution du script à {datetime.datetime.now()}")

    r2 = authenticationSSO(email)
    r3 = authenticationADFS(r2, email, mdp)
    authenticationSAML(r3)
    recupererDonnees(nombreDeJours, pathJson)
    mainCon(pathIcs, pathJson)

    print("Script terminé.")


if __name__ == "__main__":
    schedule.every().day.at("00:00").do(execution)

    execution()

    while True:
        schedule.run_pending()
        time.sleep(60) # chaque minute