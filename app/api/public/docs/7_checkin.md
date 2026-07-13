# Processo de Check-in Remoto via WebSockets (Socket.IO)

Para permitir a automação na entrada e saída de veículos, o GateIn utiliza uma comunicação bidirecional em tempo real entre o servidor backend e os **terminais físicos (totens/cancelas)** instalados na portaria. Essa comunicação é feita via protocolo WebSockets através do **Socket.IO**.

---

## Fluxo de Comunicação e Handshake

O processo de check-in remoto envolve a coordenação entre o aplicativo mobile do motorista, a API REST, o servidor de sockets e o equipamento físico do terminal.

## Passo a Passo do Fluxo de Check-in

O processo de check-in remoto é composto por seis etapas sequenciais coordenadas em tempo real:

1. **Conexão Persistente (Totem)**: O terminal físico (totem/cancela) inicia uma conexão persistente via WebSockets no namespace `/checkin`, identificando-se com sua chave de API única. O servidor valida a credencial e insere o terminal em uma sala de socket exclusiva identificada pelo UUID da empresa.
2. **Solicitação do Motorista**: Ao se posicionar na entrada do terminal, o motorista solicita o check-in remoto pelo aplicativo enviando um `POST /api/mobile/checkin/{terminal_id}`.
3. **Validação de Disponibilidade**: A API REST verifica se o totem está registrado no dicionário em memória de conexões ativas (`active_terminals`). Se estiver offline, retorna `503 Service Unavailable` imediatamente.
4. **Chamada de Socket (Handshake)**: Caso o totem esteja ativo, o servidor REST invoca uma chamada síncrona de socket (`sio.call`) com timeout de 10 segundos, enviando o CPF/CNPJ do motorista (`tax_id`) por meio do evento `request_checkin`.
5. **Ação Física no Equipamento**: O totem físico recebe o evento, realiza o processamento local (conferência física, pesagem ou impressão térmica de vias) e devolve a lista de tickets gerados no retorno do handshake (Socket ACK).
6. **Persistência & Confirmação**: O servidor recebe a lista de tickets, valida a integridade das referências de layout de impressão contra o banco de dados, marca o agendamento associado como `CHECKED_IN`, grava os tickets no banco de dados e retorna a lista de tickets gerados para o aplicativo móvel (`200 OK`).

---

## 1. Conexão do Equipamento (Totem/Terminal)

O equipamento na ponta deve manter uma conexão de socket persistente com o servidor GateIn.

### Parâmetros de Conexão
* **URL**: `http://<domain>/checkin`
* **Namespace**: `/checkin`
* **Autenticação**: É obrigatório fornecer uma chave de API (`api_key`) ativa.

Você pode passar a chave de autenticação de duas maneiras:
1. **Auth Payload (Recomendado)**: Passar um dicionário contendo a chave `api_key`.
2. **Query Parameters**: Passar como parâmetro de URL (`?api_key=sk_live_...`).

### Exemplo de Conexão (Python client)
```python
import socketio

sio = socketio.Client()

sio.connect(
    'https://api.gatein.com',
    namespaces=['/checkin'],
    auth={'api_key': 'sk_live_suachavesecreta'}
)
```

---

## 2. Eventos do Socket

### Evento Recebido pelo Terminal: `request_checkin`
Quando um motorista clica para fazer check-in próximo ao totem, o servidor envia o evento `request_checkin` para a sala específica do terminal. O terminal deve escutar este evento e retornar a resposta contendo as informações geradas (como um callback/ack).

#### Payload Recebido pelo Terminal
```json
{
  "tax_id": "12345678909"
}
```

#### Resposta Esperada do Terminal (Acknowledgement)
O terminal deve devolver um array de objetos JSON que detalha as ações e os tickets gerados. Caso ocorra erro físico (como falta de papel ou falha de impressora), o totem não deve completar o handshake ou responder com erro.

```json
[
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
        "tipo_operacao": "CARREGAMENTO_SOJA"
      }
    }
  }
]
```

---

## 3. Tratamento de Erros no Fluxo

Durante o ciclo de check-in, podem ocorrer erros nos seguintes pontos:

<table>
  <thead>
    <tr>
      <th width="30%" align="left">Erro</th>
      <th width="30%" align="center">Status HTTP</th>
      <th width="40%" align="left">Causa</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Terminal Offline</strong></td>
      <td><code>503 Service Unavailable</code></td>
      <td>O ID do terminal não possui conexão ativa registrada na memória do servidor.</td>
    </tr>
    <tr>
      <td><strong>Tempo Excedido (Timeout)</strong></td>
      <td><code>504 Gateway Timeout</code></td>
      <td>O terminal demorou mais de 10 segundos para responder ao evento <code>request_checkin</code>.</td>
    </tr>
    <tr>
      <td><strong>Falha de Comunicação</strong></td>
      <td><code>500 Internal Server Error</code></td>
      <td>Erros na camada do socket ou interrupção repentina da rede do totem.</td>
    </tr>
    <tr>
      <td><strong>Formato Inválido</strong></td>
      <td><code>502 Bad Gateway</code></td>
      <td>O terminal respondeu ao ACK mas com um payload que não seja uma lista de tickets válida.</td>
    </tr>
    <tr>
      <td><strong>Falha de Integridade</strong></td>
      <td><code>502 Bad Gateway</code></td>
      <td>O terminal retornou referências de layout (<code>layout_ref</code>) que não existem cadastradas no banco para aquele terminal.</td>
    </tr>
  </tbody>
</table>
