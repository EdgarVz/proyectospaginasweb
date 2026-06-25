# LeadFinder — Sistema de Prospección y Análisis de Sitios Web

**Fecha:** 2026-06-25

## 1. Objetivo

Herramienta personal para encontrar negocios en Venezuela/Uruguay con sitios web que necesitan mejoras, analizar automáticamente la calidad de esos sitios, y gestionar leads de prospección desde un dashboard local.

## 2. Arquitectura General

```
┌────────────────────────────────────────────────────────────┐
│                     Tu PC (local)                           │
│                                                             │
│  ┌─────────────────┐   ┌──────────────────┐               │
│  │   Scraper        │   │   Analyzer       │               │
│  │   (Google Places │──▶│  Lighthouse CLI  │               │
│  │    API + httpx)  │   │  + BeautifulSoup │               │
│  └────────┬────────┘   └────────┬─────────┘               │
│           │                     │                          │
│           ▼                     ▼                          │
│  ┌──────────────────────────────────────────────────────┐ │
│  │                  SQLite Database                      │ │
│  │  campaigns | businesses | audits | audit_metrics     │ │
│  └──────────────────────────┬───────────────────────────┘ │
│                             │                              │
│                             ▼                              │
│  ┌──────────────────────────────────────────────────────┐ │
│  │          Dashboard Web (FastAPI + HTMX)               │ │
│  │  / → resumen | /leads → tabla | /campaigns → crear   │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

### Stack tecnológico

| Capa        | Tecnología                                               |
|-------------|----------------------------------------------------------|
| Backend     | Python 3.12+, FastAPI, uvicorn                           |
| Frontend    | HTML + HTMX (CDN) + Alpine.js (CDN) + Tailwind CSS      |
| Base datos  | SQLite (vía aiosqlite para async)                        |
| Scraping    | googlemaps (wrapper Places API), httpx                   |
| Análisis    | Lighthouse CLI (npm -g lighthouse), beautifulsoup4       |
| Background  | FastAPI BackgroundTasks                                  |

**Dependencias externas:** Node.js + Lighthouse CLI (`npm install -g lighthouse`), Google Places API Key.

## 3. Modelo de Datos

```sql
CREATE TABLE campaigns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    keyword     TEXT NOT NULL,
    location    TEXT NOT NULL,
    country     TEXT NOT NULL DEFAULT 'Venezuela',
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE businesses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    name        TEXT NOT NULL,
    website     TEXT NOT NULL,
    phone       TEXT,
    address     TEXT,
    rating      REAL,
    category    TEXT,
    city        TEXT,
    country     TEXT,
    place_id    TEXT UNIQUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id     INTEGER NOT NULL UNIQUE REFERENCES businesses(id),
    status          TEXT NOT NULL DEFAULT 'pending',
    lighthouse_json TEXT,
    error_message   TEXT,
    analyzed_at     TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE audit_metrics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_id    INTEGER NOT NULL REFERENCES audits(id),
    metric_name TEXT NOT NULL,
    score       REAL NOT NULL,
    details     TEXT,
    UNIQUE(audit_id, metric_name)
);
```

### Scores calculados (audit_metrics)

| metric_name              | Rango  | Fuente                     |
|--------------------------|--------|----------------------------|
| performance_score        | 0-100  | Lighthouse                  |
| accessibility_score      | 0-100  | Lighthouse                  |
| seo_score                | 0-100  | Lighthouse                  |
| best_practices_score     | 0-100  | Lighthouse                  |
| mobile_friendly          | 0/1    | Detección de viewport tag  |
| has_meta_description     | 0/1    | BeautifulSoup              |
| has_open_graph           | 0/1    | BeautifulSoup              |
| has_ssl                  | 0/1    | Verificación HTTPS         |
| technologies             | texto  | Detección (WordPress, Wix) |
| lead_score               | 0-100  | Fórmula compuesta           |

**Fórmula lead_score:** `(100 - performance_score) * 0.35 + (100 - seo_score) * 0.25 + (1 - mobile_friendly) * 25 + (100 - best_practices_score) * 0.15`

A mayor lead_score, más necesita mejorar el sitio.

## 4. Pipeline de Scraping

### Comando de entrada
```bash
python -m leadfinder run --campaign "Restaurantes Caracas" --keyword "restaurantes" --location "Caracas,Venezuela" --radius 5000
```

### Flujo del Scraper
1. Inicializa cliente de Google Places API
2. Busca `keyword` en `location` con `radius` paginando resultados
3. Para cada resultado, si tiene `website` → guarda en `businesses`
4. Crea un `audit` con status `pending` para cada negocio
5. Retorna resumen

### Configuración
- Archivo `.env` para `GOOGLE_PLACES_API_KEY`
- Rate limit: 5 requests/seg
- Filtro opcional por rating mínimo

## 5. Pipeline de Análisis

Por cada negocio con audit pendiente:
1. Marcar audit como `running`
2. Ejecutar en paralelo:
   - **Lighthouse:** `lighthouse <url> --chrome-flags="--headless" --output=json --quiet`
   - **HTML Inspector:** httpx GET → BeautifulSoup → meta tags, tecnologías, HTTPS
3. Calcular lead_score
4. Guardar metrics y marcar `done`
5. Error → status `error`

Timeout: 30s por URL.

## 6. Dashboard Web

### Rutas

| Ruta                     | Método | Descripción                          |
|--------------------------|--------|--------------------------------------|
| `/`                      | GET    | Dashboard: cards de resumen          |
| `/leads`                 | GET    | Tabla filtrable con leads + scores   |
| `/leads/{id}`            | GET    | Detalle de lead                      |
| `/leads/export`          | GET    | Descargar CSV                        |
| `/leads/bulk-delete`     | POST   | Eliminar leads seleccionados         |
| `/campaigns`             | GET    | Lista de campañas                    |
| `/campaigns/new`         | POST   | Crear campaña + disparar scraping    |
| `/campaigns/{id}`        | GET    | Detalle de campaña                   |
| `/campaigns/{id}/analyze`| POST   | Disparar análisis manual             |

### UX
- Sidebar con secciones (Dashboard, Leads, Campañas)
- HTMX para filtros sin recargar página
- Alpine.js para modal de detalle y selección múltiple
- Colores: Rojo (<40), Amarillo (40-70), Verde (>70)
- Orden por defecto: lead_score descendente

## 7. Módulos del Proyecto

```
leadfinder/
├── __init__.py
├── __main__.py          # python -m leadfinder run ...
├── config.py            # Cargar .env
├── database.py          # Conexión SQLite, migraciones
├── models.py            # Pydantic models
├── scraper.py           # Google Places API
├── analyzer.py          # Lighthouse + HTML inspector
├── lead_score.py        # Fórmula de scoring
├── web/
│   ├── __init__.py
│   ├── app.py           # FastAPI + rutas
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── leads.html
│   │   ├── lead_detail.html
│   │   ├── campaigns.html
│   │   └── campaign_detail.html
│   └── static/
└── requirements.txt
```

## 8. Consideraciones

### Google Places API
- API Key con Places API habilitada en Google Cloud
- Cuota gratuita: ~$200/mes en créditos (~100k requests)
- Alternativa ética y legal a scrapear Google Maps

### Lighthouse
- Dependencia: Node.js + `npm install -g lighthouse`
- Se corre como subprocess desde Python

### Legal
- Places API es el canal oficial → cumple TOS
- Uruguay: solo datos comerciales públicos
