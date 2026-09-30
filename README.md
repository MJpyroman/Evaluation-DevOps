# Evaluation-DevOps

API Flask + Redis conteneurisée, testée, publiée sur `ghcr.io` puis déployée
automatiquement sur une machine cible, avec métriques Prometheus et alertes.

## Lancer le projet en local

Prérequis : Docker et Docker Compose.

```bash
git clone https://github.com/MJpyroman/Evaluation-DevOps.git
cd Evaluation-DevOps
docker compose up -d --build
```

| Service | URL |
|---|---|
| Application | <http://localhost:8080> |
| Métriques | <http://localhost:8080/metrics> |
| Prometheus | <http://localhost:9090> (alertes : `/alerts`) |

```bash
curl localhost:8080/health    # {"redis":"up","status":"ok"}
curl localhost:8080/visits    # {"visits":1}
docker compose down           # ajouter -v pour effacer aussi les données
```

### Tests

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
docker run -d --rm --name redis-tests -p 6379:6379 redis:7.4.11-alpine
pytest
```

Sans Redis joignable, les tests d'intégration sont ignorés en local — mais
ils **échouent** en CI, pour qu'un service déclaré ne puisse pas être ignoré.

## Application

| Endpoint | Rôle |
|---|---|
| `/` | nom du service, version et commit en cours d'exécution |
| `/health` | `200` si Redis répond au `PING`, **`503` sinon** |
| `/visits` | compteur incrémenté dans Redis |
| `/metrics` | métriques au format texte Prometheus |

## Image Docker

- Base épinglée `python:3.12.14-slim-trixie`, build **multi-stage** : les
  dépendances sont installées dans un venv à part, l'image finale ne garde
  que ce venv et le code.
- Utilisateur non-root `app` (uid 10001) ; le code appartient à root, il est
  lisible mais pas modifiable.
- `HEALTHCHECK` sur `/health` : le conteneur passe `unhealthy` si Redis tombe.
- `.dockerignore` en liste blanche : seuls `requirements.txt` et `src/`
  entrent dans le contexte de build, `.git` compris dans l'exclusion.
- gunicorn en un processus de 4 threads : les métriques vivent en mémoire,
  par processus ; plusieurs workers donneraient des compteurs différents à
  chaque scrape.

`docker-compose.yml` lance `app`, `redis` et `prometheus`. L'application
attend que Redis soit `healthy` avant de démarrer.

## CI — `.github/workflows/ci.yml`

Déclenchée sur chaque pull request et chaque push sur `main`.

```
lint ──► test ──► build ──► ci-ok
```

| Job | Contenu |
|---|---|
| `lint` | flake8, yamllint, shellcheck, `promtool check config` et `promtool test rules` |
| `test` | pytest en matrice Python 3.11 / 3.12, avec un service Redis réellement utilisé ; rapports JUnit et couverture publiés en artefacts |
| `build` | build de l'image (cache GitHub Actions), vérification qu'elle ne tourne pas en root |
| `ci-ok` | récupère les rapports (`download-artifact`), les résume, échoue si un job a échoué |

- `ci-ok` est le check exigé par la protection de la branche `main`. Il tourne
  avec `if: always()` : sans cela, il serait *ignoré* quand un job échoue — et
  GitHub compte un check ignoré comme réussi.
- L'action locale `.github/actions/setup-python-deps` (Python, cache pip,
  installation) est partagée par `lint` et `test`. Elle affiche
  `Cache pip : HIT` quand le cache est restauré.
- `permissions: contents: read` en tête, `timeout-minutes` sur chaque job.

## CD — `.github/workflows/cd.yml`

Déclenchée après une CI **verte** sur un **push** vers `main`
(`workflow_run`), ou à la main (`workflow_dispatch`, input
`environment: production`).

1. **`build-and-push`** (`packages: write`) publie trois tags :
   `latest`, le SHA court du commit, et la version semver lue dans `VERSION`.
   Version et commit sont injectés dans l'image, exposés par `/` et
   `app_build_info`.
2. **`deploy`** (`packages: read`) tourne sur un runner **self-hosted**
   installé sur la machine cible et lance `deploy/deploy.sh` :
   pull de l'image, redémarrage, `curl` sur `/health` avec 3 retries. En cas
   d'échec : **rollback** par re-pull de l'image précédente, et le job échoue.

Seul le `GITHUB_TOKEN` est utilisé, aucun secret n'apparaît dans les logs.
La condition `event == 'push'` empêche le code d'une pull request
fork compris, d'atteindre le runner de production.

Publier une nouvelle version : modifier `VERSION`, puis fusionner sur `main`.

## Métriques et alertes

| Métrique | Type | Labels |
|---|---|---|
| `http_requests_total` | Counter | `endpoint`, `code` |
| `http_request_duration_seconds` | Histogram | `endpoint` |
| `app_build_info` | Gauge (toujours 1) | `version`, `commit` |

`endpoint` porte le motif de route (`/visits`) et non l'URL appelée : une URL
inconnue ne crée pas de nouvelle série. `/metrics` ne se compte pas lui-même.

| Alerte | Condition | `for` | Justification |
|---|---|---|---|
| `TauxErreurs5xxEleve` | 5xx / total, fenêtre de 2 min, > **5 %** | **5 min** | au-delà d'une requête sur vingt, l'impact utilisateur est certain |
| `LatenceP95Degradee` | p95 par route, fenêtre de 5 min, > **500 ms** | **10 min** | l'API répond en quelques ms ; une lenteur est moins urgente qu'une panne |

Chaque `for` est plus long que sa fenêtre : un pic isolé sort de la fenêtre
avant d'avoir duré assez longtemps, il ne déclenche rien. 500 ms est une borne
de bucket, donc « p95 > 500 ms » ne dépend pas de l'interpolation.

`prometheus/alerts.test.yml` le prouve avec `promtool test rules` : erreurs
soutenues (alerte), pic de 3 minutes (rien), route lente contre route rapide.

## Runner self-hosted

La machine cible exécute un runner GitHub Actions en service. Pour
l'installer : *Settings → Actions → Runners → New self-hosted runner*, puis
sur la machine :

```bash
mkdir ~/actions-runner && cd ~/actions-runner
curl -o runner.tar.gz -L https://github.com/actions/runner/releases/download/v2.337.0/actions-runner-linux-x64-2.337.0.tar.gz
tar xzf runner.tar.gz
./config.sh --url https://github.com/MJpyroman/Evaluation-DevOps --token <TOKEN> --unattended
sudo ./svc.sh install "$USER" && sudo ./svc.sh start
```

L'utilisateur du runner doit pouvoir lancer `docker` (groupe `docker`).

## Structure

```
.github/
  actions/setup-python-deps/   action locale : Python + cache pip + dépendances
  workflows/ci.yml             lint, test, build, ci-ok
  workflows/cd.yml             build-and-push, deploy
deploy/deploy.sh               déploiement, vérification, rollback
prometheus/                    configuration, alertes et leurs tests
src/                           application (app.py) et métriques (metrics.py)
tests/                         tests unitaires, d'intégration Redis et des métriques
Dockerfile, docker-compose.yml, VERSION
```
