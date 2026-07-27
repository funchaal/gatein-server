# GateIn Server — Public API (`/api/v1/`) cURL Test Collection (BTP Context)

This file contains copy-paste ready `curl` commands to test **all public routes** registered on the GateIn server (`/api/v1/...`).

All examples are configured for testing with company **BTP (Brasil Terminal Portuário)**, driver user `tax_id: "43316667865"`, API Key `sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4`, using the **exact layout references currently registered in the database**.

---

## 📌 Setup & Credentials

- **Server Base URL**: `http://localhost:8000`
- **Active Company API Key**: `sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4`
- **Driver Tax ID (CPF)**: `43316667865`
- **Postman Import**: You can import these cURL commands directly into Postman by selecting **Import** -> **Raw text** / **cURL**.

---

## 1. 🔑 Authentication & Services

### 1.1 Validate API Key
Validates the provided B2B API Key and returns company details (type, username, name, tax_id).

```bash
curl -X GET "http://localhost:8000/api/v1/validate-api-key" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json"
```

---

### 1.2 Validate User Auth Token (Service Integration)
Validates a mobile driver's JWT token passed via `Auth-Token` header.

```bash
curl -X GET "http://localhost:8000/api/v1/services/validate-user-token" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Auth-Token: YOUR_DRIVER_JWT_TOKEN_HERE" \
  -H "Content-Type: application/json"
```

---

## 2. 📅 Appointments (`/api/v1/appointments`)

Layout Used: **BTP Carga de Contêiner (`ref: "LAYOUT-001"`)**
- Header field: `summary`
- Sub-Header field: `vehicle_plate`
- Body field: `gate_assignment`
- Modal QRCode: `gate_pass_token`

---

### 2.1 Create Single Appointment
Registers a new appointment linked to driver `tax_id: "43316667865"`.

```bash
curl -X POST "http://localhost:8000/api/v1/appointments" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json" \
  -d '{
    "driver": {
      "tax_id": "43316667865",
      "driver_license_number": "12345678900",
      "license_category": "E"
    },
    "appointment": {
      "ref": "BTP-AG-2026-001",
      "layout_ref": "LAYOUT-001",
      "window_start": "2026-07-25T14:00:00Z",
      "window_end": "2026-07-25T22:00:00Z",
      "start_tolerance": 30,
      "end_tolerance": 30,
      "summary": "Carga de Contêiner BTP",
      "license_plate": "XYZ-9876",
      "custom_data": {
        "vehicle_plate": "XYZ-9876",
        "nome_motorista": "Rafael Santos",
        "cnh_motorista": "12345678900",
        "gate_assignment": "Portão B - Pista 3",
        "gate_pass_token": "BTP-2026-001-5502",
        "nota_fiscal": "987654",
        "transportadora": "TransLog Logística"
      }
    }
  }'
```

---

### 2.2 Create Batch Appointments
Registers multiple appointments in a single request.

```bash
curl -X POST "http://localhost:8000/api/v1/appointments" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "driver": {
        "tax_id": "43316667865",
        "driver_license_number": "12345678900",
        "license_category": "E"
      },
      "appointment": {
        "ref": "BTP-AG-2026-002",
        "layout_ref": "LAYOUT-001",
        "window_start": "2026-07-25T15:00:00Z",
        "window_end": "2026-07-25T21:00:00Z",
        "start_tolerance": 15,
        "end_tolerance": 15,
        "summary": "Carga de Contêiner Lote 1",
        "license_plate": "ABC-1234",
        "custom_data": {
          "vehicle_plate": "ABC-1234",
          "nome_motorista": "Rafael Santos",
          "gate_assignment": "Portão A - Pista 1",
          "gate_pass_token": "BTP-2026-002-9901"
        }
      }
    },
    {
      "driver": {
        "tax_id": "43316667865",
        "driver_license_number": "12345678900",
        "license_category": "E"
      },
      "appointment": {
        "ref": "BTP-AG-2026-003",
        "layout_ref": "LAYOUT-001",
        "window_start": "2026-07-25T17:00:00Z",
        "window_end": "2026-07-25T23:00:00Z",
        "start_tolerance": 20,
        "end_tolerance": 20,
        "summary": "Carga de Contêiner Lote 2",
        "license_plate": "KLU-5544",
        "custom_data": {
          "vehicle_plate": "KLU-5544",
          "nome_motorista": "Rafael Santos",
          "gate_assignment": "Portão C - Pista 2",
          "gate_pass_token": "BTP-2026-003-7712"
        }
      }
    }
  ]'
```

