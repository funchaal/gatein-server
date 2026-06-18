from urllib.parse import parse_qs
import socketio
from fastapi import HTTPException

from app.core.database import SessionLocal
from app.models import Terminal
from app.core.dependencies import get_company_from_api_key

# Criação do servidor Socket.IO assíncrono
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

# Criação da aplicação ASGI exclusiva para o WebSocket
socket_app = socketio.ASGIApp(sio)

# Dicionário em memória para manter o controle dos terminais ativos {terminal_id: sid}
active_terminals = {}

@sio.on('connect', namespace='/checkin')
async def connect_checkin(sid, environ, auth):
    print(f"\n[DEBUG WS] Nova tentativa de conexão. SID: {sid}")
    
    api_key = None
    
    # 1. Tenta pegar pelo Auth Payload
    if auth and 'api_key' in auth:
        api_key = auth['api_key']
        
    # 2. Tenta pegar pela URL (Params do Postman/Cliente)
    if not api_key:
        query_string = environ.get('QUERY_STRING', '')
        query_params = parse_qs(query_string)
        if 'api_key' in query_params:
            api_key = query_params['api_key'][0]

    # Se não achou em nenhum lugar
    if not api_key:
        print("[DEBUG WS] RECUSADO: Nenhuma API Key fornecida.")
        raise socketio.exceptions.ConnectionRefusedError('Autenticação requerida (api_key).')
    
    db = SessionLocal()
    try:
        try:
            # Reutiliza a função de segurança
            company = get_company_from_api_key(x_api_key=api_key, db=db)
        except HTTPException as e:
            erro_detail = e.detail.get("code") if isinstance(e.detail, dict) else e.detail
            print(f"[DEBUG WS] RECUSADO pela segurança: {erro_detail}")
            raise socketio.exceptions.ConnectionRefusedError(f'Acesso negado: {erro_detail}')
        
        # OTIMIZAÇÃO/SEGURANÇA: Garante que transportadoras não conectem no check-in
        if company.type != 'terminal':
            print(f"[DEBUG WS] RECUSADO: Empresa {company.id} não é um terminal.")
            raise socketio.exceptions.ConnectionRefusedError('Apenas terminais podem conectar ao check-in.')
        
        terminal_id_str = str(company.id)
        active_terminals[terminal_id_str] = sid
        sio.enter_room(sid, terminal_id_str, namespace='/checkin')
        
        print(f"[DEBUG WS] SUCESSO! Terminal conectado. Terminal ID: {terminal_id_str}")
        
    finally:
        db.close()

@sio.on('disconnect', namespace='/checkin')
async def disconnect_checkin(sid):
    print(f"\n[DEBUG WS] Conexão encerrada/perdida. SID: {sid}")
    
    for terminal_id, saved_sid in list(active_terminals.items()):
        if saved_sid == sid:
            del active_terminals[terminal_id]
            print(f"[DEBUG WS] Limpeza feita! Terminal {terminal_id} removido dos ativos.")
            break