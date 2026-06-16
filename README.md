# QData - Sistema de Análisis de Calidad de Datos

Plataforma completa para analizar, validar y monitorear la calidad de datos desde múltiples fuentes (PostgreSQL, MySQL, SQL Server, SQLite, CSV, Excel, JSON, Parquet).

## 🚀 Inicio Rápido

```bash
# Clonar e iniciar
docker compose up -d

# Abrir frontend
open http://localhost:5173

# O ejecutar análisis desde CLI
docker compose exec backend qdata analyze --file datos.csv
```

## 📋 Características

| Característica | Descripción |
|---|---|
| **🔍 10+ reglas de validación** | Nulos, duplicados, tipos, outliers, patrones, unicidad, cardinalidad, distribuciones, correlaciones |
| **🗄️ Conectores múltiples** | PostgreSQL, MySQL, SQL Server, SQLite, CSV, Excel, JSON, Parquet |
| **📊 Dashboard glassmorphism** | UI moderna con React + Tailwind + shadcn/ui |
| **⏰ Scheduler programado** | Tareas cron con APScheduler + notificaciones email |
| **🧪 Datos sintéticos** | Genera datos de prueba con perfiles (ventas, RH, finanzas, salud) |
| **💡 Recomendaciones IA** | Sugerencias automáticas de limpieza para cada regla |
| **🔐 Autenticación JWT** | Usuarios con roles (admin, analyst, viewer) |
| **🐳 Dockerizado** | docker-compose listo para dev y producción |
| **🎨 Glassmorphism** | Diseño moderno con efecto vidrio, dark/light mode |

## 🏗️ Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 async |
| Base de datos | PostgreSQL 16 + asyncpg |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4 |
| UI | shadcn/ui, framer-motion, Recharts |
| Scheduler | APScheduler |
| Email | aiosmtplib + Jinja2 |
| Infra | Docker Compose, Nginx |

## 📦 Estructura

```
qdata/
├── backend/          # API FastAPI + motor de reglas
│   ├── qdata/
│   │   ├── core/     # Engine, Profiler, Score, Reporter
│   │   ├── rules/    # 10 reglas de validación
│   │   ├── connectors/ # 9 conectores de datos
│   │   ├── scheduler/ # APScheduler + notificador email
│   │   ├── synthetic/ # Generador de datos sintéticos
│   │   ├── auth/     # JWT + autenticación
│   │   ├── web/      # FastAPI routes
│   │   └── cli/      # Typer CLI
│   └── Dockerfile
├── frontend/         # SPA React
│   ├── src/
│   │   ├── pages/    # 10 páginas
│   │   ├── components/ # Layout, charts, data
│   │   └── ...
│   └── Dockerfile
├── docker-compose.yml
└── docker-compose.prod.yml
```

## 🖥️ CLI

```bash
# Análisis desde base de datos
qdata analyze --db "postgresql://user:pass@host:5432/db" --rules all --output reporte.html

# Análisis desde archivo
qdata analyze --file ventas.csv --source csv

# Generar datos sintéticos
qdata synthetic --profile ventas --rows 10000 --null-rate 0.05 --output test.csv

# Programar análisis diario
qdata scheduler create --name "Diario" --db "postgresql://..." --cron "0 8 * * *" --email ana@empresa.com
```

## 🔧 Desarrollo

```bash
# Iniciar stack completo con hot reload
docker compose up -d

# Ejecutar migraciones
docker compose exec backend alembic upgrade head

# Ejecutar tests
docker compose exec backend pytest --cov

# Ver emails capturados (Mailpit)
open http://localhost:8025
```

## 📄 Licencia

MIT