---

### 2.3 Update Appointment
Partially updates metadata, schedules, or custom data of an existing appointment.

```bash
curl -X PUT "http://localhost:8000/api/v1/appointments" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json" \
  -d '{
    "ref": "BTP-AG-2026-001",
    "appointment": {
      "summary": "Carga de Contêiner Reagendada",
      "window_start": "2026-07-25T15:00:00Z",
      "window_end": "2026-07-25T21:00:00Z",
      "custom_data": {
        "vehicle_plate": "XYZ-9876",
        "nome_motorista": "Rafael Santos",
        "gate_assignment": "Portão B - Pista 4",
        "gate_pass_token": "BTP-2026-001-5502"
      }
    }
  }'
```

---

### 2.4 Query Appointment Logs & Details
Retrieves detailed appointment data, driver profile, and execution log traces.

```bash
curl -X GET "http://localhost:8000/api/v1/appointments/logs?refs=BTP-AG-2026-001&refs=BTP-AG-2026-002" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json"
```

---

### 2.5 Ping Appointments (Terminal Heartbeat)
Renews the 2-hour activity window for an appointment to prevent timeout.

```bash
curl -X POST "http://localhost:8000/api/v1/appointments/ping" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json" \
  -d '{
    "appointment_refs": ["BTP-AG-2026-001"]
  }'
```

---

### 2.6 Delete / Cancel Appointment
Cancels appointment(s) and logs deletion status.

```bash
curl -X DELETE "http://localhost:8000/api/v1/appointments" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json" \
  -d '["BTP-AG-2026-001"]'
```

---

## 3. 🎟️ Digital Tickets (`/api/v1/tickets`)

Layout Used: **BTP Agendamento Padrão (`ref: "3"`)**
- Highlight: `area_coleta`
- Operation Section: `motorista`, `placa`, `transportadora`
- Condition Attention: `condicao_container`

---

### 3.1 Create Ticket
Creates a digital ticket linked to an existing appointment reference.

```bash
curl -X POST "http://localhost:8000/api/v1/tickets" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json" \
  -d '{
    "appointment_ref": "BTP-AG-2026-001",
    "layout_ref": "3",
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
  }'
```

---

### 3.2 Query Tickets by Appointment Reference
Fetches all tickets registered for the given appointment reference(s).

```bash
curl -X GET "http://localhost:8000/api/v1/tickets?appointment_refs=BTP-AG-2026-001" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json"
```

---

### 3.3 Update Ticket
Updates content or layout reference of an existing ticket by its UUID.

```bash
curl -X PUT "http://localhost:8000/api/v1/tickets" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "REPLACE_WITH_TICKET_UUID",
    "layout_ref": "3",
    "content": {
      "area_coleta": "Quadra D",
      "motorista": "Rafael Santos",
      "placa": "ABC-1234",
      "placa_carreta": "XYZ-9876",
      "transportadora": "Logística TransBrasil S/A",
      "tipo_operacao": "CARREGAMENTO_CONTAINER",
      "armador": "Maersk Line",
      "booking": "BKG-99281726",
      "previsao_navio": "2026-06-28T07:00:00Z",
      "gate_pass_token": "PASS-9021-SOJA",
      "condicao_container": "Lacre verificado pela equipe de pátio."
    }
  }'
```

---

### 3.4 Delete Ticket
Deletes ticket(s) by UUID.

