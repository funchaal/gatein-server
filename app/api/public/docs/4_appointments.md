# Gestão de Agendamentos (Appointments)

O módulo de agendamentos foi feito sob medida para **Terminais logísticos e Portuários** gerenciarem o fluxo planejado de entradas e saídas de motoristas e veículos. Todas as operações são feitas em lote (batch) para otimizar a performance da rede e o processamento de dados.

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
      <td>CPF ou CNPJ do motorista (apenas números, sem pontos ou traço)</td>
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


### Appointment

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
      <td>Chave única no seu sistema de origem (ex: ID da Ordem de Carga). Usada para buscar, alterar ou remover o registro</td>
    </tr>
    <tr>
      <td><code>*layout_ref</code></td>
      <td><code>string</code></td>
      <td>ID do layout dinâmico a aplicar a este agendamento</td>
    </tr>
    <tr>
      <td><code>schedule_start_time</code></td>
      <td><code>string</code> ISO-8601</td>
      <td>Horário inicial agendado (ex: <code>2026-07-15T08:00:00Z</code>)</td>
    </tr>
    <tr>
      <td><code>schedule_end_time</code></td>
      <td><code>string</code> ISO-8601</td>
      <td>Horário limite final agendado (ex: <code>2026-07-15T12:00:00Z</code>)</td>
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
      <td><code>vehicle_plate</code></td>
      <td><code>string</code></td>
      <td>Placa do cavalo mecânico ou veículo principal</td>
    </tr>
    <tr>
      <td><code>summary</code></td>
      <td><code>string</code></td>
      <td>Observações ou notas textuais sobre a operação</td>
    </tr>
    <tr>
      <td><code>custom_data</code></td>
      <td><code>object</code></td>
      <td>Campos adicionais chave-valor para armazenamento livre</td>
    </tr>
  </tbody>
</table>


### Customização Dinâmica de Layout (`layout_ref`)

A propriedade `layout_ref` vincula o agendamento a um modelo de layout dinâmico cadastrado, ditando como o GateIn App e o painel web renderizam o agendamento e o **Ticket digital de acesso** do motorista.

#### Elementos do Card / Modal (`card_layout` / `modal_layout`)

<table>
  <thead>
    <tr>
      <th width="30%" align="left">Elemento</th>
      <th width="70%" align="left">Descrição</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>section</code></td>
      <td>Título de seção agrupador</td>
    </tr>
    <tr>
      <td><code>field</code></td>
      <td>Linha com rótulo + valor extraído dinamicamente (ex: <code>driver.name</code>)</td>
    </tr>
    <tr>
      <td><code>alert</code></td>
      <td>Bloco de destaque com cores (<code>purple</code>, <code>blue</code>, <code>green</code>, <code>yellow</code>, <code>red</code>, <code>gray</code>) e ícones</td>
    </tr>
    <tr>
      <td><code>qrcode</code></td>
      <td>Código QR renderizado a partir de uma chave de dados</td>
    </tr>
  </tbody>
</table>

#### Elementos do Ticket Digital (`TicketLayout`)

<table>
  <thead>
    <tr>
      <th width="30%" align="left">Elemento</th>
      <th width="70%" align="left">Descrição</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>divider</code></td>
      <td>Linha separadora horizontal</td>
    </tr>
    <tr>
      <td><code>field</code></td>
      <td>Linha chave-valor (rótulo em cinza, valor em negrito)</td>
    </tr>
    <tr>
      <td><code>section</code></td>
      <td>Divisor com título de agrupamento em caixa alta</td>
    </tr>
    <tr>
      <td><code>tag_container</code></td>
      <td>Grupo de etiquetas coloridas arredondadas</td>
    </tr>
    <tr>
      <td><code>attention</code></td>
      <td>Caixa de alerta com borda e ícone (ex: uso de EPI)</td>
    </tr>
    <tr>
      <td><code>instruction</code></td>
      <td>Lista ordenada com bullets numerados para o fluxo do motorista</td>
    </tr>
    <tr>
      <td><code>text</code></td>
      <td>Parágrafo de texto livre (avisos, regras, informações legais)</td>
    </tr>
    <tr>
      <td><code>highlight</code> / <code>highlight_grid</code></td>
      <td>Dado em destaque com fonte grande (ex: número da baia, peso na balança)</td>
    </tr>
  </tbody>
</table>


---

## Criar Agendamento(s) (POST)

**Endpoint:** `POST /api/v1/appointments` — **`201 Created`**

> [!NOTE]
> Este endpoint aceita tanto um **único objeto** quanto uma **lista (array) de objetos** para criação em lote.

### Regras de Negócio

> **Importante:**
> * **Fail-Fast (Chaves Duplicadas):** Se algum `ref` já existir, toda a transação sofre rollback (`409 Conflict`).
> * **Fail-Fast (Layout Inválido):** `layout_ref` inexistente retorna `400 Bad Request`.
> * **Criação Inteligente de Motoristas:** Se o `tax_id` não existir, o motorista é criado automaticamente. Se já existir, os dados da CNH são atualizados.

