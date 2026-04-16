# Scrap EDT

Scrap EDT genere automatiquement un calendrier ICS depuis l'emploi du temps CESI, puis le rend accessible via une URL que vous pouvez importer dans Outlook, Google Calendar ou Apple Calendar.

## Fonctionnement

Le projet lance deux services Docker.

1. script-runner (Python): authentification SSO/ADFS/SAML, recuperation des seances CESI, generation du fichier ICS, execution immediate au demarrage puis tous les jours a 22:30.
1. web-server (Apache): publication de l'interface web et exposition du fichier ICS dans api_data/emploisDuTemps.ics.

## Arborescence

```text
.
|-- client/
|   |-- Dockerfile
|   |-- index.html
|   |-- app.js
|   `-- style.css
|-- server/
|   |-- Dockerfile
|   |-- main.py
|   |-- scrap.py
|   |-- convertissor.py
|   `-- requirements.txt
|-- docker-compose.yml
`-- README.md
```

## Frontend

Le client est separe en 3 fichiers.

1. client/index.html: structure de la page.
1. client/style.css: styles de l'interface.
1. client/app.js: logique JavaScript (copie du lien ICS).

## Prerequis

1. Docker
1. Docker Compose
1. Un reseau Docker externe nomme npm-network

Creation du reseau si besoin:

```bash
docker network create npm-network
```

## Configuration

Creez un fichier .env a la racine du projet:

```env
EMAIL=votre.email@exemple.com
MDP=votre_mot_de_passe
```

Variables utilisees:

1. EMAIL: identifiant CESI
1. MDP: mot de passe CESI

## Lancer le projet

Depuis la racine:

```bash
docker compose up -d --build
```

Consulter les logs du script:

```bash
docker compose logs -f script-runner
```

Arreter les services:

```bash
docker compose down
```

## Utilisation

1. Ouvrez l'interface web sur [http://localhost:8081](http://localhost:8081).
1. Copiez l'URL ICS affichee.
1. Importez ou abonnez cette URL dans votre calendrier.

URL ICS locale:

```text
http://localhost:8081/api_data/emploisDuTemps.ics
```

## Details techniques

1. Le script conserve un historique limite de fichiers JSON intermediaires.
1. Le nettoyage conserve au maximum 7 fichiers JSON recents cote serveur.
1. Le fichier ICS final est regenere a chaque execution.
1. Certains creneaux sont filtres dans la logique de conversion (voir server/convertissor.py).

## Depannage

1. Le conteneur Python ne demarre pas: verifiez EMAIL et MDP dans .env puis consultez docker compose logs -f script-runner.
1. Le fichier ICS est inaccessible: verifiez l'etat des services avec docker compose ps puis testez [http://localhost:8081/api_data/emploisDuTemps.ics](http://localhost:8081/api_data/emploisDuTemps.ics).
1. Erreur reseau Docker: verifiez que npm-network existe, sinon creez-le avec docker network create npm-network.

## Ameliorations possibles

1. Renforcer la centralisation des logs et la supervision.
1. Ajouter des metadonnees ou couleurs calendrier selon les clients (Apple/Google).
1. Ajouter des tests automatiques pour la chaine scraping vers JSON puis ICS.
1. Ajouter une route de sante pour faciliter le monitoring des conteneurs.
