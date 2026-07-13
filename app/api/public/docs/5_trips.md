# Gestão de Viagens (Trips)

O módulo de viagens foi projetado para **Transportadoras, Embarcadores e Operadores de Frota** registrarem e rastrearem a locomoção de cargas entre pontos de coleta (origem) e entrega (destino). As requisições são processadas em lote (batch) para alta performance.

---

## Schemas

### Driver

> [!NOTE]
> Os campos marcados com `*` são obrigatórios.

<table>
  <thead>
    <tr>
      <th width="40%" align="left">Campo</th>
      <th width="20%" align="left">Tipo</th>
      <th width="40%" align="left">Descrição</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>*tax_id</code></td>
      <td><code>string</code></td>
      <td>CPF ou CNPJ do motorista (apenas números)</td>
    </tr>
    <tr>
      <td><code>*driver_license_number</code></td>
      <td><code>string</code></td>
      <td>Número da CNH</td>
    </tr>
    <tr>
      <td><code>*license_category</code></td>
      <td><code>string</code></td>
      <td>Categoria de habilitação (ex: <code>C</code>, <code>D</code>, <code>E</code>)</td>
    </tr>
  </tbody>
</table>

### Trip

<table>
  <thead>
    <tr>
      <th width="40%" align="left">Campo</th>
      <th width="20%" align="left">Tipo</th>
      <th width="40%" align="left">Descrição</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>*ref</code></td>
      <td><code>string</code></td>
      <td>Referência única da viagem no seu TMS/ERP (ex: número do MDF-e ou CT-e). Usada em todas as consultas e atualizações</td>
    </tr>
    <tr>
      <td><code>*layout_ref</code></td>
      <td><code>string</code></td>
      <td>Código do layout dinâmico associado</td>
    </tr>
    <tr>
      <td><code>vehicle_plate</code></td>
      <td><code>string</code></td>
      <td>Placa do caminhão/carreta</td>
    </tr>
    <tr>
      <td><code>summary</code></td>
      <td><code>string</code></td>
      <td>Observações ou detalhes adicionais da rota</td>
    </tr>
    <tr>
      <td><code>start_time</code></td>
      <td><code>string</code> ISO-8601</td>
      <td>Início previsto da viagem</td>
    </tr>
    <tr>
      <td><code>end_time</code></td>
      <td><code>string</code> ISO-8601</td>
      <td>Término previsto</td>
    </tr>
    <tr>
      <td><code>schedule_start_tolerance</code></td>
      <td><code>integer</code></td>
      <td>Margem de tolerância em minutos antes do início (default: <code>0</code>)</td>
    </tr>
    <tr>
      <td><code>schedule_end_tolerance</code></td>
      <td><code>integer</code></td>
      <td>Margem de tolerância em minutos após o término (default: <code>0</code>)</td>
    </tr>
    <tr>
      <td><code>custom_data</code></td>
      <td><code>object</code></td>
      <td>Metadados dinâmicos estruturados da viagem</td>
    </tr>
  </tbody>
</table>

### Dados Geográficos de Origem

<table>
  <thead>
    <tr>
      <th width="40%" align="left">Campo</th>
      <th width="20%" align="left">Tipo</th>
      <th width="40%" align="left">Descrição</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>from_location</code></td>
      <td><code>string</code></td>
      <td>Descrição textual da origem (ex: <code>Fábrica de Cimento Votorantim</code>)</td>
    </tr>
    <tr>
      <td><code>origin_street</code></td>
      <td><code>string</code></td>
      <td>Nome da rua/avenida</td>
    </tr>
    <tr>
      <td><code>origin_number</code></td>
      <td><code>string</code></td>
      <td>Número predial</td>
    </tr>
    <tr>
      <td><code>origin_city</code></td>
      <td><code>string</code></td>
      <td>Cidade</td>
    </tr>
    <tr>
      <td><code>origin_state</code></td>
      <td><code>string</code></td>
      <td>Estado (sigla com 2 caracteres, ex: <code>SP</code>)</td>
    </tr>
    <tr>
      <td><code>origin_country</code></td>
      <td><code>string</code></td>
      <td>País</td>
    </tr>
    <tr>
      <td><code>origin_zip</code></td>
      <td><code>string</code></td>
      <td>CEP (apenas números)</td>
    </tr>
    <tr>
      <td><code>origin_lat</code></td>
      <td><code>float</code></td>
      <td>Latitude para geofencing (ex: <code>-20.1219</code>)</td>
    </tr>
    <tr>
      <td><code>origin_lng</code></td>
      <td><code>float</code></td>
      <td>Longitude para geofencing (ex: <code>-44.1997</code>)</td>
    </tr>
  </tbody>
</table>

### Dados Geográficos de Destino

