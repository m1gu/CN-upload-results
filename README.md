# CN Upload Results

Aplicación de escritorio (PySide6) para parsear hojas de resultados CN, publicar datos en QBench y respaldarlos en Supabase.

## Características principales
- **Autenticación Supabase**: inicio de sesión con email/contraseña; el usuario autenticado se registra como `created_by` en Supabase.
- **Parser de Excel**: extrae metadatos (fecha de corrida, lotes, mapeo batch→samples) y cuantificaciones.
- **Workflow QBench**: actualiza worksheets de los tests CN/HO mediante API autenticada.
- **Persistencia Supabase**: inserta un registro JSON por corrida en la tabla `cn_upload_results` (metadatos, samples, payloads QBench).
- **UI fluida**:
  - Preview previo a publicar.
  - Overlay semitransparente con spinner y mensajes dinámicos.
  - Procesamiento en segundo plano (QThread) para mantener animaciones activas.
- **Pruebas unitarias**: cobertura para parser, workflow y nueva capa de persistencia/publicación (`python -m pytest`).

## Requisitos
- Python 3.12+
- Dependencias en `requirements.txt` (PySide6, pandas, supabase-py, etc.).
- Variables .env para QBench (`QBENCH_*`) y Supabase (`SUPABASE_*`).
- Acceso a proyecto Supabase con tabla `cn_upload_results` (RLS con usuarios autenticados).

## Instalación
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

## Ejecución de la UI
```powershell
python -m cn_upload_results
```
Flujo:
1. Iniciar sesión (Supabase).
2. Seleccionar Excel → vista preliminar.
3. Pulsar “Procesar” → overlay muestra estados mientras se publica en QBench y se guarda en Supabase.
4. Mensaje final con número de samples sincronizados.

## Ejecución de pruebas
```powershell
python -m pytest
```
*Nota:* `test_publish_worker` se omite si PySide6 no está instalado en el entorno de pruebas.

## Estructura relevante
```
src/cn_upload_results/
  clients/         # QBench & Supabase wrappers
  config/          # Settings (Pydantic)
  domain/          # Modelos (RunMetadata, SampleQuantification,…)
  parsers/         # Lectura Excel
  services/        # Persistencia Supabase
  ui/              # PySide6 (login, overlay, worker, main window)
  workflows/       # Lógica para QBench
tests/unit/        # pytest
```

## Tabla Supabase (ejemplo)
`cn_upload_results` con columnas:
- `run_id uuid PK default gen_random_uuid()`
- `run_date date`, `instrument text`, `file_name text`, `workbook_hash text`
- `batch_codes text[]`, `sample_ids text[]`, `created_by text`, `created_at timestamptz`
- `excel_payload jsonb`, `qbench_payload jsonb`, `notes text`

Incluye RLS “authenticated access” para lectura/escritura de usuarios logueados.

