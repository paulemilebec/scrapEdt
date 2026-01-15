# Scrap edt

-----

## 1️⃣ Requête 1 : Initialisation (WAYF GET)

Le but de cette requête est de déclencher le processus d'authentification et d'arriver sur la page de connexion de l'IdP (ADFS).

| Caractéristique | Contenu | Rôle |
| :--- | :--- | :--- |
| **Type** | **GET** | On demande au serveur de nous envoyer la page d'accueil de la connexion. |
| **URL Cible** | Le service **WAYF** (ex: `https://wayf.cesi.fr/login?...`). Votre email y est souvent inclus en paramètre (`UserName`). | Le serveur WAYF reçoit l'email et redirige le navigateur vers le bon Fournisseur d'Identité (ADFS). |
| **Données** | Aucune (sauf les paramètres dans l'URL). | |
| **Résultat** | La réponse contient le code HTML d'une page ADFS qui, dans votre cas, est souvent un **formulaire SAML initial** qui s'auto-soumet immédiatement. |

### Note sur l'auto-soumission

Dans votre code, la réponse `r1` contient un petit formulaire SAML qui doit être soumis immédiatement (Requête 2a) pour arriver à la vraie page de login ADFS (Requête 2b). Cette étape est une transition standard dans les fédérations.

-----

## 2️⃣ Requête 2 : Authentification (ADFS POST)

Cette requête simule l'action d'entrer le mot de passe et de cliquer sur "Se connecter". C'est là que l'IdP (ADFS) vérifie votre identité.

| Caractéristique | Contenu | Rôle |
| :--- | :--- | :--- |
| **Type** | **POST** | On envoie des données sensibles au serveur pour authentification. |
| **URL Cible** | L'**`action`** du formulaire ADFS (ex: `https://sts.viacesi.fr/adfs/ls/...`). | C'est le point de terminaison qui traite les identifiants. |
| **Données (`data`)** | **Crucial :** Un dictionnaire contenant :<br>\* `UserName` (votre email)<br>\* `Password` (votre mot de passe)<br>\* **Tous les champs cachés** (`AuthMethod`, `client-request-id`, etc.) extraits du formulaire ADFS. | Le serveur a besoin de tous ces jetons et identifiants pour valider la session et prévenir les attaques CSRF. |
| **Résultat** | Si l'authentification réussit, la réponse `r3` contient le **Formulaire de Réponse SAML** caché (le jeton de sécurité). |

-----

## 3️⃣ Requête 3 : Fédération (SAML POST)

Cette requête est la dernière étape de la chaîne de confiance. Elle transmet la preuve de votre identité (le jeton) au Service Provider (Moodle/ENT).

| Caractéristique | Contenu | Rôle |
| :--- | :--- | :--- |
| **Type** | **POST** | On soumet le jeton de sécurité. |
| **URL Cible** | L'**`action`** du formulaire SAML (ex: `https://wayf.cesi.fr/login?...` ou directement l'URL Moodle/ENT). | C'est le point de terminaison du Service Provider qui reçoit la preuve d'identité. |
| **Données (`data`)** | Un dictionnaire contenant :<br>\* **`SAMLResponse`** : Le jeton d'identité encodé, prouvant que vous avez été authentifié par l'IdP.<br>\* **`RelayState`** (si présent) : Information de contexte. | Le SP utilise le `SAMLResponse` pour vérifier l'identité de l'utilisateur et lui créer une session de connexion. |
| **Résultat** | La réponse **`r4`** est la page finale de la ressource demandée (ex: la page d'accueil de l'ENT), avec les **cookies de session** désormais actifs. |

### Le rôle de la Session

Il est fondamental que toutes ces requêtes soient faites en utilisant la **même instance de `requests.Session()`**. Cette session est responsable de la conservation et de l'échange automatique des **cookies** qui lient ces trois étapes ensemble, garantissant que le serveur reconnaisse que chaque requête fait partie du même flux d'authentification.