<table>
  <thead>
    <tr>
      <th width="40%" align="left">Campo</th>
      <th width="20%" align="left">Tipo</th>
      <th width="40%" align="left">Descrição</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>to_location</code></td>
      <td><code>string</code></td>
      <td>Descrição textual do destino (ex: <code>Centro de Distribuição Cajamar</code>)</td>
    </tr>
    <tr>
      <td><code>destiny_street</code></td>
      <td><code>string</code></td>
      <td>Nome da rua/avenida</td>
    </tr>
    <tr>
      <td><code>destiny_number</code></td>
      <td><code>string</code></td>
      <td>Número predial</td>
    </tr>
    <tr>
      <td><code>destiny_city</code></td>
      <td><code>string</code></td>
      <td>Cidade</td>
    </tr>
    <tr>
      <td><code>destiny_state</code></td>
      <td><code>string</code></td>
      <td>Estado (sigla com 2 caracteres)</td>
    </tr>
    <tr>
      <td><code>destiny_country</code></td>
      <td><code>string</code></td>
      <td>País</td>
    </tr>
    <tr>
      <td><code>destiny_zip</code></td>
      <td><code>string</code></td>
      <td>CEP (apenas números)</td>
    </tr>
    <tr>
      <td><code>destiny_lat</code></td>
      <td><code>float</code></td>
      <td>Latitude do destino</td>
    </tr>
    <tr>
      <td><code>destiny_lng</code></td>
      <td><code>float</code></td>
      <td>Longitude do destino</td>
    </tr>
  </tbody>
</table>

---

## Criar Viagem(ns) (POST)

**Endpoint:** `POST /api/v1/trips` — **`201 Created`**

> [!NOTE]
> Este endpoint aceita tanto um **único objeto** quanto uma **lista (array) de objetos** para criação em lote.

### Regras de Negócio

> **Importante:**
> * **Fail-Fast (Chaves Duplicadas):** Se algum `ref` já existir associado à sua empresa, toda a transação falha (`409 Conflict`).
> * **Fail-Fast (Layout Inválido):** Referências de layout inexistentes retornam `400 Bad Request`.

### Payload de Exemplo
```json
[
  {
    "driver": {
      "tax_id": "98765432109",
      "driver_license_number": "1234567890",
      "license_category": "D"
    },
    "trip": {
      "ref": "TR-MDFE-4819",
      "layout_ref": "layout-mineracao-v2",
      "vehicle_plate": "BRA2E19",
      "start_time": "2026-07-16T06:00:00Z",
      "end_time": "2026-07-16T18:00:00Z",
      "schedule_start_tolerance": 30,
      "schedule_end_tolerance": 60,
      "from_location": "Sede Mineradora Brumadinho",
      "origin_city": "Brumadinho",
      "origin_state": "MG",
      "origin_lat": -20.1219,
      "origin_lng": -44.1997,
      "to_location": "Porto de Tubarão",
      "destiny_city": "Vitória",
      "destiny_state": "ES",
      "destiny_lat": -20.2878,
      "destiny_lng": -40.2882,
      "summary": "Transporte de Minério de Ferro bruto.",
      "custom_data": {
        "mdf_key": "31260712345678901234580010000048191000048198"
      }
    }
  }
]
```

### Exemplos de Código

#### cURL
```bash
curl -X POST "https://api.gatein.com/api/v1/trips" \
  -H "X-API-Key: sk_live_suachave" \
  -H "Content-Type: application/json" \
  -d '[{"driver":{"tax_id":"98765432109","driver_license_number":"1234567890","license_category":"D"},"trip":{"ref":"TR-MDFE-4819","layout_ref":"layout-mineracao-v2","vehicle_plate":"BRA2E19"}}]'
```

#### Python
```python
import requests

url = "https://api.gatein.com/api/v1/trips"
headers = {"X-API-Key": "sk_live_suachave", "Content-Type": "application/json"}
payload = [
    {
        "driver": {"tax_id": "98765432109", "driver_license_number": "1234567890", "license_category": "D"},
        "trip": {
            "ref": "TR-MDFE-4819",
            "layout_ref": "layout-mineracao-v2",
            "vehicle_plate": "BRA2E19",
            "from_location": "Filial SP",
            "to_location": "Porto Santos"
        }
    }
]

response = requests.post(url, headers=headers, json=payload)
print(response.json())
```

---

## Atualizar Viagem(ns) (PUT)

**Endpoint:** `PUT /api/v1/trips`

> [!NOTE]
> Este endpoint aceita tanto um **único objeto** de atualização quanto uma **lista (array) de objetos** para atualização em lote.

### Campos Protegidos (não editáveis)

