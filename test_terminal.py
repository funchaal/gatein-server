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
            "appointment_ref": "AG-2026-004",
            "ticket": {
                "layout_ref": "2",
                "content": {
                    "status":             "Acesso Liberado",
                    "area_coleta":        "P-4",
                    "numero_container":   "MSCU 741830-2",
                    "motorista":          "Robson Alves Pinto",
                    "placa":              "SP-GH319",
                    "placa_carreta":      "MG-AA9821",
                    "transportadora":     "MSC Logística Brasil",
                    "tipo_operacao":      "Retirada de vazio",
                    "armador":            "Mediterranean Shipping Co.",
                    "booking":            "BKG-7748821",
                    "previsao_navio":     "18/07 — MSC ARIES",
                    "condicao_container": "Container vistoriado. Amassado na parede lateral direita registrado em sistema. Não impede operação.",
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