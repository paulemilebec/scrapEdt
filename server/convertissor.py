from icalendar import Calendar, Event, vCalAddress
from datetime import datetime
import json
import os


def convert(fileName, cal_global, UIDS_DEJA_VUS, pathJson):
    completPathJson = os.path.join(pathJson, fileName)
    
    try:
        with open(completPathJson, "r", encoding="utf-8") as f:
            dataJson = json.load(f)
    except Exception as e:
        print(f"❌ Erreur de lecture du fichier JSON {fileName}: {e}")
        return 0

    evenementsAjoutes = 0
    
    # Vérification que le JSON est bien une liste de séances
    if isinstance(dataJson, list):
        for seance in dataJson:
            try:
                # On n'incrémente le compteur que si processClass réussit
                if processClass(seance, UIDS_DEJA_VUS, cal_global):
                    evenementsAjoutes += 1
            except Exception as e:
                # Si une séance pose problème, on l'affiche mais on continue la boucle
                print(f"⚠️ Erreur sur une séance dans {fileName}: {e}")
                continue
    else:
        print(f"⚠️ Le fichier {fileName} ne contient pas une liste de séances valide (Type: {type(dataJson)}).")
        
    return evenementsAjoutes

def processClass(seance, UIDS_DEJA_VUS, cal_global):
    if not isinstance(seance, dict):
        return False

    startVal = seance.get('start') or ''
    titleVal = seance.get('title') or ''
    codeVal = seance.get('code')
    
    # Création de l'UID
    uid = str(codeVal if codeVal is not None else hash(startVal + titleVal))
    fullUid = f"{uid}@ent.cesi.fr"

    # Vérification doublons
    if fullUid in UIDS_DEJA_VUS:
        return False
    
    UIDS_DEJA_VUS.add(fullUid)

    # --- Construction des champs ---
    summary = titleVal or 'Cours sans titre'
    if titleVal == "A planifier":
        summary = "Autonomie"

    categoriesList = []
    if summary == "Autonomie": categoriesList.append("Autonomie")
    elif summary == "Anglais": categoriesList.append("Anglais")
    elif "Prosit" in summary: categoriesList.append("Prosit")
    elif "Workshop" in summary: categoriesList.append("Workshop")
    
    # Salles (Sécurisé contre le None)
    salles_raw = seance.get('salles') or []
    salles_list = []
    if isinstance(salles_raw, list):
        for s in salles_raw:
            if isinstance(s, dict) and s.get('nomSalle'):
                salles_list.append(s.get('nomSalle'))
    
    salles = ", ".join(salles_list) if salles_list else ""
    
    description_lines = [
        f"Matière: {seance.get('matiere') or seance.get('theme', 'N/A')}",
        f"Lieu: {salles}",
    ]
    
    # Intervenants
    intervenants = seance.get('intervenants') or []
    nomsProfs = []
    if isinstance(intervenants, list):
        for i in intervenants:
            if isinstance(i, dict):
                prenom = (i.get('prenom') or '').strip()
                nom = (i.get('nom') or '').strip()
                nom_complet = f"{prenom} {nom}".strip()
                if nom_complet:
                    nomsProfs.append(nom_complet)        
    
    if nomsProfs:
        description_lines.append(f"Intervenant(s): {', '.join(nomsProfs)}")
    
    # Participants
    participants = seance.get('participants') or []
    groupes = []
    if isinstance(participants, list):
        for p in participants:
            if isinstance(p, dict) and p.get('libelleGroupe'):
                groupes.append(p.get('libelleGroupe'))
    
    if groupes:
        description_lines.append(f"Groupe(s): {', '.join(groupes)}")

    description = "\n".join(description_lines)

    # Dates
    try:
        dtstart = datetime.fromisoformat(seance['start'])
        dtend = datetime.fromisoformat(seance['end'])
    except Exception:
        # Si pas de date, l'événement est invalide
        return False

    # Suppression Jeudi après-midi (13:30 - 17:30)
    HEURE_MIN = "13:30"
    HEURE_MAX = "17:30"
    if dtstart.weekday() == 3: # 3 = Jeudi
        if dtstart.strftime("%H:%M") == HEURE_MIN and dtend.strftime("%H:%M") == HEURE_MAX:
            print(f"⚙️ Exclusion : {summary} le Jeudi (13h30-17h30).")
            return False

    # Création de l'événement iCal
    event = Event()
    event.add('categories', categoriesList)
    event.add('summary', summary)
    event.add('dtstart', dtstart)
    event.add('dtend', dtend)
    event.add('location', salles)
    event.add('description', description)
    event.add('uid', fullUid)
    
    # Organisateur
    if isinstance(intervenants, list):
        for i in intervenants:
            if isinstance(i, dict) and i.get('adresseMail'):
                organizer = vCalAddress(f'MAILTO:{i.get("adresseMail")}')
                cn = f"{i.get('prenom','') or ''} {i.get('nom','') or ''}".strip()
                if cn: organizer.params['cn'] = cn
                event['organizer'] = organizer
                break
                
    cal_global.add_component(event)
    return True



def mainCon(pathIcs, pathJson):
    # Initialisation du Calendrier Global pour la Fusion
    cal_final = Calendar()
    cal_final.add('prodid', '-//Emploi du temps CESI//fr')
    cal_final.add('version', '2.0')
    cal_final.add('X-WR-CALNAME', 'Emploi du temps CESI')
    
    # Structure de données pour la déduplication
    uids_vus = set()
    totalEvenementsAjoutes = 0
    fichiersTraites = 0

    print("\n\n-------------- Démarrage de la fusion --------------")
    
    try:
        # Parcourt tous les fichiers JSON dans le répertoire source
        if not os.path.exists(pathJson):
            print(f"\n❌ Erreur : Le répertoire source {pathJson} est introuvable. Veuillez vérifier le chemin.")
            return


        for file in os.listdir(pathJson):
            if file.endswith(".json"):
                fichiersTraites += 1
                print(f"⚙️ Traitement du fichier : {file}...")
                
                # Appelle la fonction convert() pour ajouter les événements uniques au cal_final
                evenementsAjoutes = convert(file, cal_final, uids_vus, pathJson)
                if evenementsAjoutes is not None:
                    totalEvenementsAjoutes += evenementsAjoutes
        
        # Écriture du fichier .ics final
        
        nomFichierFinal = "emploisDuTemps" + ".ics" #os.path.splitext(file)[0]
        cheminFinalIcs = os.path.join(pathIcs, nomFichierFinal)
        
        # Écriture du contenu binaire du calendrier
        with open(cheminFinalIcs, 'wb') as f:
            f.write(cal_final.to_ical())
            
        print("-" * 40)
        print(f"✅ Conversion et fusion réussies après traitement de {fichiersTraites} fichiers.")
        print(f"Nombre total d'événements uniques enregistrés : {totalEvenementsAjoutes}")
        print(f"Fichier final sauvegardé dans : {cheminFinalIcs}")
        print("Vous pouvez importer ce fichier unique dans votre logiciel de calendrier.")

    except FileNotFoundError:
        print(f"\n❌ Erreur : Le répertoire source {pathJson} est introuvable. Veuillez vérifier le chemin.")
    except Exception as e:
        print(f"\n❌ Erreur inattendue lors de la fusion : {e}")