<table>
  <thead>
    <tr>
      <th width="30%" align="left">Campo</th>
      <th width="70%" align="left">Motivo</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>id</code></td>
      <td>Chave primária interna</td>
    </tr>
    <tr>
      <td><code>trucking_company_id</code></td>
      <td>Vínculo de propriedade imutável</td>
    </tr>
    <tr>
      <td><code>ref</code></td>
      <td>Chave de referência externa — usada como identificador</td>
    </tr>
    <tr>
      <td><code>driver_id</code></td>
      <td>Identidade do motorista vinculado</td>
    </tr>
  </tbody>
</table>


### Payload de Exemplo
```json
[
  {
    "ref": "TR-MDFE-4819",
    "trip": {
      "vehicle_plate": "NEW3A21",
      "summary": "Placa de cavalo mecânico substituída por pane mecânica."
    }
  }
]
```

---

## Cancelar / Deletar Viagem(ns) (DELETE)

**Endpoint:** `DELETE /api/v1/trips`

> [!NOTE]
> Este endpoint aceita tanto uma **única string** de referência quanto um **array de strings** para cancelamento em lote.

Altera o status da viagem para `DELETED`. Exemplo de envio em lote:

```json
["TR-MDFE-4819"]
```

---

## Consultar Logs e Histórico de Rastreamento (GET)

**Endpoint:** `GET /api/v1/trips/logs`

### Query Parameters

<table>
  <thead>
    <tr>
      <th width="20%" align="left">Parâmetro</th>
      <th width="20%" align="left">Tipo</th>
      <th width="60%" align="left">Descrição</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>refs</code></td>
      <td><code>string[]</code></td>
      <td>Repita o parâmetro para múltiplos valores: <code>?refs=TR-MDFE-4819&amp;refs=TR-MDFE-4820</code></td>
    </tr>
  </tbody>
</table>


### Resposta de Exemplo
```json
{
  "success": true,
  "data": [
    {
      "ref": "TR-MDFE-4819",
      "found": true,
      "data": {
        "trip": {
          "id": "f5e92716-11f8-4cb3-a5c6-c9a7d36d8f1e",
          "trucking_company_id": "b3e9281a-12f8-4cb3-a5c6-d9a7e36d8f92",
          "ref": "TR-MDFE-4819",
          "layout_ref": "layout-mineracao-v2",
          "driver_id": "d1d82761-b7e1-4560-84c4-f2a8c17df20b",
          "vehicle_plate": "NEW3A21",
          "status": "CREATED",
          "summary": "Transporte de minério de ferro",
          "schedule_start_time": "2026-07-16T06:00:00Z",
          "schedule_end_time": "2026-07-16T18:00:00Z",
          "schedule_start_tolerance": 30,
          "schedule_end_tolerance": 60,
          "custom_data": {},
          "origin_street": "Avenida Mineral",
          "origin_number": "1000",
          "origin_city": "Brumadinho",
          "origin_state": "MG",
          "origin_country": "BR",
          "origin_zip": "35460000",
          "origin_lat": -20.1219,
          "origin_lng": -44.1997,
          "destiny_street": "Avenida Portuária",
          "destiny_number": "S/N",
          "destiny_city": "Vitória",
          "destiny_state": "ES",
          "destiny_country": "BR",
          "destiny_zip": "29000000",
          "destiny_lat": -20.3184,
          "destiny_lng": -40.2925,
          "from_location": "Sede Mineradora Brumadinho",
          "to_location": "Porto de Tubarão",
          "created_at": "2026-07-12T12:10:00Z",
          "updated_at": "2026-07-12T12:18:14Z"
        },
        "driver": {
          "tax_id": "98765432109",
          "driver_license_number": "1234567890",
          "driver_license_category": "D"
        },
        "logs": [
          { "event": "updated", "message": "Viagem atualizada via API.", "created_at": "2026-07-12T12:18:14.000000" },
          { "event": "created", "message": "Viagem criada via API.", "created_at": "2026-07-12T12:10:00.000000" }
        ]
      }
    }
  ]
}
```

---

## Erros Comuns

<table>
  <thead>
    <tr>
      <th width="15%" align="left">HTTP</th>
      <th width="35%" align="left">code</th>
      <th width="50%" align="left">Causa</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>400</code></td>
      <td><code>EMPTY_PAYLOAD</code></td>
      <td>Array vazio enviado no body</td>
    </tr>
    <tr>
      <td><code>400</code></td>
      <td><code>INVALID_LAYOUT_REF</code></td>
      <td><code>layout_ref</code> não existe para esta transportadora</td>
    </tr>
    <tr>
      <td><code>409</code></td>
      <td><code>DUPLICATE_KEY</code></td>
      <td>Um ou mais <code>ref</code>s já existem no banco</td>
    </tr>
    <tr>
      <td><code>404</code></td>
      <td><code>REFS_NOT_FOUND</code></td>
      <td><code>ref</code>s informados no PUT/DELETE não foram encontrados</td>
    </tr>
  </tbody>
</table>