```bash
curl -X DELETE "http://localhost:8000/api/v1/tickets" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json" \
  -d '["REPLACE_WITH_TICKET_UUID"]'
```

---

## 4. 🚛 Freight Trips (`/api/v1/trips`)

Layout Used: **Standard Trip (`ref: "standard_trip"`)**

---

### 4.1 Create Single Trip
Registers a freight trip with origin/destiny location data and driver profile `tax_id: "43316667865"`.

```bash
curl -X POST "http://localhost:8000/api/v1/trips" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json" \
  -d '{
    "driver": {
      "tax_id": "43316667865",
      "driver_license_number": "12345678900",
      "license_category": "E"
    },
    "trip": {
      "ref": "BTP-TRIP-2026-001",
      "layout_ref": "standard_trip",
      "license_plate": "XYZ-9876",
      "summary": "Transporte de Carga BTP Santos -> Campinas",
      "window_start": "2026-07-25T08:00:00Z",
      "window_end": "2026-07-25T22:00:00Z",
      "start_tolerance": 60,
      "end_tolerance": 60,
      "from_location": "BTP - Brasil Terminal Portuário",
      "to_location": "Depósito Central - Campinas",
      "origin_street": "Av. Eduardo Guinle",
      "origin_number": "S/N",
      "origin_city": "Santos",
      "origin_state": "SP",
      "origin_country": "Brasil",
      "origin_zip": "11095-000",
      "origin_lat": -23.924156643454374,
      "origin_lng": -46.34930933223951,
      "destiny_street": "Av. Eng. Fábio Roberto Barnabé",
      "destiny_number": "1500",
      "destiny_city": "Campinas",
      "destiny_state": "SP",
      "destiny_country": "Brasil",
      "destiny_zip": "13000-000",
      "destiny_lat": -22.90556,
      "destiny_lng": -47.06083,
      "custom_data": {
        "cargo_type": "Carga Geral",
        "origin_city": "Santos - SP",
        "destination_city": "Campinas - SP",
        "cargo_weight": "25.0 tons",
        "customer_name": "Cliente Exemplo S/A",
        "carrier_notes": "Atenção nas curvas e limite de velocidade."
      }
    }
  }'
```

---

### 4.2 Update Trip
Updates trip parameters or execution status.

```bash
curl -X PUT "http://localhost:8000/api/v1/trips" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json" \
  -d '{
    "ref": "BTP-TRIP-2026-001",
    "trip": {
      "summary": "Em trânsito - Santos para Campinas",
      "status": "IN_PROGRESS"
    }
  }'
```

---

### 4.3 Query Trip Logs & Audit Details

```bash
curl -X GET "http://localhost:8000/api/v1/trips/logs?refs=BTP-TRIP-2026-001" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json"
```

---

### 4.4 Delete / Cancel Trip

```bash
curl -X DELETE "http://localhost:8000/api/v1/trips" \
  -H "X-API-Key: sk_live_8852fa2f02_6dAnCOPnylOMXwi-i0fQg5TO6G-7AlMGbOBA7jnyVk4" \
  -H "Content-Type: application/json" \
  -d '["BTP-TRIP-2026-001"]'
```

---

## 📋 Database Verified Layout References (BTP)

| Entity | DB Layout Ref | Layout Title | Schema Target | Key Fields |
| :--- | :--- | :--- | :--- | :--- |
| **Appointment** | `"LAYOUT-001"` | Carga de Contêiner | `custom_data` | `vehicle_plate`, `gate_assignment`, `gate_pass_token`, `nome_motorista` |
| **Ticket** | `"3"` | Agendamento Padrão | `content` | `area_coleta`, `motorista`, `placa`, `transportadora`, `condicao_container` |
| **Trip** | `"standard_trip"` | Layout Padrao de Viagem | `custom_data` | `origin_city`, `destination_city`, `cargo_type`, `cargo_weight`, `carrier_notes` |
