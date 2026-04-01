from datetime import datetime, timezone
from icalendar import Calendar, Event, vCalAddress
import hashlib
import json
import os
import re

def cleanOldFiles(pathJson, max_files=7):
    """Supprime les fichiers JSON les plus anciens si la limite est dépassée."""
    try:
        files = [f for f in os.listdir(pathJson) if f.endswith(".json")]
        if len(files) > max_files:
            files_with_time = []
            for f in files:
                full_path = os.path.join(pathJson, f)
                files_with_time.append((full_path, os.path.getmtime(full_path)))
            
            files_with_time.sort(key=lambda x: x[1])
            to_delete_count = len(files_with_time) - max_files
            
            for i in range(to_delete_count):
                file_to_remove = files_with_time[i][0]
                os.remove(file_to_remove)
    except Exception as e:
        print(f"[WARNING] Erreur lors du nettoyage : {e}")

def processClass(seance, UIDS_DEJA_VUS, cal_global):
    """Traite une séance individuelle et l'ajoute au calendrier si valide."""
    if not isinstance(seance, dict):
        return False

    # 1. GESTION DES DATES (Correction UTC & DTSTAMP pour Outlook)
    try:
        dtstart = datetime.fromisoformat(seance['start']).astimezone(timezone.utc)
        dtend = datetime.fromisoformat(seance['end']).astimezone(timezone.utc)
        dtstamp = datetime.now(timezone.utc)
    except Exception:
        return False

    # 2. EXCLUSION JEUDI APRÈS-MIDI (13:30 - 17:30)
    # On compare en heure locale pour que les créneaux correspondent au planning CESI
    local_start = datetime.fromisoformat(seance['start'])
    local_end = datetime.fromisoformat(seance['end'])
    if local_start.weekday() == 3:  # 3 = Jeudi
        if local_start.strftime("%H:%M") == "13:30" and local_end.strftime("%H:%M") == "17:30":
            print(f"[EXCLUDED] {seance.get('title')} on Thursday afternoon.")
            return False

    # 3. FIX VOLATILITÉ UID
    code_unique_cesi = seance.get('code')
    if code_unique_cesi:
        uid_str = str(code_unique_cesi)
    else:
        matiere = seance.get('matiere') or seance.get('title') or 'unknown'
        jour = dtstart.strftime("%Y%m%d")
        seed = f"{matiere}-{jour}"
        uid_str = hashlib.md5(seed.encode('utf-8')).hexdigest()
    
    fullUid = f"{uid_str}@ent.cesi.fr"

    if fullUid in UIDS_DEJA_VUS:
        return False
    UIDS_DEJA_VUS.add(fullUid)

    # 4. CHAMPS TEXTE & CATÉGORIES
    titleVal = seance.get('title') or 'Cours sans titre'
    summary = "Autonomie" if titleVal == "A planifier" else titleVal

    categoriesList = []
    if summary == "Autonomie": categoriesList.append("Autonomie")
    elif summary == "Anglais": categoriesList.append("Anglais")
    elif "Prosit" in summary: categoriesList.append("Prosit")
    elif "Workshop" in summary: categoriesList.append("Workshop")

    # Salles
    salles_raw = seance.get('salles') or []
    salles_list = [s.get('nomSalle') for s in salles_raw if isinstance(s, dict) and s.get('nomSalle')]
    salles = ", ".join(salles_list)

    # Intervenants
    intervenants = seance.get('intervenants') or []
    nomsProfs = [f"{(i.get('prenom') or '').strip()} {(i.get('nom') or '').strip()}".strip() 
                 for i in intervenants if isinstance(i, dict)]
    
    # Participants
    participants = seance.get('participants') or []
    groupes = [p.get('libelleGroupe') for p in participants if isinstance(p, dict) and p.get('libelleGroupe')]

    description = "\n".join(filter(None, [
        f"Matière: {seance.get('matiere') or seance.get('theme', 'N/A')}",
        f"Lieu: {salles}",
        f"Intervenant(s): {', '.join(nomsProfs)}" if nomsProfs else None,
        f"Groupe(s): {', '.join(groupes)}" if groupes else None
    ]))
    
    # 5. CRÉATION EVENT
    summary = clean_text(seance.get('title'))
    salles = ", ".join(salles_list)
    description = clean_text(description).replace('\n', '\\n')

    event = Event()
    event.add('uid', fullUid)
    event.add('dtstamp', dtstamp) 
    event.add('dtstart', dtstart)
    event.add('dtend', dtend)
    event.add('summary', summary)
    event.add('location', salles)
    event.add('description', description)
    event.add('categories', categoriesList)
    
    # Organisateur
    for i in intervenants:
        if isinstance(i, dict) and i.get('adresseMail'):
            organizer = vCalAddress(f'MAILTO:{i.get("adresseMail")}')
            cn = f"{i.get('prenom','')} {i.get('nom','')}".strip()
            if cn: organizer.params['cn'] = cn
            event['organizer'] = organizer
            break
                
    cal_global.add_component(event)
    return True

def convert(fileName, cal_global, UIDS_DEJA_VUS, pathJson):
    completPathJson = os.path.join(pathJson, fileName)
    try:
        with open(completPathJson, "r", encoding="utf-8") as f:
            dataJson = json.load(f)
    except Exception:
        return None 
    
    if not isinstance(dataJson, list): return None

    evenementsAjoutes = 0
    for seance in dataJson:
        if processClass(seance, UIDS_DEJA_VUS, cal_global):
            evenementsAjoutes += 1
    return evenementsAjoutes


def clean_text(text):
    if not text:
        return ""
    text = text.replace('\xa0', ' ')
    text = " ".join(text.split())
    return text


def mainCon(pathIcs, pathJson):
    print("\n-------------- Starting merge process --------------")
    
    # Step 1: Nettoyage
    cleanOldFiles(pathJson, max_files=7)

    # Step 2: Init Calendrier avec en-têtes de rafraîchissement
    cal_final = Calendar()
    cal_final.add('prodid', '-//Emploi du temps CESI//fr')
    cal_final.add('version', '2.0')
    cal_final.add('X-WR-CALNAME', 'Emploi du temps CESI')
    cal_final.add('X-PUBLISHED-TTL', 'PT15M')
    cal_final.add('X-WR-RECALC-DESC', 'PT15M')
    cal_final.add('REFRESH-INTERVAL;VALUE=DURATION', 'PT15M')
    
    uids_vus = set()
    totalEvenementsAjoutes = 0
    fichiersTraites = 0

    try:
        if not os.path.exists(pathJson):
            print(f"[ERROR] Source directory {pathJson} not found.")
            return

        for file in os.listdir(pathJson):
            if file.endswith(".json"):
                fichiersTraites += 1
                print(f"[PROCESSING] File: {file}...")
                evenementsAjoutes = convert(file, cal_final, uids_vus, pathJson)
                if evenementsAjoutes is not None:
                    totalEvenementsAjoutes += evenementsAjoutes
        
        cheminFinalIcs = os.path.join(pathIcs, "emploisDuTemps.ics")
        with open(cheminFinalIcs, 'wb') as f:
            f.write(cal_final.to_ical())
            
        print("-" * 40)
        print(f"[SUCCESS] Completed: {fichiersTraites} files merged.")
        print(f"Total events: {totalEvenementsAjoutes}")
        print(f"Output file: {cheminFinalIcs}")

    except Exception as e:
        print(f"\n[ERROR] Unexpected error during merge: {e}")