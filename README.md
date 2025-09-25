# CN Upload Results

Automatizacion para cargar resultados de CN desde archivos Excel a QBench, iniciando en sandbox y preparando la transicion a produccion.

## Objetivos
- Procesar archivos Excel aplicando reglas de extraccion definidas.
- Buscar y actualizar samples correspondientes en QBench.
- Sincronizar autenticacion y registro con Supabase.
- Mantener una arquitectura escalable, testeable y segura.

## Estructura Inicial
```
CN-upload-results/
  docs/
  src/
    cn_upload_results/
      clients/
      config/
      domain/
      parsers/
      ui/
      workflows/
  tests/
  requirements.txt
  README.md
```

## Requisitos
- Python 3.12+
- Acceso a QBench (sandbox y produccion)
- Proyecto Supabase con auth y tabla `qbench_uploads`

## Puesta en Marcha
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

## Flujo de Trabajo
- CLI con Typer: `python -m cn_upload_results upload <archivo.xlsx>`
- UI en PySide6: `python -m cn_upload_results ui` (requiere Supabase configured).
- Parser de Excel extrae fecha, batch numbers y componentes (CBDVA... CBT).
- Clientes dedicados para QBench (HTTP) y Supabase (auth + logging).
- Tests en `tests/unit` validan las reglas principales del parser.

## Proximos Pasos
1. Mapear endpoints exactos de QBench sandbox y adaptar payloads.
2. Definir esquema de tabla en Supabase y politicas de acceso.
3. Completar interacciones de UI (preview interactivo, manejo de errores, monitoreo).
4. Integrar pipeline CI/CD para ejecutar lint y pytest en cada commit.

