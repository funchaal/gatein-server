import socketio
import time

# Cliente Socket.IO puro (finge ser o equipamento físico)
sio = socketio.Client()

@sio.event(namespace='/checkin')
def connect():
    print("[TERMINAL] Conectado com sucesso ao servidor!")

@sio.on('request_checkin', namespace='/checkin')
def on_request_checkin(data):
    print(f"\n[TERMINAL] Recebi um pedido do celular! Dados: {data}")
    print("[TERMINAL] Processando e devolvendo o ticket...")
    
    time.sleep(5)
    
    # O 'return' dentro deste evento é a mágica. 
    # Ele gera o Ack automático que o 'sio.call' do servidor está esperando!
    return [
        {
            "appointment_ref": "AG-2026-002",
            "ticket": {
                "layout_ref": "3",
                "content": {
                    "placa": "ABC-1234",
                    "status": "CHECKED_IN",
                    "armador": "Maersk Line",
                    "booking": "BKG-99281726",
                    "motorista": "Carlos de Oliveira Souza",
                    "created_at": "2026-06-25T14:30:00Z",
                    "area_coleta": "Quadra C",
                    "placa_carreta": "XYZ-9876",
                    "tipo_operacao": "CARREGAMENTO_SOJA",
                    "previsao_navio": "2026-06-28T07:00:00Z",
                    "transportadora": "Logística TransBrasil S/A",
                    "gate_pass_token": "PASS-9021-SOJA",
                    "condicao_container": "Lacre intacto. Sem avarias estruturais observadas."
                },
    }
        }
    ]

@sio.event(namespace='/checkin')
def disconnect():
    print("[TERMINAL] Desconectado.")

if __name__ == '__main__':
    print("Ligando o equipamento simulado...")
    
    # Conecta passando a chave de segurança no 'auth'
    sio.connect(
        'http://127.0.0.1:8000',
        namespaces=['/checkin'],
        auth={'api_key': 'sk_live_f7d34f213a_ajd7fLnMllb6jH4wekplTNLcURa6B6-l29OASx9N_bk'} # <-- Ponha sua chave aqui
    )
    
    # Mantém o script rodando infinitamente aguardando eventos
    sio.wait()