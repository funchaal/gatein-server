#!/usr/bin/env python3
"""
GateIn Server — Terminal Check-in Socket.IO Simulator (BTP Context)

Simulates a physical terminal hardware unit connecting to the GateIn backend 
via Socket.IO on the `/checkin` namespace.

Features:
- Connects using B2B API Key authentication (`auth={'api_key': ...}`)
- Listens for remote check-in requests (`request_checkin`) for tax ID 43316667865
- Responds with ticket payloads matching BTP Ticket Layout `ref: "3"` (DB verified)
"""

import sys
import time
import argparse
import socketio

# Create Socket.IO synchronous client
sio = socketio.Client(logger=True, engineio_logger=False)

# Target namespace for terminal check-ins
NAMESPACE = '/checkin'

# Configured defaults for BTP and driver 43316667865
DEFAULT_API_KEY = "sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4"
DEFAULT_DRIVER_TAX_ID = "43316667865"

# Database verified layout reference for BTP Ticket Layout ("Agendamento Padrão")
BTP_TICKET_LAYOUT_REF = "3"
BTP_DEFAULT_APPOINTMENT_REF = "BTP-AG-2026-001"


@sio.event(namespace=NAMESPACE)
def connect():
    print(f"\n✅ [SOCKET CONNECTED] Successfully connected to GateIn backend on namespace '{NAMESPACE}'!")
    print("📡 Hardware terminal is active and listening for mobile check-in requests...")


@sio.event(namespace=NAMESPACE)
def connect_error(data):
    print(f"\n❌ [CONNECTION ERROR] Failed to connect to server: {data}")
    print("💡 Please check that server is running (main.py) and the API Key is valid.")


@sio.event(namespace=NAMESPACE)
def disconnect():
    print("\n⚠️ [SOCKET DISCONNECTED] Terminal disconnected from server.")


@sio.on('request_checkin', namespace=NAMESPACE)
def on_request_checkin(data):
    """
    Callback executed when the server triggers a remote checkin request.
    The return value of this handler is sent back as an Acknowledgement (ACK) payload.
    """
    print(f"\n📲 [CHECK-IN REQUEST RECEIVED]")
    print(f"   Payload from Mobile/Server: {data}")
    
    tax_id = data.get('tax_id', DEFAULT_DRIVER_TAX_ID) if isinstance(data, dict) else DEFAULT_DRIVER_TAX_ID
    appointment_ref = data.get('appointment_ref', BTP_DEFAULT_APPOINTMENT_REF) if isinstance(data, dict) else BTP_DEFAULT_APPOINTMENT_REF

    print(f"   Driver Tax ID: {tax_id}")
    print(f"   Target Appointment Ref: {appointment_ref}")
    print("   ⚙️ Processing check-in and validating terminal gate access...")
    
    # Simulate hardware verification delay (1.5 seconds)
    time.sleep(1.5)
    
    ticket_payload = [
        {
            "appointment_ref": appointment_ref,
            "ticket": {
                "layout_ref": BTP_TICKET_LAYOUT_REF,
                "content": {
                    "area_coleta": "Quadra C",
                    "motorista": "Rafael Santos",
                    "placa": "ABC-1234",
                    "placa_carreta": "XYZ-9876",
                    "transportadora": "Logística TransBrasil S/A",
                    "tipo_operacao": "CARREGAMENTO_SOJA",
                    "armador": "Maersk Line",
                    "booking": "BKG-99281726",
                    "previsao_navio": "2026-06-28T07:00:00Z",
                    "gate_pass_token": "PASS-9021-SOJA",
                    "condicao_container": "Lacre intacto. Sem avarias estruturais observadas."
                }
            }
        }
    ]

    print("   ✅ Ticket generated! Returning response to backend...")
    print(f"   Ticket Data: {ticket_payload}\n")

    # Returning list generates the Socket.IO ACK response expected by sio.call
    return ticket_payload


def main():
    parser = argparse.ArgumentParser(description="Simulate a physical terminal checkin over Socket.IO (BTP context)")
    parser.add_argument(
        "--url", 
        default="http://localhost:8000", 
        help="Backend server URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--api-key", 
        default=DEFAULT_API_KEY, 
        help=f"API Key for terminal authentication (default: {DEFAULT_API_KEY})"
    )
    args = parser.parse_args()

    print("=" * 70)
    print(" 🚀 GateIn Terminal Check-in Socket.IO Simulator (BTP)")
    print("=" * 70)
    print(f"Connecting to: {args.url}")
    print(f"Namespace:     {NAMESPACE}")
    print(f"API Key:       {args.api_key[:20]}...")
    print(f"Driver Tax ID: {DEFAULT_DRIVER_TAX_ID}")
    print(f"Ticket Layout: {BTP_TICKET_LAYOUT_REF}")
    print("-" * 70)

    try:
        sio.connect(
            args.url,
            namespaces=[NAMESPACE],
            auth={'api_key': args.api_key}
        )
        sio.wait()
    except KeyboardInterrupt:
        print("\n👋 Stopping terminal simulator...")
        sio.disconnect()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