### Payload de Exemplo
```json
[
  {
    "driver": {
      "tax_id": "12345678909",
      "driver_license_number": "9876543210",
      "license_category": "E"
    },
    "appointment": {
      "ref": "AG-2026-009",
      "layout_ref": "layout-graos-v1",
      "schedule_start_time": "2026-07-15T14:00:00Z",
      "schedule_end_time": "2026-07-15T16:00:00Z",
      "schedule_start_tolerance": 30,
      "schedule_end_tolerance": 60,
      "summary": "Descarregamento de Soja Orgânica",
      "vehicle_plate": "ABC1D23",
      "custom_data": {
        "nota_fiscal": "45982",
        "peso_estimado_kg": 42000
      }
    }
  }
]
```

### Exemplos de Código

#### cURL
```bash
curl -X POST "https://api.gatein.com/api/v1/appointments" \
  -H "X-API-Key: sk_live_suachave" \
  -H "Content-Type: application/json" \
  -d '[{"driver":{"tax_id":"12345678909","driver_license_number":"9876543210","license_category":"E"},"appointment":{"ref":"AG-2026-009","layout_ref":"layout-graos-v1"}}]'
```

#### Python
```python
import requests

url = "https://api.gatein.com/api/v1/appointments"
headers = {"X-API-Key": "sk_live_suachave", "Content-Type": "application/json"}
payload = [
    {
        "driver": {"tax_id": "12345678909", "driver_license_number": "9876543210", "license_category": "E"},
        "appointment": {
            "ref": "AG-2026-009",
            "layout_ref": "layout-graos-v1",
            "schedule_start_time": "2026-07-15T14:00:00Z",
            "schedule_end_time": "2026-07-15T16:00:00Z",
            "vehicle_plate": "ABC1D23"
        }
    }
]

response = requests.post(url, headers=headers, json=payload)
print(response.json())
```

---

## Atualizar Agendamento(s) (PUT)

**Endpoint:** `PUT /api/v1/appointments`

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
      <td><code>terminal_id</code></td>
      <td>Vínculo de propriedade imutável</td>
    </tr>
    <tr>
      <td><code>ref</code></td>
      <td>Chave de referência externa — usada como identificador</td>
    </tr>
    <tr>
      <td><code>user_tax_id</code></td>
      <td>Identidade do motorista vinculado</td>
    </tr>
  </tbody>
</table>


### Payload de Exemplo
```json
[
  {
    "ref": "AG-2026-009",
    "appointment": {
      "vehicle_plate": "XYZ9Z99",
      "summary": "Placa de cavalo mecânico atualizada por mudança de frota."
    }
  }
]
```

---

## Cancelar / Deletar Agendamento(s) (DELETE)

**Endpoint:** `DELETE /api/v1/appointments`

> [!NOTE]
> Este endpoint aceita tanto uma **única string** de referência quanto um **array de strings** para cancelamento em lote.

Altera o status do agendamento para `DELETED` e insere logs de auditoria. Exemplo de envio em lote:

```json
["AG-2026-009", "AG-2026-010"]
```

---

## Consultar Logs e Histórico (GET)

**Endpoint:** `GET /api/v1/appointments/logs`

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
      <td>Repita o parâmetro para múltiplos valores: <code>?refs=AG-2026-009&amp;refs=AG-2026-010</code></td>
    </tr>
  </tbody>
</table>


### Resposta de Exemplo
```json
{
  "success": true,
  "data": [
    {
      "ref": "AG-2026-009",
      "found": true,
      "data": {
        "appointment": {
          "id": "c1f72782-b7e1-4560-84c4-f2a8c17df20b",
          "terminal_id": "e3a817a9-17d2-4e92-bc91-2a1c8f1e56ab",
          "ref": "AG-2026-009",
          "layout_ref": "3",
          "user_tax_id": "12345678909",
          "status": "DELETED",
          "summary": "Agendamento cancelado",
          "vehicle_plate": "XYZ9Z99",
          "schedule_start_time": "2026-07-12T10:00:00Z",
          "schedule_end_time": "2026-07-12T12:00:00Z",
          "schedule_start_tolerance": 30,
          "schedule_end_tolerance": 30,
          "custom_data": {
            "ticket_acesso": "TC-90182"
          },
          "created_at": "2026-07-12T09:00:00Z",
          "updated_at": "2026-07-12T10:15:00Z"
        },
        "driver": {
          "tax_id": "12345678909",
          "driver_license_number": "902817265",
          "driver_license_category": "D"
        },
        "logs": [
          { "event": "deleted", "message": "Agendamento deletado/cancelado.", "created_at": "2026-07-12T10:15:00.000000" },
          { "event": "created", "message": "Agendamento criado via API.", "created_at": "2026-07-12T09:00:00.000000" }
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
      <td><code>layout_ref</code> não existe para este terminal</td>
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
