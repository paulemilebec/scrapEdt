import hashlib
from icalendar import Calendar, Event, vCalAddress
from datetime import datetime
import json
import os


def cleanOldFiles(pathJson, max_files=7):
    """Remove the oldest JSON files if the limit is exceeded."""
    try:
        # List only .json files
        files = [f for f in os.listdir(pathJson) if f.endswith(".json")]
        
        if len(files) > max_files:
            # Create a list of tuples (filename, modification_date)
            files_with_time = []
            for f in files:
                full_path = os.path.join(pathJson, f)
                files_with_time.append((full_path, os.path.getmtime(full_path)))
            
            # Sort by date (oldest first)
            files_with_time.sort(key=lambda x: x[1])
            
            # Number of files to delete
            to_delete_count = len(files_with_time) - max_files
            
            print(f"[CLEANUP] {to_delete_count} old file(s) detected beyond limit ({max_files}).")
            
            for i in range(to_delete_count):
                file_to_remove = files_with_time[i][0]
                os.remove(file_to_remove)
                print(f"[DELETED] {os.path.basename(file_to_remove)}")
                
    except Exception as e:
        print(f"[WARNING] Error during file cleanup: {e}")


def convert(fileName, cal_global, UIDS_DEJA_VUS, pathJson):
    completPathJson = os.path.join(pathJson, fileName)
    try:
        with open(completPathJson, "r", encoding="utf-8") as f:
            dataJson = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read JSON file {fileName}: {e}")
        # On retourne None pour signaler une ERREUR technique
        return None 
    
    evenementsAjoutes = 0
    
    # Vérification que le JSON est bien une liste
    if not isinstance(dataJson, list):
        print(f"[WARNING] Invalid format in {fileName}: Expected a list.")
        # Format invalide = Erreur technique
        return None

    for seance in dataJson:
        try:
            if processClass(seance, UIDS_DEJA_VUS, cal_global):
                evenementsAjoutes += 1
        except Exception as e:
            print(f"[WARNING] Error processing session in {fileName}: {e}")
            continue
            
    # On retourne un nombre (0 ou plus) pour signaler un SUCCÈS
    return evenementsAjoutes

def processClass(seance, UIDS_DEJA_VUS, cal_global):
    if not isinstance(seance, dict):
        return False

    startVal = seance.get('start') or ''
    titleVal = seance.get('title') or ''
    codeVal = seance.get('code')
    
    if codeVal is not None:
        uid = str(codeVal)
    else:
        seed = f"{startVal}{titleVal}"
        uid = hashlib.md5(seed.encode('utf-8')).hexdigest()
    
    fullUid = f"{uid}@ent.cesi.fr"

    # Duplicate check
    if fullUid in UIDS_DEJA_VUS:
        return False
    
    UIDS_DEJA_VUS.add(fullUid)

    # Build event fields
    summary = titleVal or 'Cours sans titre'
    if titleVal == "A planifier":
        summary = "Autonomie"

    categoriesList = []
    if summary == "Autonomie": categoriesList.append("Autonomie")
    elif summary == "Anglais": categoriesList.append("Anglais")
    elif "Prosit" in summary: categoriesList.append("Prosit")
    elif "Workshop" in summary: categoriesList.append("Workshop")
    
    # Rooms (safely handle None values)
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
    
    # Instructors
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
        # Invalid event if no date is present
        return False

    # Exclude Thursday afternoon sessions (13:30 - 17:30)
    HEURE_MIN = "13:30"
    HEURE_MAX = "17:30"
    if dtstart.weekday() == 3:  # 3 = Thursday
        if dtstart.strftime("%H:%M") == HEURE_MIN and dtend.strftime("%H:%M") == HEURE_MAX:
            print(f"[EXCLUDED] {summary} on Thursday (13:30-17:30).")
            return False

    # Create iCal event
    event = Event()
    event.add('categories', categoriesList)
    event.add('summary', summary)
    event.add('dtstart', dtstart)
    event.add('dtend', dtend)
    event.add('location', salles)
    event.add('description', description)
    event.add('uid', fullUid)
    
    # Organizer
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
    # Step 1: Cleanup old files before processing
    cleanOldFiles(pathJson, max_files=7)

    cal_final = Calendar()
    cal_final.add('prodid', '-//Emploi du temps CESI//fr')
    cal_final.add('version', '2.0')
    cal_final.add('X-WR-CALNAME', 'Emploi du temps CESI')
    
    uids_vus = set()
    totalEvenementsAjoutes = 0
    fichiersTraites = 0

    print("\n-------------- Starting merge process --------------")
    
    try:
        if not os.path.exists(pathJson):
            print(f"\n[ERROR] Source directory {pathJson} not found.")
            return

        # Process remaining files (max 7 after cleanup)
        for file in os.listdir(pathJson):
            if file.endswith(".json"):
                fichiersTraites += 1
                print(f"[PROCESSING] File: {file}...")
                evenementsAjoutes = convert(file, cal_final, uids_vus, pathJson)
                if evenementsAjoutes is not None:
                    totalEvenementsAjoutes += evenementsAjoutes
        
        nomFichierFinal = "emploisDuTemps.ics"
        cheminFinalIcs = os.path.join(pathIcs, nomFichierFinal)
        
        with open(cheminFinalIcs, 'wb') as f:
            f.write(cal_final.to_ical())
            
        print("-" * 40)
        print(f"[SUCCESS] Completed: {fichiersTraites} files merged.")
        print(f"Output file: {cheminFinalIcs}")

    except Exception as e:
        print(f"\n[ERROR] Unexpected error during merge: {e}")