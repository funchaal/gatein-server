import socketio
from urllib.parse import parse_qs
from fastapi import HTTPException

from app.core.database import SessionLocal
from app.models import Terminal
from app.core.dependencies import get_company_from_api_key

# Thread-safe in-memory mapping to keep track of active terminal connections: {terminal_id_str: sid}
active_terminals = {}

class CheckinNamespace(socketio.AsyncNamespace):
    """
    Class-based Namespace handler for '/checkin'.
    Handles connection, authentication, room allocation, and disconnection cleanups for physical terminals.
    """

    async def on_connect(self, sid, environ, auth):
        """
        Invoked when a physical terminal client attempts to connect to the /checkin namespace.
        Authenticates the client using an API Key provided either in the connection's auth payload 
        or via URL query parameters.
        """
        print(f"\n[DEBUG WS] Nova tentativa de conexão. SID: {sid}")
        
        api_key = None
        
        # 1. Attempt to extract the API Key from the Socket.IO Auth Payload (recommended method)
        if auth and 'api_key' in auth:
            api_key = auth['api_key']
            
        # 2. Fallback: Attempt to extract the API Key from the URL query string (e.g., Postman / simple clients)
        if not api_key:
            query_string = environ.get('QUERY_STRING', '')
            query_params = parse_qs(query_string)
            if 'api_key' in query_params:
                api_key = query_params['api_key'][0]

        if not api_key:
            print("[DEBUG WS] RECUSADO: Nenhuma API Key fornecida.")
            raise socketio.exceptions.ConnectionRefusedError('Autenticação requerida (api_key).')
        
        db = SessionLocal()
        try:
            try:
                # Authenticate and validate the API key using existing dependency logic
                company = get_company_from_api_key(x_api_key=api_key, db=db)
            except HTTPException as e:
                error_detail = e.detail.get("code") if isinstance(e.detail, dict) else e.detail
                print(f"[DEBUG WS] RECUSADO pela segurança: {error_detail}")
                raise socketio.exceptions.ConnectionRefusedError(f'Acesso negado: {error_detail}')
            
            # Security Constraint: Only terminals are allowed to authenticate on this namespace
            if company.type != 'terminal':
                print(f"[DEBUG WS] RECUSADO: Empresa {company.id} não é um terminal.")
                raise socketio.exceptions.ConnectionRefusedError('Apenas terminais podem conectar ao check-in.')
            
            terminal_id_str = str(company.id)
            active_terminals[terminal_id_str] = sid
            
            # Put this terminal's socket session into a dedicated room matching its UUID.
            # This allows the HTTP API to send events/calls targeting a specific terminal room.
            self.enter_room(sid, terminal_id_str)
            
            print(f"[DEBUG WS] SUCESSO! Terminal conectado. Terminal ID: {terminal_id_str}")
            
        finally:
            db.close()

    async def on_disconnect(self, sid):
        """
        Invoked when a physical terminal client disconnects or connection is lost.
        Cleans up the active terminals registry map to avoid stale references.
        """
        print(f"\n[DEBUG WS] Conexão encerrada/perdida. SID: {sid}")
        
        # Search and clean up the active terminals dictionary
        for terminal_id, saved_sid in list(active_terminals.items()):
            if saved_sid == sid:
                active_terminals.pop(terminal_id, None)
                print(f"[DEBUG WS] Limpeza feita! Terminal {terminal_id} removido dos ativos.")
                break
