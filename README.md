Todo :
    Gestion des logs
    Garder les anciens cours
    Mettre des couleurs avec X-APPLE-CALENDAR-COLOR ou X-GOOGLE-CALENDAR-COLOR
    Mettre les addresses mails des profs

Fix:
    Gestion du cache : Côté Serveur (Important) : Comme ton site est sur OVH, si tu utilises un script PHP ou Python pour servir le fichier, assure-toi d'ajouter ces headers dans ta réponse HTTP :

    Cache-Control: no-cache, no-store, must-revalidate
    Pragma: no-cache
    Expires: 0

docker stop scrapedt-server
docker rm scrapedt-server
docker build -t scrapedt-script-runner .
docker run -d --name scrapedt-server scrapedt-script-runner


git fetch --all
git reset --hard origin/main
docker compose up -d --build