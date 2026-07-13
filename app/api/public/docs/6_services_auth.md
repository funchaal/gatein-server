# Autenticação de Serviços da Empresa (Services Auth)

Quando um usuário acessa um **serviço externo cadastrado por uma empresa parceira** (ex: portal de agendamento, rastreamento de carga ou benefícios), o aplicativo GateIn Mobile autentica o usuário automaticamente através de um handshake seguro baseado em JWT.

---

## Como Funciona o Handshake?

1. O usuário clica em um serviço da empresa no app GateIn Mobile.
2. O app obtém um token JWT de curta duração junto ao servidor GateIn.
3. O app abre uma WebView para a URL do serviço e **injeta o token via JavaScript** no `localStorage` da página antes de ela ser renderizada.
4. O JavaScript da página lê o token do `localStorage` e chama o endpoint `/services/validate-user-token` para validar o usuário.
5. O servidor GateIn retorna os dados do usuário e o site libera o acesso.

---

## Como o Token é Injetado

O GateIn Mobile usa `injectedJavaScript` da WebView para gravar o token no `localStorage` da página do serviço **antes** de qualquer código da página executar:

```javascript
// Código executado pela WebView do GateIn Mobile ao abrir o serviço
(function() {
    window.localStorage.setItem('auth_token', '<jwt_token>');
})();
```

O site da empresa deve ler essa chave ao inicializar:

```javascript
const authToken = window.localStorage.getItem('auth_token');
if (authToken) {
    validateGateInUser(authToken);
}
```

---

## Validando o Token

Após ler o `auth_token` do `localStorage`, faça uma requisição autenticada com sua API Key:

### Headers da Requisição

> [!NOTE]
> Os campos marcados com `*` são obrigatórios.

<table>
  <thead>
    <tr>
      <th width="30%" align="left">Header</th>
      <th width="70%" align="left">Descrição</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>*X-API-Key</code></td>
      <td>Chave de API da sua empresa (<code>sk_live_...</code>)</td>
    </tr>
    <tr>
      <td><code>*Auth-Token</code></td>
      <td>O JWT lido do <code>localStorage.auth_token</code></td>
    </tr>
  </tbody>
</table>

### Campos da Resposta (`data`)

> [!NOTE]
> Os campos marcados com `*` são obrigatórios.

<table>
  <thead>
    <tr>
      <th width="20%" align="left">Campo</th>
      <th width="30%" align="left">Tipo</th>
      <th width="50%" align="left">Descrição</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>*tax_id</code></td>
      <td><code>string</code></td>
      <td>CPF ou CNPJ do usuário</td>
    </tr>
    <tr>
      <td><code>name</code></td>
      <td><code>string | null</code></td>
      <td>Nome completo do usuário</td>
    </tr>
    <tr>
      <td><code>phone</code></td>
      <td><code>string | null</code></td>
      <td>Telefone com DDD</td>
    </tr>
    <tr>
      <td><code>email</code></td>
      <td><code>string | null</code></td>
      <td>E-mail cadastrado (pode ser nulo)</td>
    </tr>
  </tbody>
</table>

---

## Segurança

<table>
  <thead>
    <tr>
      <th width="30%" align="left">Aspecto</th>
      <th width="70%" align="left">Detalhe</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Algoritmo JWT</strong></td>
      <td>HS256, assinado com a chave secreta do GateIn</td>
    </tr>
    <tr>
      <td><strong>Expiração</strong></td>
      <td>3 minutos (180 segundos) — valide imediatamente após abrir a página</td>
    </tr>
    <tr>
      <td><strong>Autenticação</strong></td>
      <td>API Key (<code>X-API-Key</code>) obrigatória em todas as chamadas</td>
    </tr>
    <tr>
      <td><strong>Escopo</strong></td>
      <td>O token dá acesso apenas à leitura de dados do usuário</td>
    </tr>
    <tr>
      <td><strong>Reutilização</strong></td>
      <td>Gere um novo token a cada abertura do serviço</td>
    </tr>
  </tbody>
</table>


---

## Exemplos de Integração

### Lendo e validando o token (JavaScript / fetch)

```javascript
async function validateGateInUser(authToken) {
  const response = await fetch(
    'https://api.gatein.com/api/v1/services/validate-user-token',
    {
      method: 'GET',
      headers: {
        'X-API-Key': 'sk_live_suachavesecreta',
        'Auth-Token': authToken
      }
    }
  );

  if (!response.ok) {
    console.error('Token inválido ou expirado');
    return null;
  }

  const { data } = await response.json();
  console.log('Usuário autenticado:', data.name, data.tax_id);
  return data;
}

// Ponto de entrada — lê o token injetado pelo GateIn Mobile
const authToken = window.localStorage.getItem('auth_token');
if (authToken) {
  validateGateInUser(authToken);
}
```

### Validando no backend (Python)

```python
import requests

def validate_gatein_user(auth_token: str) -> dict | None:
    url = "https://api.gatein.com/api/v1/services/validate-user-token"
    headers = {
        "X-API-Key": "sk_live_suachavesecreta",
        "Auth-Token": auth_token
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["data"]
    return None
```

---

## Erros Comuns

<table>
  <thead>
    <tr>
      <th width="20%" align="left">HTTP</th>
      <th width="30%" align="left">Code</th>
      <th width="50%" align="left">Causa</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>401</code></td>
      <td><code>EXPIRED_TOKEN</code></td>
      <td>Token gerado há mais de 3 minutos</td>
    </tr>
    <tr>
      <td><code>401</code></td>
      <td><code>INVALID_TOKEN</code></td>
      <td>Token malformado ou assinatura inválida</td>
    </tr>
    <tr>
      <td><code>401</code></td>
      <td><code>USER_NOT_FOUND</code></td>
      <td>Usuário referenciado no token não existe mais</td>
    </tr>
    <tr>
      <td><code>401</code></td>
      <td><code>INVALID_API_KEY</code></td>
      <td>A <code>X-API-Key</code> fornecida é inválida</td>
    </tr>
  </tbody>
</table>
