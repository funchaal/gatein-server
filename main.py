# main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.openapi.utils import get_openapi
import socketio

# Importação de Sockets
from app.api.sockets.connection import sio

# Importação de Roteadores Unificados
from app.api.mobile import router as mobile_router
from app.api.web import router as web_router
from app.api.public import router as public_router
from app.api.admin import router as admin_router

# Inicialização do FastAPI com documentação padrão desativada
fastapi_app = FastAPI(
    title="GateIn API", 
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# Middleware CORS (Configurado apenas uma vez)
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusão de Rotas Unificadas
fastapi_app.include_router(mobile_router)
fastapi_app.include_router(web_router)
fastapi_app.include_router(public_router)
fastapi_app.include_router(admin_router)

def load_doc_file(filename: str) -> str:
    import os
    docs_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gatein-docs", "docs"))
    file_path = None
    for root, dirs, files in os.walk(docs_dir):
        if filename in files:
            file_path = os.path.join(root, filename)
            break
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Strip Docusaurus Front Matter if present
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        content = parts[2].strip()
                return content
        except Exception as e:
            print(f"Error reading doc file {file_path}: {e}")
    return ""

def load_external_api_docs() -> str:
    return load_doc_file("1_introduction.md") or "Documentação oficial da API de Integração Externa do GateIn."

# Rota para o OpenAPI customizado contendo apenas a API
@fastapi_app.get("/api/v1/openapi.json", include_in_schema=False)
def get_external_openapi():
    # 1. Recupera o OpenAPI completo gerado pelo FastAPI (com todas as rotas e esquemas)
    openapi_schema = fastapi_app.openapi()
    
    # 2. Filtra as rotas para expor publicamente apenas os endpoints da API
    external_paths = {}
    for path, path_item in openapi_schema.get("paths", {}).items():
        if (path.startswith("/api/v1") and path != "/api/v1/openapi.json") or path.startswith("/api/mobile/checkin"):
            external_paths[path] = path_item
            
    # 3. Retorna a documentação filtrada com tags detalhadas e descrição rica
    api_keys_content = load_doc_file("2_api_keys.md")
    appointments_content = load_doc_file("4_appointments.md")
    trips_content = load_doc_file("5_trips.md")
    services_auth_content = load_doc_file("10_custom_services.md")
    checkin_content = load_doc_file("7_checkin.md")
    tickets_content = load_doc_file("11_tickets.md")

    auth_description = api_keys_content or "Endpoints de autenticação e validação de tokens JWT / chaves de API."

    tags_metadata = [
        {
            "name": "Authentication",
            "description": auth_description
        },
        {
            "name": "Appointments",
            "description": appointments_content or "Endpoints para gestão de agendamentos (Appointments) de veículos/motoristas em lote."
        },
        {
            "name": "Trips",
            "description": trips_content or "Endpoints para controle e sincronização de viagens (Trips) e rotas em lote."
        },
        {
            "name": "Services",
            "description": services_auth_content or "Endpoints para autenticação de usuários em serviços externos de empresas parceiras via handshake JWT."
        },
        {
            "name": "Websocket & Checkin",
            "description": checkin_content or "Explicação do fluxo de check-in remoto via WebSockets (Socket.IO) integrado aos servidores de terminal."
        },
        {
            "name": "Tickets",
            "description": tickets_content or "Endpoints para criação, atualização e remoção de tickets digitais vinculados a agendamentos."
        }
    ]
    
    # 4. Remove a segurança global e componentes de segurança para evitar o box de autenticação vazio
    clean_schema = {**openapi_schema}
    if "components" in clean_schema:
        components = {**clean_schema["components"]}
        if "securitySchemes" in components:
            del components["securitySchemes"]
        clean_schema["components"] = components
    if "security" in clean_schema:
        del clean_schema["security"]
    
    return {
        **clean_schema,
        "info": {
            "title": "GateIn External API",
            "version": "1.0.0",
            "description": load_external_api_docs()
        },
        "paths": external_paths,
        "tags": tags_metadata
    }

# Rota para a documentação Scalar (Padrão)
@fastapi_app.get("/redoc", response_class=HTMLResponse, include_in_schema=False)
def custom_scalar():
    import json
    import os
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scalar.config.json")
    config_data = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception as e:
            print(f"Error loading scalar.config.json: {e}")
    scalar_config_js = json.dumps(config_data)

    return HTMLResponse(f"""
    <!doctype html>
    <html>
      <head>
        <title>GateIn External API Documentation</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
          body {{
            margin: 0;
            padding: 0;
          }}
        </style>
      </head>
      <body>
        <div id="scalar-app"></div>
        <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
        <script>
          const scalarConfig = {scalar_config_js};
          Scalar.createApiReference(document.getElementById('scalar-app'), {{
            url: '/api/v1/openapi.json',
            showSidebar: true,
            hideModels: true,
            ...scalarConfig
          }})
        </script>
      </body>
    </html>
    """)

# Inicialização do Socket.IO ASGI App
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app)

if __name__ == "__main__":
    import uvicorn
    # Ele vai rodar o "app" que agora contém tanto o Socket.IO quanto o FastAPI
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
